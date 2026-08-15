import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from cohab.models.base import Base, UUIDPKMixin, check_in

# COHAB_PRD.md §10 DPDP Act — consent per purpose.
CONSENT_PURPOSES = ("matching", "communication", "analytics")


class ConsentRecord(Base, UUIDPKMixin):
    __tablename__ = "consent_record"
    __table_args__ = (
        CheckConstraint(check_in("purpose", CONSENT_PURPOSES), name="ck_consent_record_purpose"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    purpose: Mapped[str] = mapped_column(String, nullable=False)
    notice_version: Mapped[str] = mapped_column(String, nullable=False)
    granted_at: Mapped[datetime] = mapped_column(nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)
