"""Hand-computed Kaplan-Meier cases (COHAB_BUILD_PLAN.md §3: known inputs,
known outputs). The pure estimator and the per-pair feedback reconciliation
(`_reconcile`) are both covered directly here, with plain in-memory ORM
instances (no DB session needed for attribute construction) — only the
DB-querying half of `load_cohabitation_observations` is left as glue,
sanity-checked against the real dev DB when `evaluation.py` runs (see
docs/DECISIONS.md's Phase 9 section)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from cohab.models import Feedback, MatchScore
from cohab.services.matching.survival import Observation, _reconcile, kaplan_meier

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _row(days_ago: int) -> MatchScore:
    return MatchScore(cohabiting_since=NOW - timedelta(days=days_ago))


def _feedback(outcome: str, duration_days: int | None, submitted_days_ago: int = 0) -> Feedback:
    return Feedback(
        outcome=outcome,
        cohabitation_duration_days=duration_days,
        submitted_at=NOW - timedelta(days=submitted_days_ago),
    )


def test_empty_input_returns_no_points():
    assert kaplan_meier([]) == []


def test_all_censored_has_no_event_times_and_no_points():
    obs = [Observation(5, event=False), Observation(9, event=False)]
    assert kaplan_meier(obs) == []


def test_single_event_no_censoring():
    # n=3 at risk at t=4, 1 event -> S(4) = 1 - 1/3 = 2/3.
    obs = [Observation(4, event=True), Observation(4, event=False), Observation(4, event=False)]
    points = kaplan_meier(obs)
    assert len(points) == 1
    assert points[0].time == 4
    assert points[0].at_risk == 3
    assert points[0].events == 1
    assert points[0].survival == pytest.approx(2 / 3)


def test_tied_events_and_a_later_censoring_then_event():
    # Worked by hand (also the example in survival.py's own module docstring):
    #   durations: (5, event), (5, event), (8, censored), (10, event), (10, censored)
    #   t=5:  at_risk=5 (all 5 rows have duration >= 5), events=2 -> S(5) = 1 - 2/5 = 0.6
    #   t=10: at_risk=2 (only the two duration=10 rows remain >= 10), events=1
    #         -> S(10) = 0.6 * (1 - 1/2) = 0.3
    obs = [
        Observation(5, event=True),
        Observation(5, event=True),
        Observation(8, event=False),
        Observation(10, event=True),
        Observation(10, event=False),
    ]
    points = kaplan_meier(obs)
    assert [p.time for p in points] == [5, 10]

    assert points[0].at_risk == 5
    assert points[0].events == 2
    assert points[0].survival == pytest.approx(0.6)

    assert points[1].at_risk == 2
    assert points[1].events == 1
    assert points[1].survival == pytest.approx(0.3)


def test_survival_is_non_increasing():
    obs = [
        Observation(3, event=True),
        Observation(6, event=True),
        Observation(6, event=False),
        Observation(9, event=True),
        Observation(12, event=False),
    ]
    points = kaplan_meier(obs)
    survivals = [p.survival for p in points]
    assert survivals == sorted(survivals, reverse=True)
    assert survivals[0] <= 1.0
    assert survivals[-1] >= 0.0


# --- _reconcile: per-pair feedback -> one (duration, event) observation ----

def test_reconcile_moved_out_with_duration_is_an_event():
    row = _row(days_ago=40)
    obs = _reconcile(row, [_feedback("moved_out", 25)], NOW)
    assert obs == Observation(duration_days=25, event=True)


def test_reconcile_moved_out_without_a_duration_falls_back_to_submitted_at():
    # cohabitation_duration_days is optional even for moved_out at both the
    # API schema and FeedbackService.submit() — a client can omit it. The
    # bug this guards against: falling through to the censored branch would
    # have silently counted a real relationship failure as still-ongoing.
    row = _row(days_ago=40)
    fb = _feedback("moved_out", None, submitted_days_ago=10)  # reported 10 days ago
    obs = _reconcile(row, [fb], NOW)
    assert obs.event is True
    assert obs.duration_days == 30  # 40 days cohabiting - 10 days since the report


def test_reconcile_two_moved_out_reports_takes_the_smaller_duration():
    row = _row(days_ago=40)
    obs = _reconcile(row, [_feedback("moved_out", 25), _feedback("moved_out", 15)], NOW)
    assert obs == Observation(duration_days=15, event=True)


def test_reconcile_still_together_is_censored_at_the_reported_duration():
    row = _row(days_ago=40)
    obs = _reconcile(row, [_feedback("still_together", 40)], NOW)
    assert obs == Observation(duration_days=40, event=False)


def test_reconcile_no_feedback_yet_is_censored_at_now():
    row = _row(days_ago=17)
    obs = _reconcile(row, [], NOW)
    assert obs == Observation(duration_days=17, event=False)


def test_reconcile_moved_out_wins_over_a_conflicting_still_together_report():
    # One party says they moved out, the other hasn't reported (or reported
    # still_together) — the relationship genuinely ended, so it's an event.
    row = _row(days_ago=40)
    obs = _reconcile(row, [_feedback("moved_out", 20), _feedback("still_together", 40)], NOW)
    assert obs == Observation(duration_days=20, event=True)
