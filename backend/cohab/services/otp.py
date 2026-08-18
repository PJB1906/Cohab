"""OTP delivery behind an interface — same swap-behind-a-protocol pattern as
`TextSimilarity` (services/matching/text.py). No SMTP credentials exist in
this project, so a real email sender is a documented future swap-in, not
built now; `ConsoleOTPSender` is the Phase 4 default.
"""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

logger = logging.getLogger("cohab.otp")


@runtime_checkable
class OTPSender(Protocol):
    def send(self, email: str, code: str) -> None: ...


class ConsoleOTPSender:
    """Logs the code instead of emailing it. Deliberately dev-only: CLAUDE.md
    forbids logging message content, contact details or ID references, but an
    OTP is a verification code with no such sensitivity, and printing it here
    is the only way to complete the flow without real SMTP. A production
    `OTPSender` must send the code by email and must not log it."""

    def send(self, email: str, code: str) -> None:
        logger.info("OTP for %s: %s", email, code)
