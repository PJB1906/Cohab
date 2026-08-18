import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cohab.models.base import (
    Base,
    CreatedAtMixin,
    UpdatedAtMixin,
    UUIDPKMixin,
    check_in,
)

GENDERS = ("male", "female", "non_binary")
SEEKER_TYPES = ("needs_place", "has_place")
VERIFICATION_STATUSES = ("unverified", "pending", "verified")
ACCOUNT_STATUSES = ("active", "suspended", "banned", "erased")

VERIFICATION_METHODS = ("email_otp", "id_document")
VERIFICATION_RECORD_STATUSES = ("pending", "verified", "rejected")


class User(Base, UUIDPKMixin, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = "user"
    __table_args__ = (
        CheckConstraint(check_in("gender", GENDERS), name="ck_user_gender"),
        CheckConstraint(check_in("seeker_type", SEEKER_TYPES), name="ck_user_seeker_type"),
        CheckConstraint(
            check_in("verification_status", VERIFICATION_STATUSES),
            name="ck_user_verification_status",
        ),
        CheckConstraint(
            check_in("account_status", ACCOUNT_STATUSES), name="ck_user_account_status"
        ),
    )

    institution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("institution.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    gender: Mapped[str] = mapped_column(String, nullable=False)
    seeker_type: Mapped[str] = mapped_column(String, nullable=False)
    verification_status: Mapped[str] = mapped_column(
        String, nullable=False, default="unverified"
    )
    account_status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    # Cosmetic only, not read by any hard constraint or score — addition beyond
    # COHAB_PRD.md §5.2's ERD, confirmed with the user (Phase 1 planning).
    course: Mapped[str | None] = mapped_column(String, nullable=True)
    # Cosmetic only, same precedent as `course` — served from UPLOAD_DIR via
    # the /media static mount (Phase 5, cohab/api/uploads.py).
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)

    institution: Mapped["Institution"] = relationship(back_populates="users")
    verification_record: Mapped["VerificationRecord"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    preference_profile: Mapped["PreferenceProfile"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    attribute_weights: Mapped[list["UserAttributeWeight"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    listing: Mapped["Listing"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class VerificationRecord(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "verification_record"
    __table_args__ = (
        CheckConstraint(check_in("method", VERIFICATION_METHODS), name="ck_verification_method"),
        CheckConstraint(
            check_in("status", VERIFICATION_RECORD_STATUSES), name="ck_verification_status"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False, unique=True
    )
    method: Mapped[str] = mapped_column(String, nullable=False, default="email_otp")
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    # Object-store key; deleted post dispute-window per PRD §10 DPDP data minimisation.
    id_document_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    document_deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # Pending email-OTP state (Phase 4). Hashed, never the raw code; cleared
    # once verified. `otp_attempts` is the rate-limit counter for guessing.
    otp_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    otp_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    otp_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    user: Mapped["User"] = relationship(back_populates="verification_record")
