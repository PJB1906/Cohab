"""v2 W1: exposure + state-event logs, match_score instrumentation columns,
and the explicit indexes v1 never had (Cohab v2 plan W1, deck slide 23).

Revision ID: a1c0e5d2f7b9
Revises: 2bb5bde5a3e4
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1c0e5d2f7b9"
down_revision: Union[str, None] = "2bb5bde5a3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REJECTION_REASONS = (
    "not_interested", "budget", "location", "lifestyle", "schedule", "found_elsewhere", "safety", "other",
)

INDEXES = [
    ("ix_message_match_created", "message", ["match_score_id", "created_at"]),
    ("ix_message_sender_created", "message", ["sender_id", "created_at"]),
    ("ix_match_score_user_a_state", "match_score", ["user_id_a", "state"]),
    ("ix_match_score_user_b_state", "match_score", ["user_id_b", "state"]),
    ("ix_match_score_state", "match_score", ["state"]),
    ("ix_report_status", "report", ["status"]),
    ("ix_user_verification_account", "user", ["verification_status", "account_status"]),
    ("ix_user_block_blocked", "user_block", ["blocked_id"]),
]


def upgrade() -> None:
    op.add_column("match_score", sa.Column("rejection_reason", sa.String(), nullable=True))
    op.add_column("match_score", sa.Column("first_shown_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("match_score", sa.Column("first_messaged_at", sa.DateTime(timezone=True), nullable=True))
    quoted = ", ".join(f"'{r}'" for r in REJECTION_REASONS)
    op.create_check_constraint(
        "ck_match_score_rejection_reason",
        "match_score",
        f"rejection_reason IS NULL OR rejection_reason IN ({quoted})",
    )

    op.create_table(
        "match_exposure",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("match_score_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("match_score.id", ondelete="CASCADE"), nullable=False),
        sa.Column("viewer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("shown_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rank_position", sa.Integer(), nullable=False),
        sa.Column("surface", sa.String(), nullable=False),
        sa.Column("policy_version", sa.String(), nullable=False),
        sa.Column("propensity", sa.Float(), nullable=False),
        sa.Column("weight_set_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("weight_set.id"), nullable=False),
        sa.Column("combined_score", sa.Float(), nullable=False),
        sa.CheckConstraint("surface IN ('list', 'detail', 'lab')", name="ck_match_exposure_surface"),
    )
    op.create_index("ix_match_exposure_viewer_shown", "match_exposure", ["viewer_id", "shown_at"])
    op.create_index("ix_match_exposure_match", "match_exposure", ["match_score_id"])

    op.create_table(
        "match_state_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("match_score_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("match_score.id", ondelete="CASCADE"), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("from_state", sa.String(), nullable=True),
        sa.Column("to_state", sa.String(), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_match_state_event_match_at", "match_state_event", ["match_score_id", "at"])

    for name, table, cols in INDEXES:
        op.create_index(name, table, cols)

    # Backfill: one event per pre-existing row, marking the state it was in
    # when instrumentation began. Flagged so analyses can exclude it.
    op.execute(
        """
        INSERT INTO match_state_event (id, match_score_id, at, from_state, to_state, actor_id, metadata)
        SELECT gen_random_uuid(), id, updated_at, NULL, state, NULL, '{"backfill": true}'::jsonb
        FROM match_score
        """
    )


def downgrade() -> None:
    for name, table, _cols in reversed(INDEXES):
        op.drop_index(name, table_name=table)
    op.drop_index("ix_match_state_event_match_at", table_name="match_state_event")
    op.drop_table("match_state_event")
    op.drop_index("ix_match_exposure_match", table_name="match_exposure")
    op.drop_index("ix_match_exposure_viewer_shown", table_name="match_exposure")
    op.drop_table("match_exposure")
    op.drop_constraint("ck_match_score_rejection_reason", "match_score", type_="check")
    op.drop_column("match_score", "first_messaged_at")
    op.drop_column("match_score", "first_shown_at")
    op.drop_column("match_score", "rejection_reason")
