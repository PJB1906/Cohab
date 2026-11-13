"""Small in-process sliding-window rate limiter (v2 audit).

The study endpoints that create rows need no account, so without a limit a
script could fill `study_rater` / `study_pair` with millions of rows. The
limits are generous on purpose: a whole class doing the study in one session
shares a single campus NAT address, and the aim is to stop automated abuse,
not people.

In-process state is exact for the pilot's single uvicorn worker (CLAUDE.md);
more workers would each keep their own window, which only loosens the limit.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status


class SlidingWindowLimiter:
    def __init__(self, max_events: int, window_seconds: float) -> None:
        self.max_events = max_events
        self.window = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, now: float | None = None) -> bool:
        """Record one event for `key`; False if it would exceed the limit."""
        now = time.monotonic() if now is None else now
        with self._lock:
            q = self._events[key]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.max_events:
                return False
            q.append(now)
            if len(self._events) > 50_000:  # bound memory under a key flood
                for k in [k for k, v in self._events.items() if not v]:
                    del self._events[k]
            return True

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


def client_key(request: Request) -> str:
    """Behind Render's proxy every request arrives from the proxy address, so
    the first X-Forwarded-For hop identifies the caller. It can be forged,
    which only lets a caller spread its own requests across keys; a global
    cap below bounds that case too."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return request.client.host if request.client else "unknown"


# Per address: 200 new study sessions an hour. Overall: 3,000 a day.
study_per_client = SlidingWindowLimiter(200, 3600)
study_global = SlidingWindowLimiter(3000, 86400)


def limit_study_creation(request: Request) -> None:
    if not study_per_client.hit(client_key(request)) or not study_global.hit("all"):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many new study sessions from this network right now. Please try again later.",
        )
