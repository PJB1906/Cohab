import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from cohab.models.base import Base, CreatedAtMixin, UUIDPKMixin


class Message(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "message"

    match_score_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("match_score.id"), nullable=False
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    # Encrypted at rest under a server-held key — COHAB_PRD.md §10. Phase 1
    # stores plaintext; the encryption mechanism is a Phase 6 concern.
    body_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pii_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ContactShare(Base, UUIDPKMixin):
    __tablename__ = "contact_share"
    __table_args__ = (
        UniqueConstraint("match_score_id", "user_id", name="uq_contact_share_score_user"),
    )

    match_score_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("match_score.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    consented_at: Mapped[datetime] = mapped_column(nullable=False)
