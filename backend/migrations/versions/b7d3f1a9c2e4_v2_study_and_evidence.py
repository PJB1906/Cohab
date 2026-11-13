"""v2 W2/W3/W4: study tables (isolated) and stored evidence tables.

Revision ID: b7d3f1a9c2e4
Revises: a1c0e5d2f7b9
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b7d3f1a9c2e4"
down_revision: Union[str, None] = "a1c0e5d2f7b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()
TS = sa.DateTime(timezone=True)
EMPTY_LIST = sa.text("'[]'::jsonb")
EMPTY_OBJ = sa.text("'{}'::jsonb")
SOURCES = "('real', 'dryrun', 'simulation', 'public')"


def upgrade() -> None:
    op.create_table(
        "study_rater",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("cohort", sa.String(), nullable=False),
        sa.Column("consent_version", sa.String(), nullable=True),
        sa.Column("consented_at", TS, nullable=True),
        sa.Column("questionnaire", JSONB, nullable=True),
        sa.Column("important_attributes", JSONB, nullable=False, server_default=EMPTY_LIST),
        sa.Column("demographics", JSONB, nullable=False, server_default=EMPTY_OBJ),
        sa.Column("design_seed", sa.Integer(), nullable=True),
        sa.Column("started_trials_at", TS, nullable=True),
        sa.Column("completed_at", TS, nullable=True),
        sa.Column("withdrawn_at", TS, nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "study_trial",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("rater_id", UUID, sa.ForeignKey("study_rater.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("cards", JSONB, nullable=False),
        sa.Column("varied_attributes", JSONB, nullable=False, server_default=EMPTY_LIST),
        sa.Column("repeat_of", sa.Integer(), nullable=True),
        sa.Column("expected_card", sa.String(), nullable=True),
        sa.Column("presented_at", TS, nullable=True),
        sa.CheckConstraint("kind IN ('pair', 'repeat', 'attention', 'rank')", name="ck_study_trial_kind"),
        sa.UniqueConstraint("rater_id", "position", name="uq_study_trial_position"),
    )
    op.create_table(
        "study_response",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("trial_id", UUID, sa.ForeignKey("study_trial.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("choice", sa.String(), nullable=True),
        sa.Column("ranking", JSONB, nullable=True),
        sa.Column("confidence", sa.Integer(), nullable=True),
        sa.Column("would_message", sa.String(), nullable=True),
        sa.Column("reason_text", sa.String(140), nullable=True),
        sa.Column("response_ms", sa.Integer(), nullable=True),
        sa.Column("answered_at", TS, nullable=False),
        sa.CheckConstraint("choice IS NULL OR choice IN ('left', 'right', 'none')", name="ck_study_response_choice"),
        sa.CheckConstraint(
            "would_message IS NULL OR would_message IN ('left', 'right', 'both', 'neither')",
            name="ck_study_response_would_message",
        ),
        sa.CheckConstraint("confidence IS NULL OR (confidence BETWEEN 1 AND 5)", name="ck_study_response_confidence"),
    )
    op.create_table(
        "study_pair",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("invite_token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("cohort", sa.String(), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "study_pair_member",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("pair_id", UUID, sa.ForeignKey("study_pair.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(1), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("consent_version", sa.String(), nullable=True),
        sa.Column("consented_at", TS, nullable=True),
        sa.Column("questionnaire", JSONB, nullable=True),
        sa.Column("important_attributes", JSONB, nullable=False, server_default=EMPTY_LIST),
        sa.Column("roommate_ratings", JSONB, nullable=True),
        sa.Column("outcomes", JSONB, nullable=True),
        sa.Column("months_together", sa.Float(), nullable=True),
        sa.Column("still_together", sa.Boolean(), nullable=True),
        sa.Column("free_text", sa.Text(), nullable=True),
        sa.Column("submitted_at", TS, nullable=True),
        sa.CheckConstraint("role IN ('a', 'b')", name="ck_study_pair_member_role"),
        sa.UniqueConstraint("pair_id", "role", name="uq_study_pair_member_role"),
    )
    op.create_table(
        "analysis_run",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("data_source", sa.String(), nullable=False),
        sa.Column("provenance", JSONB, nullable=False, server_default=EMPTY_OBJ),
        sa.Column("payload", JSONB, nullable=False),
        sa.CheckConstraint(f"data_source IN {SOURCES}", name="ck_analysis_run_source"),
    )
    op.create_index("ix_analysis_run_kind", "analysis_run", ["kind"])
    op.create_table(
        "calibration_model",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, unique=True),
        sa.Column("target", sa.String(), nullable=False),
        sa.Column("weight_set_id", UUID, sa.ForeignKey("weight_set.id"), nullable=False),
        sa.Column("data_source", sa.String(), nullable=False),
        sa.Column("knots", JSONB, nullable=False),
        sa.Column("metrics", JSONB, nullable=False, server_default=EMPTY_OBJ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("published_at", TS, nullable=True),
        sa.CheckConstraint(f"data_source IN {SOURCES}", name="ck_calibration_source"),
    )
    op.create_table(
        "weight_set_uncertainty",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("weight_set_id", UUID, sa.ForeignKey("weight_set.id"), nullable=False, unique=True),
        sa.Column("method", sa.String(), nullable=False),
        sa.Column("samples", JSONB, nullable=False),
    )


def downgrade() -> None:
    for table in (
        "weight_set_uncertainty",
        "calibration_model",
        "analysis_run",
        "study_pair_member",
        "study_pair",
        "study_response",
        "study_trial",
        "study_rater",
    ):
        op.drop_table(table)
