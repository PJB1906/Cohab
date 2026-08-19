"""phase 7 safety

Revision ID: 4b7c9f2a1d63
Revises: 1eac5ce1061c
Create Date: 2026-08-19 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '4b7c9f2a1d63'
down_revision: Union[str, None] = '1eac5ce1061c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default backfills existing rows, matching the precedent in
    # 1221949ea658 — ADD COLUMN ... NOT NULL fails outright on a non-empty
    # table without one. The ORM-level default (models/user.py) covers new
    # rows from here on.
    op.add_column('user', sa.Column('is_moderator', sa.Boolean(), nullable=False, server_default=sa.false()))

    # `moderator` has no live writer yet (Phase 7 introduces the first one),
    # so this is safe to add NOT NULL with no server_default.
    op.add_column('moderator', sa.Column('user_id', sa.UUID(), nullable=False))
    op.create_foreign_key('fk_moderator_user_id_user', 'moderator', 'user', ['user_id'], ['id'])
    op.create_unique_constraint('uq_moderator_user_id', 'moderator', ['user_id'])

    op.add_column('report', sa.Column('resolution_note', sa.Text(), nullable=True))
    op.add_column('report', sa.Column('sanction', sa.String(), nullable=True))
    op.create_check_constraint(
        'ck_report_sanction',
        'report',
        "sanction IS NULL OR (sanction IN ('warn', 'suspend', 'ban'))",
    )


def downgrade() -> None:
    op.drop_constraint('ck_report_sanction', 'report', type_='check')
    op.drop_column('report', 'sanction')
    op.drop_column('report', 'resolution_note')

    # `moderator` rows only ever exist because Phase 7's `get_or_create_
    # moderator` created them (linked to a `user_id`) — without that
    # column they're meaningless orphans, not data worth preserving through
    # a rollback. Clearing the table here, not just dropping the column,
    # is what keeps `upgrade()`'s `ADD COLUMN user_id ... NOT NULL` (no
    # server_default) valid on a subsequent re-upgrade — found live: a
    # downgrade -> upgrade round trip on a DB where any moderator had
    # actually been created failed with a NOT NULL violation without this.
    # `report.assigned_moderator_id` (nullable since Phase 1, f0f781556f25)
    # FKs to `moderator` too and must be cleared first, or the delete below
    # hits the same FK violation one layer up — also found live.
    op.execute('UPDATE report SET assigned_moderator_id = NULL')
    op.execute('DELETE FROM moderator')
    op.drop_constraint('uq_moderator_user_id', 'moderator', type_='unique')
    op.drop_constraint('fk_moderator_user_id_user', 'moderator', type_='foreignkey')
    op.drop_column('moderator', 'user_id')

    op.drop_column('user', 'is_moderator')
