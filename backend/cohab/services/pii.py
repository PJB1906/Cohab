"""PII detection on chat send — PRD §9.1 item 1, "the highest-value item in
the whole feature." Regex heuristics for phone numbers, email addresses and
social handles — an MVP detector in the same spirit as `TfidfSimilarity`
before `EmbeddingSimilarity` (build plan §2): good enough to interrupt the
common case, not a claim of completeness. False negatives are a documented
limitation, not a bug; false positives are why `ChatService.send_message`
takes a `confirm` override rather than hard-blocking forever.
"""

from __future__ import annotations

import re

# Indian mobile numbers: optional +91/91/0 prefix, then 10 digits, each
# optionally preceded by a single space/hyphen — covers "9876543210",
# "98765 43210" (the common 5+5 spacing), "987-654-3210", "+91 98765 43210".
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[\s-]?|0)?[6-9](?:[\s-]?\d){9}(?!\d)")

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# Handles/links for the apps people actually redirect to: an @handle of
# meaningful length, a bare mention of the app as its own word ("on insta"),
# or a link with a handle after it. The bare-word branch is \b-wrapped on
# both sides and the link branch requires an actual "/" or ":" before the
# handle — an earlier, looser version matched "insta" as a mere prefix, so
# "instantly"/"instance" were flagged as PII (found in code review).
_HANDLE_RE = re.compile(
    r"(?:^|\s)@\w{3,}"
    r"|\b(?:instagram|insta)\b"
    r"|\b(?:wa\.me|t\.me|instagram\.com)[/:]\s*@?\w+",
    re.IGNORECASE,
)


def detect_pii(text: str) -> bool:
    return bool(_PHONE_RE.search(text) or _EMAIL_RE.search(text) or _HANDLE_RE.search(text))
