"""Stored analysis outputs the app can display (Cohab v2 plan W4 and W6).

`analysis_run` holds each reproducible analysis result as JSON, tagged with
where its data came from. `data_source` is the guard rail for deck
invariant 6: the evidence page renders the tag on every chart, and a
`synthetic` or `dryrun` result is never presented as evidence about people.

`calibration_model` and `weight_set_uncertainty` are versioned, immutable
inputs the live match API reads (confidence tiers, tie hint).
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from cohab.models.base import Base, CreatedAtMixin, UUIDPKMixin, check_in

DATA_SOURCES = ("real", "dryrun", "simulation", "public")


class AnalysisRun(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "analysis_run"
    __table_args__ = (CheckConstraint(check_in("data_source", DATA_SOURCES), name="ck_analysis_run_source"),)

    kind: Mapped[str] = mapped_column(String, nullable=False, index=True)
    data_source: Mapped[str] = mapped_column(String, nullable=False)
    # Git commit + seed + input hash, so a stored result names how to regenerate it.
    provenance: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)


class CalibrationModel(Base, UUIDPKMixin, CreatedAtMixin):
    """Isotonic map from a directional score to a probability, versioned."""

    __tablename__ = "calibration_model"
    __table_args__ = (CheckConstraint(check_in("data_source", DATA_SOURCES), name="ck_calibration_source"),)

    version: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    # What the probability is OF. v2 can only support "would_message".
    target: Mapped[str] = mapped_column(String, nullable=False)
    weight_set_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("weight_set.id"), nullable=False)
    data_source: Mapped[str] = mapped_column(String, nullable=False)
    # Piecewise-linear knots: {"x": [...], "y": [...]}, x ascending.
    knots: Mapped[dict] = mapped_column(JSONB, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WeightSetUncertainty(Base, UUIDPKMixin, CreatedAtMixin):
    """Resampled weight vectors for one weight set: bootstrap refits for a
    fitted set, or a declared prior perturbation for an expert set."""

    __tablename__ = "weight_set_uncertainty"

    weight_set_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("weight_set.id"), nullable=False, unique=True
    )
    method: Mapped[str] = mapped_column(String, nullable=False)  # "bootstrap_raters" | "dirichlet_prior"
    samples: Mapped[list] = mapped_column(JSONB, nullable=False)  # list of {attr: weight}
