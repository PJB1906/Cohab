"""Structured logs, request IDs and a minimal /metrics (Cohab v2 plan W1).

No new dependency: a JSON log formatter, a contextvar carrying the request ID
into every log line emitted while that request is handled, and in-process
counters rendered in the Prometheus text format. Counters are per-process,
which is exact for the pilot's single uvicorn worker (CLAUDE.md) and would
need a shared backend before running more workers.
"""

from __future__ import annotations

import contextvars
import json
import logging
import threading
import time
import uuid
from collections import defaultdict

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        rid = request_id_var.get()
        if rid:
            payload["request_id"] = rid
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(json_logs: bool) -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter() if json_logs else logging.Formatter("%(name)s: %(message)s"))
    root.handlers = [handler]


def new_request_id(incoming: str | None) -> str:
    # Accept a caller-supplied ID only if it looks like one we would mint, so
    # a client cannot inject arbitrary text into every log line.
    if incoming and len(incoming) <= 64 and all(c.isalnum() or c == "-" for c in incoming):
        return incoming
    return uuid.uuid4().hex


class Metrics:
    """Request counts by (method, route template, status) and a latency sum."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.requests: dict[tuple[str, str, int], int] = defaultdict(int)
        self.latency_sum: dict[tuple[str, str], float] = defaultdict(float)
        self.latency_count: dict[tuple[str, str], int] = defaultdict(int)

    def observe(self, method: str, route: str, status: int, seconds: float) -> None:
        with self._lock:
            self.requests[(method, route, status)] += 1
            self.latency_sum[(method, route)] += seconds
            self.latency_count[(method, route)] += 1

    def render(self) -> str:
        lines = [
            "# HELP cohab_http_requests_total HTTP requests by method, route and status.",
            "# TYPE cohab_http_requests_total counter",
        ]
        with self._lock:
            for (method, route, status), n in sorted(self.requests.items()):
                lines.append(
                    f'cohab_http_requests_total{{method="{method}",route="{route}",status="{status}"}} {n}'
                )
            lines += [
                "# HELP cohab_http_request_seconds Request latency.",
                "# TYPE cohab_http_request_seconds summary",
            ]
            for (method, route), total in sorted(self.latency_sum.items()):
                count = self.latency_count[(method, route)]
                labels = f'method="{method}",route="{route}"'
                lines.append(f"cohab_http_request_seconds_sum{{{labels}}} {total:.6f}")
                lines.append(f"cohab_http_request_seconds_count{{{labels}}} {count}")
        return "\n".join(lines) + "\n"


metrics = Metrics()
