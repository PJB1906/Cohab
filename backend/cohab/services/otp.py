"""OTP delivery behind an interface — same swap-behind-a-protocol pattern as
`TextSimilarity` (services/matching/text.py). `ConsoleOTPSender` was the only
implementation through Phase 4-10; `ResendOTPSender` (docs/DECISIONS.md,
Phase 11 addendum) closes the "documented future swap-in" this module's own
docstring used to flag, using the Resend transactional-email API since the
user already holds an account there. `get_otp_sender()` picks between them
from config so `cohab/api/auth.py`'s call sites don't need to know which is
active.
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText
from typing import Protocol, runtime_checkable

import httpx

from cohab.core.config import (
    OTP_SENDER_EMAIL,
    RESEND_API_KEY,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USER,
)

logger = logging.getLogger("cohab.otp")

RESEND_API_URL = "https://api.resend.com/emails"


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


class OTPDeliveryFailed(Exception):
    """Raised when the Resend API rejects or fails to deliver the email —
    kept distinct from `InvalidOTP`/`OTPExpired` etc. (services/auth.py) so
    callers can tell "we couldn't send it" from "the user got it wrong"."""


class ResendOTPSender:
    """Sends the code as a real email via the Resend API
    (https://resend.com/docs/api-reference/emails/send-email). Never logs the
    code (CLAUDE.md: no message content/contact details in logs — an OTP
    delivered by a real channel is exactly the sensitive case that rule is
    for, unlike `ConsoleOTPSender`'s dev-only exception).

    `from_email` defaults to Resend's own shared sandbox address
    (`onboarding@resend.dev`), not the developer's personal address, per the
    user's explicit requirement. That sandbox address only delivers to the
    email the Resend account itself was signed up with until a real sending
    domain is verified in the Resend dashboard — a real pilot (many distinct
    student recipients) needs that domain verification done first; this
    class has no way to detect or work around that limit itself, it will
    just get an API error for any other recipient in the meantime.
    """

    def __init__(self, api_key: str, from_email: str) -> None:
        self._api_key = api_key
        self._from_email = from_email

    def send(self, email: str, code: str) -> None:
        try:
            response = httpx.post(
                RESEND_API_URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "from": self._from_email,
                    "to": [email],
                    "subject": "Your Cohab verification code",
                    "html": f"<p>Your Cohab verification code is <strong>{code}</strong>. "
                    "It expires in 10 minutes.</p>",
                },
                timeout=10.0,
            )
        except httpx.HTTPError as exc:
            raise OTPDeliveryFailed(str(exc)) from exc
        if response.status_code >= 400:
            raise OTPDeliveryFailed(f"Resend API returned {response.status_code}: {response.text}")


class SMTPOTPSender:
    """Plain SMTP via `smtplib` (stdlib, no domain/DNS verification needed —
    unlike Resend without a verified domain, this delivers to any recipient).
    Meant for a throwaway mailbox (e.g. a fresh Gmail account + app
    password), not the developer's personal address, same requirement as
    `ResendOTPSender`."""

    def __init__(self, host: str, port: int, user: str, password: str, from_email: str) -> None:
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._from_email = from_email

    def send(self, email: str, code: str) -> None:
        msg = MIMEText(f"Your Cohab verification code is {code}. It expires in 10 minutes.")
        msg["Subject"] = "Your Cohab verification code"
        msg["From"] = self._from_email
        msg["To"] = email
        try:
            with smtplib.SMTP(self._host, self._port, timeout=10) as server:
                server.starttls()
                server.login(self._user, self._password)
                server.sendmail(self._from_email, [email], msg.as_string())
        except (smtplib.SMTPException, OSError) as exc:
            raise OTPDeliveryFailed(str(exc)) from exc


def get_otp_sender() -> OTPSender:
    """SMTP config set → plain SMTP (works for any recipient, no domain
    verification). Else `RESEND_API_KEY` set → Resend. Else console log,
    same as every session before this one."""
    if SMTP_HOST and SMTP_USER and SMTP_PASSWORD:
        return SMTPOTPSender(
            host=SMTP_HOST, port=SMTP_PORT, user=SMTP_USER, password=SMTP_PASSWORD, from_email=OTP_SENDER_EMAIL
        )
    if RESEND_API_KEY:
        return ResendOTPSender(api_key=RESEND_API_KEY, from_email=OTP_SENDER_EMAIL)
    return ConsoleOTPSender()
