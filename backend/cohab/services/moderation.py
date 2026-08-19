"""Abuse-content flagging on chat send — PRD §9.1 item 2: "flag for review;
do not block outright, to avoid suppressing legitimate conversation." Same
swap-behind-a-protocol pattern as `TextSimilarity` (services/matching/text.py)
and `OTPSender` (services/otp.py). `KeywordAbuseFlagger` is a deliberately
small, literal keyword match — Phase 7 builds the moderator queue this feeds;
a real classifier is a documented future swap-in, not built now (mirrors the
TF-IDF -> EmbeddingSimilarity precedent, build plan §2).
"""

from __future__ import annotations

import re
from typing import Protocol, runtime_checkable

# Deliberately short and blunt: unambiguous threats/slurs only, to keep the
# false-positive rate low on ordinary roommate-logistics conversation. Not
# exhaustive — flagged content goes to human review (Phase 7), not an
# automatic sanction, so a narrow list here is a reasonable MVP trade-off.
_ABUSE_KEYWORDS = (
    "kill you",
    "kill yourself",
    "rape",
    "i'll hurt you",
    "i will hurt you",
)

# \b-wrapped: an unanchored "rape" also matches inside "grapes"/"therapeutic"
# (found in code review) — ordinary vocabulary must never get flagged.
_ABUSE_RE = re.compile(
    "|".join(rf"\b{re.escape(w)}\b" for w in _ABUSE_KEYWORDS), re.IGNORECASE
)


@runtime_checkable
class AbuseFlagger(Protocol):
    def flag(self, text: str) -> bool: ...


class KeywordAbuseFlagger:
    def flag(self, text: str) -> bool:
        return bool(_ABUSE_RE.search(text))
