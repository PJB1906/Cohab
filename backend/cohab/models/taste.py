"""Per-member learned taste (services/taste.py)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from cohab.models.base import Base, utcnow


class UserTaste(Base):
    __tablename__ = "user_taste"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), primary_key=True
    )
    # The member can switch learning off; their list then uses stated weights only.
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    model: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    decisions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
