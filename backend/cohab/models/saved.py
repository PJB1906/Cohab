"""Saved matches — a user bookmarks another user's match to compare later.

New scope: not in `docs/COHAB_PRD.md` or `docs/COHAB_MATCHING_SPEC.md`. Added
while porting the mobile mockup's "Saved" tab, which has no backend support
yet. `UNIQUE (user_id, match_score_id)` mirrors `UserBlock`'s
`uq_user_block_pair` (safety.py) — one save per (user, match) pair, so a
repeat save is idempotent at the DB level too, not just in the service.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from cohab.models.base import Base, CreatedAtMixin, UUIDPKMixin


class SavedMatch(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "saved_match"
    __table_args__ = (
        UniqueConstraint("user_id", "match_score_id", name="uq_saved_match_user_pair"),
    )

    # The person who saved it — not necessarily user_id_a/user_id_b's
    # ordering on match_score, just whichever party bookmarked it.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    match_score_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("match_score.id"), nullable=False
    )
