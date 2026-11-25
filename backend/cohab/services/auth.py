"""Registration, email-OTP verification and login — build plan §4 Phase 4.

Framework-free per CLAUDE.md: raises plain exceptions the API layer
translates to HTTP status codes, never touches a `Request`/`Response`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from cohab.core.config import OTP_MAX_ATTEMPTS, OTP_TTL_MINUTES, RESEND_OTP_COOLDOWN_SECONDS
from cohab.core.security import (
    generate_otp,
    hash_otp,
    hash_password,
    verify_otp_hash,
    verify_password,
)
from cohab.models import Institution, User, VerificationRecord
from cohab.services.otp import OTPSender


class AuthError(Exception):
    """Base for every auth-flow failure the API layer maps to a 4xx."""


class UnknownEmailDomain(AuthError):
    pass


class EmailAlreadyRegistered(AuthError):
    pass


class InvalidCredentials(AuthError):
    pass


class AccountNotActive(AuthError):
    pass


class InvalidOTP(AuthError):
    pass


class OTPExpired(AuthError):
    pass


class TooManyOTPAttempts(AuthError):
    pass


class UserNotFound(AuthError):
    pass


class AlreadyVerified(AuthError):
    pass


class ResendTooSoon(AuthError):
    """`resend_otp` cooldown (docs/DECISIONS.md D-10.6) — cheap guard against
    an unauthenticated caller spamming the delivery mechanism or using rapid
    resends to keep resetting `otp_attempts` back to 0."""

    def __init__(self, retry_after_seconds: float) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"retry after {retry_after_seconds:.0f}s")


def _resolve_institution(session: Session, email: str) -> Institution:
    """Suffix match, not exact equality: the part after `@` must equal an
    institution's `email_domain` or end with `"." + email_domain`, so a
    departmental subdomain (e.g. `msds.christuniversity.in`) resolves to the
    `christuniversity.in` row. Confirmed with the user, Phase 4 planning."""
    domain = email.rsplit("@", 1)[-1].lower()
    for institution in session.scalars(select(Institution)).all():
        allowed = institution.email_domain.lower()
        if domain == allowed or domain.endswith("." + allowed):
            return institution
    raise UnknownEmailDomain(domain)


class AuthService:
    def __init__(self, session: Session, otp_sender: OTPSender) -> None:
        self.session = session
        self.otp_sender = otp_sender

    def register(
        self,
        *,
        email: str,
        password: str,
        full_name: str,
        gender: str,
        seeker_type: str,
        course: str | None = None,
        phone_number: str | None = None,
    ) -> User:
        email = email.strip().lower()
        institution = _resolve_institution(self.session, email)

        if self.session.scalar(select(User).where(User.email == email)) is not None:
            raise EmailAlreadyRegistered(email)

        user = User(
            institution_id=institution.id,
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            gender=gender,
            seeker_type=seeker_type,
            course=course,
            phone_number=phone_number,
            verification_status="unverified",
            account_status="active",
        )
        self.session.add(user)
        try:
            self.session.flush()  # assigns user.id for the FK below; hits `uq` on a race
        except IntegrityError as err:
            # Two near-simultaneous registrations with the same email: the
            # earlier `select` above can't see the other transaction's
            # not-yet-committed insert, so both reach here. The loser gets
            # the intended 409 instead of a raw 500.
            self.session.rollback()
            raise EmailAlreadyRegistered(email) from err

        code = generate_otp()
        record = VerificationRecord(
            user_id=user.id,
            method="email_otp",
            status="pending",
            otp_hash=hash_otp(code),
            otp_expires_at=datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES),
            otp_attempts=0,
        )
        self.session.add(record)
        self.session.commit()

        self.otp_sender.send(email, code)
        return user

    def verify_otp(self, *, user_id: uuid.UUID, code: str) -> User:
        user = self.session.get(User, user_id)
        record = (
            self.session.scalars(
                select(VerificationRecord).where(VerificationRecord.user_id == user_id)
            ).first()
            if user is not None
            else None
        )
        if user is None or record is None:
            raise InvalidOTP("no pending verification for this account")

        if record.status == "verified":
            return user  # idempotent: already done

        if record.otp_attempts >= OTP_MAX_ATTEMPTS:
            raise TooManyOTPAttempts()

        if record.otp_expires_at is None or datetime.now(timezone.utc) > record.otp_expires_at:
            raise OTPExpired()

        if record.otp_hash is None or not verify_otp_hash(code, record.otp_hash):
            record.otp_attempts += 1
            self.session.commit()
            raise InvalidOTP()

        record.status = "verified"
        record.verified_at = datetime.now(timezone.utc)
        record.otp_hash = None
        record.otp_expires_at = None
        user.verification_status = "verified"
        self.session.commit()
        return user

    def resend_otp(self, *, email: str) -> User:
        """Recovers a stuck-unverified account, whatever the reason the
        original code is unusable — expired (`OTP_TTL_MINUTES`), attempts
        exhausted (`OTP_MAX_ATTEMPTS`), or simply lost because the user
        closed the tab and no longer has `user_id` (`verify_otp`'s own key).
        Keyed by email instead, so it also closes the "came back later and
        `register()` just says 409" dead end — docs/DECISIONS.md D-10.1.
        Returns the user so the caller (the API layer) can hand its id back
        to a frontend that has no `user_id` of its own to call `verify_otp`
        with (the register()-409 recovery path)."""
        email = email.strip().lower()
        user = self.session.scalar(select(User).where(User.email == email))
        if user is None:
            raise UserNotFound(email)
        if user.verification_status != "unverified":
            raise AlreadyVerified(email)

        record = self.session.scalars(
            select(VerificationRecord).where(VerificationRecord.user_id == user.id)
        ).first()
        if record is None:
            raise UserNotFound(email)  # register() always creates one alongside the user

        if record.otp_expires_at is not None:
            issued_at = record.otp_expires_at - timedelta(minutes=OTP_TTL_MINUTES)
            elapsed = (datetime.now(timezone.utc) - issued_at).total_seconds()
            if elapsed < RESEND_OTP_COOLDOWN_SECONDS:
                raise ResendTooSoon(RESEND_OTP_COOLDOWN_SECONDS - elapsed)

        code = generate_otp()
        record.otp_hash = hash_otp(code)
        record.otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES)
        record.otp_attempts = 0
        self.session.commit()

        self.otp_sender.send(email, code)
        return user

    def request_password_reset(self, *, email: str) -> None:
        """Email a one-time code that lets the owner of `email` set a new
        password (D-14.27). Reuses the account's verification row: same code
        hashing, expiry (`OTP_TTL_MINUTES`), attempt limit and resend cooldown
        as sign-up. An unknown email does nothing, silently, so this endpoint
        cannot be used to find out who has an account."""
        email = email.strip().lower()
        user = self.session.scalar(select(User).where(User.email == email))
        if user is None or user.account_status != "active":
            return
        record = self.session.scalars(
            select(VerificationRecord).where(VerificationRecord.user_id == user.id)
        ).first()
        if record is None:
            record = VerificationRecord(user_id=user.id, method="email_otp", status="pending", otp_attempts=0)
            self.session.add(record)
        elif record.otp_expires_at is not None:
            issued_at = record.otp_expires_at - timedelta(minutes=OTP_TTL_MINUTES)
            elapsed = (datetime.now(timezone.utc) - issued_at).total_seconds()
            if elapsed < RESEND_OTP_COOLDOWN_SECONDS:
                raise ResendTooSoon(RESEND_OTP_COOLDOWN_SECONDS - elapsed)

        code = generate_otp()
        record.otp_hash = hash_otp(code)
        record.otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES)
        record.otp_attempts = 0
        self.session.commit()
        self.otp_sender.send(email, code)

    def reset_password(self, *, email: str, code: str, new_password: str) -> User:
        """Check the emailed code and set the new password. A correct code
        also proves the inbox, so an account that never finished verifying is
        marked verified here too."""
        email = email.strip().lower()
        user = self.session.scalar(select(User).where(User.email == email))
        record = (
            self.session.scalars(select(VerificationRecord).where(VerificationRecord.user_id == user.id)).first()
            if user is not None
            else None
        )
        if user is None or record is None or record.otp_hash is None:
            raise InvalidOTP("no reset code for this account")
        if record.otp_attempts >= OTP_MAX_ATTEMPTS:
            raise TooManyOTPAttempts()
        if record.otp_expires_at is None or datetime.now(timezone.utc) > record.otp_expires_at:
            raise OTPExpired()
        if not verify_otp_hash(code, record.otp_hash):
            record.otp_attempts += 1
            self.session.commit()
            raise InvalidOTP()
        if user.account_status != "active":
            raise AccountNotActive(user.account_status)

        user.password_hash = hash_password(new_password)
        record.otp_hash = None
        record.otp_expires_at = None
        if record.status != "verified":
            record.status = "verified"
            record.verified_at = datetime.now(timezone.utc)
            user.verification_status = "verified"
        self.session.commit()
        return user

    def login(self, *, email: str, password: str) -> User:
        email = email.strip().lower()
        user = self.session.scalar(select(User).where(User.email == email))
        if user is None or not verify_password(password, user.password_hash):
            raise InvalidCredentials()
        if user.account_status != "active":
            raise AccountNotActive(user.account_status)
        return user


class BlankFullName(Exception):
    """`full_name` is `NOT NULL` (models/user.py) — unlike `course`/
    `phone_number`, an empty string can't normalise to `NULL` here. Raised
    rather than silently ignoring the edit, which used to leave the account
    unchanged with no error and no feedback to the caller."""


def update_account(
    session: Session,
    user: User,
    *,
    full_name: str | None = None,
    course: str | None = None,
    phone_number: str | None = None,
) -> User:
    """Apply an account-details edit (docs/DECISIONS.md D-13.9).

    A module-level function rather than an `AuthService` method because it
    needs no `OTPSender` — constructing the service just to rename someone
    would drag an email dependency into a path that never sends mail.

    `None` means "not supplied, leave alone". For `course`/`phone_number`,
    clearing a value is expressed as an empty string, which normalises to
    `NULL`, so a member can remove a phone number they no longer want on
    file. `full_name` can't follow that rule (`NOT NULL`) — an empty/
    whitespace value raises `BlankFullName` instead.
    """
    if full_name is not None:
        cleaned = full_name.strip()
        if not cleaned:
            raise BlankFullName()
        user.full_name = cleaned
    if course is not None:
        user.course = course.strip() or None
    if phone_number is not None:
        user.phone_number = phone_number.strip() or None
    session.commit()
    session.refresh(user)
    return user
