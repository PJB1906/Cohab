import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cohab.models.base import Base, CreatedAtMixin, UpdatedAtMixin, UUIDPKMixin, check_in

ROOM_TYPES = ("private", "shared")


class Listing(Base, UUIDPKMixin, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = "listing"
    __table_args__ = (
        CheckConstraint(check_in("room_type", ROOM_TYPES), name="ck_listing_room_type"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False, unique=True
    )
    locality: Mapped[str] = mapped_column(String, nullable=False)
    rent_per_person: Mapped[int] = mapped_column(Integer, nullable=False)
    deposit: Mapped[int] = mapped_column(Integer, nullable=False)
    room_type: Mapped[str] = mapped_column(String, nullable=False)
    available_from: Mapped[date] = mapped_column(Date, nullable=False)
    amenities: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    photos: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    current_housemates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    user: Mapped["User"] = relationship(back_populates="listing")
