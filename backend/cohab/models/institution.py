from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cohab.models.base import Base, CreatedAtMixin, UUIDPKMixin


class Institution(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "institution"

    name: Mapped[str] = mapped_column(String, nullable=False)
    email_domain: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    users: Mapped[list["User"]] = relationship(back_populates="institution")
