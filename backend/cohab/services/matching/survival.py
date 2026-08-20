"""Kaplan–Meier survival analysis for the 90-day cohabitation metric —
PRD line 53 ("the primary outcome... this will not be measurable inside the
project timeline; the instrumentation is built anyway") and PRD §15
("a right-censored survival problem... the Kaplan–Meier estimator is the
correct treatment").

Hand-rolled rather than a dependency (`lifelines`) — see docs/DECISIONS.md's
Phase 9 section, D-9.3: ~30 lines of standard product-limit estimator is
easier to defend line-by-line than a new library, and matches this project's
established minimal-dependency stance (D-4.5, D-6.2).

The observation unit is the *pair* (`match_score`), not the individual —
`feedback` allows up to two rows per match (`UNIQUE(score_id, submitted_by)`
lets each participant report once), so `load_cohabitation_observations`
reconciles them into one duration/event per pair. See D-9.3 for the
reconciliation policy this implements: either party reporting `moved_out` is
an event at the *smaller* of the two reported durations (the earlier-observed
failure is the true one); otherwise the pair is censored at the *larger* of
the two known durations (the freshest observation).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from cohab.models import Feedback, MatchScore


@dataclass(frozen=True)
class Observation:
    duration_days: int
    event: bool  # True = event observed (moved_out); False = censored


@dataclass(frozen=True)
class KMPoint:
    time: int
    at_risk: int
    events: int
    survival: float


def kaplan_meier(observations: list[Observation]) -> list[KMPoint]:
    """The product-limit estimator. Returns one point per distinct event
    time, S(t) = product over event times <= t of (1 - d_i / n_i), d_i =
    events at t_i, n_i = number still under observation just before t_i
    (duration_days >= t_i — censored rows leave the risk set at their own
    time without contributing a drop, exactly as a censoring should)."""
    if not observations:
        return []

    event_times = sorted({o.duration_days for o in observations if o.event})
    points: list[KMPoint] = []
    survival = 1.0
    for t in event_times:
        at_risk = sum(1 for o in observations if o.duration_days >= t)
        events = sum(1 for o in observations if o.duration_days == t and o.event)
        if at_risk == 0:
            continue  # defensive — can't happen given event_times is drawn from these rows
        survival *= 1 - events / at_risk
        points.append(KMPoint(time=t, at_risk=at_risk, events=events, survival=survival))
    return points


def _duration_for_moved_out(f: Feedback, row: MatchScore) -> int:
    if f.cohabitation_duration_days is not None:
        return f.cohabitation_duration_days
    # `cohabitation_duration_days` is optional even for outcome="moved_out"
    # at both the API schema and FeedbackService.submit() — a client can
    # omit it. Falling through to the censored branch below would silently
    # misclassify a real relationship failure as still-ongoing, which is
    # worse than an approximate duration: fall back to how long the pair
    # had been cohabiting as of the report itself (an upper bound on the
    # true move-out date, since they'd already moved out by the time they
    # reported it). Found by code review, not a live run — no feedback rows
    # exist in the dev DB yet either way; see docs/DECISIONS.md's Phase 9
    # section, D-9.3.
    return max((f.submitted_at - row.cohabiting_since).days, 0)


def _reconcile(row: MatchScore, feedbacks: list[Feedback], now: datetime) -> Observation:
    moved_out = [f for f in feedbacks if f.outcome == "moved_out"]
    if moved_out:
        duration = min(_duration_for_moved_out(f, row) for f in moved_out)
        return Observation(duration_days=duration, event=True)

    still_together = [
        f for f in feedbacks
        if f.outcome == "still_together" and f.cohabitation_duration_days is not None
    ]
    if still_together:
        duration = max(f.cohabitation_duration_days for f in still_together)
    else:
        # Nobody has submitted feedback yet — right-censored at "now",
        # the same computation FeedbackService uses for an in-progress
        # "still_together" report (services/feedback.py:_days_since_cohabiting).
        duration = max((now - row.cohabiting_since).days, 0)
    return Observation(duration_days=duration, event=False)


def load_cohabitation_observations(session: Session) -> list[Observation]:
    """Every `match_score` that reached `cohabiting`, reconciled to one
    (duration, event) pair per match. DB-loading glue, not logic — like
    report.py's/tuning.py's own `_load_candidates`, not unit-tested; sanity-
    checked against the real dev DB when `evaluation.py` is run."""
    rows = session.scalars(
        select(MatchScore).where(MatchScore.state == "cohabiting")
    ).all()

    now = datetime.now(timezone.utc)
    observations: list[Observation] = []
    for row in rows:
        if row.cohabiting_since is None:
            continue  # defensive — shouldn't happen once state is cohabiting
        feedbacks = list(
            session.scalars(
                select(Feedback).where(Feedback.match_score_id == row.id)
            ).all()
        )
        observations.append(_reconcile(row, feedbacks, now))
    return observations
