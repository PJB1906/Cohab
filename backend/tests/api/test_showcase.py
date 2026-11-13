"""W6 backend: match insights, calibrated tiers, evidence page, playground,
dry-run round trip and study-data deletion."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from cohab.analysis import fitting
from cohab.analysis.dryrun_seed import write_dryrun
from cohab.models import AnalysisRun, CalibrationModel, Institution, StudyRater, User, WeightSet
from cohab.services.insights import calibrate, study_score_towards, tier_for
from cohab.services.study.delete_data import delete_study_data
from cohab.services.study.export import load_pairs, load_raters
from tests.api.test_chat import ANSWERS, _login, _onboard


@pytest.fixture()
def asha(
    client: TestClient, db_session: Session, institution: Institution, weight_set: WeightSet, caplog: pytest.LogCaptureFixture
) -> str:
    # Independent of a demo calibration activated in the dev database.
    db_session.execute(update(CalibrationModel).values(is_active=False))
    db_session.flush()
    uid = _onboard(client, institution, caplog, name="Asha", email_local="asha")
    _login(client, f"asha@{institution.email_domain}")
    return uid


def test_insights_explains_pool_and_writes_nothing(client: TestClient, db_session: Session, asha: str) -> None:
    from cohab.models import MatchExposure, MatchScore

    before = (
        db_session.scalar(select(func.count()).select_from(MatchScore)),
        db_session.scalar(select(func.count()).select_from(MatchExposure)),
    )
    resp = client.get("/matches/insights")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    pool = body["pool"]
    assert pool["considered"] >= pool["eligible"] >= 0
    labels = {r["reason"] for r in pool["excluded_by_reason"]}
    assert not labels & {"not_verified_or_active", "blocked", "already_decided"}  # never revealed
    assert sum(r["count"] for r in pool["excluded_by_reason"]) <= pool["considered"] - pool["eligible"]
    assert body["calibration"] == {"active": False, "version": None, "data_source": None, "target": None}
    assert body["tie_hint"]["method"] in ("dirichlet_prior", "bootstrap_raters")
    after = (
        db_session.scalar(select(func.count()).select_from(MatchScore)),
        db_session.scalar(select(func.count()).select_from(MatchExposure)),
    )
    assert after == before


def test_budget_suggestion_is_exact(client: TestClient, db_session: Session, asha: str) -> None:
    """A narrow budget excludes most of the seeded pool; the suggestion's
    'adds' must equal the real change in the eligible count."""
    client.put(
        "/profile",
        json={
            "city": "Bangalore", "budget_min": 6000, "budget_max": 6500, "move_in_date": "2026-09-01",
            "gender_preference": "any", "questionnaire": ANSWERS, "important_attributes": [],
        },
    )
    body = client.get("/matches/insights").json()
    budget = next((s for s in body["pool"]["suggestions"] if s["kind"] == "budget"), None)
    if budget is None:
        pytest.skip("seeded pool has nobody just above this budget")
    step = int(budget["label"].split("₹")[1].replace(",", "").split()[0])
    before = body["pool"]["eligible"]
    client.put(
        "/profile",
        json={
            "city": "Bangalore", "budget_min": 6000, "budget_max": 6500 + step, "move_in_date": "2026-09-01",
            "gender_preference": "any", "questionnaire": ANSWERS, "important_attributes": [],
        },
    )
    assert client.get("/matches/insights").json()["pool"]["eligible"] == before + budget["adds"]


def test_tiers_appear_only_with_active_calibration(client: TestClient, db_session: Session, asha: str) -> None:
    items = client.get("/matches").json()
    assert items and all(i["confidence_tier"] is None for i in items)

    active = db_session.scalar(select(WeightSet).where(WeightSet.is_active.is_(True)))
    db_session.add(
        CalibrationModel(
            version=9001, target="would_message", weight_set_id=active.id, data_source="dryrun",
            knots={"x": [0.0, 0.6, 1.0], "y": [0.05, 0.4, 0.9]}, metrics={}, is_active=True,
            published_at=datetime.now(timezone.utc),
        )
    )
    db_session.flush()
    items = client.get("/matches").json()
    first = items[0]
    assert first["confidence_tier"] in ("strong", "good", "possible")
    assert first["calibration_source"] == "dryrun" and first["calibration_version"] == 9001
    assert 0.05 <= first["would_message_probability"] <= 0.9
    detail = client.get(f"/matches/{first['match_id']}/explanation").json()
    assert detail["confidence_tier"] is not None
    assert client.get("/matches/insights").json()["calibration"]["active"] is True


def test_calibration_helpers() -> None:
    bd = {
        "cleanliness_level": {"w_a": 0.2, "sim_a": 1.0, "w_b": 0.1, "sim_b": 0.0},
        "budget_proximity": {"w_a": 0.5, "sim_a": 0.0, "w_b": 0.5, "sim_b": 0.0},  # held out
        "guests": {"w_a": 0.2, "sim_a": 0.5, "w_b": 0.1, "sim_b": 1.0},
    }
    assert study_score_towards(bd, "a") == pytest.approx(0.75)
    assert study_score_towards(bd, "b") == pytest.approx(0.5)
    assert tier_for(0.7) == "strong" and tier_for(0.4) == "good" and tier_for(0.1) == "possible"
    assert calibrate(None, bd) is None


def test_evidence_and_playground_are_moderator_only(client: TestClient, asha: str) -> None:
    assert client.get("/evidence/summary").status_code == 403
    assert client.get("/evidence/playground").status_code == 403


def test_evidence_summary_returns_latest_per_kind(client: TestClient, db_session: Session, moderator_user) -> None:
    db_session.add(AnalysisRun(kind="power", data_source="simulation", provenance={"v": 1}, payload={"old": True}))
    db_session.flush()
    db_session.add(AnalysisRun(kind="power", data_source="simulation", provenance={"v": 2}, payload={"old": False}))
    db_session.flush()
    body = client.get("/evidence/summary").json()
    assert body["power"]["payload"] == {"old": False}
    assert body["power"]["data_source"] == "simulation"


def test_playground_client_arithmetic_matches_server(client: TestClient, moderator_user) -> None:
    """The page re-ranks in the browser from the sims this endpoint returns.
    Re-implement that arithmetic here and check it against the server."""
    pg = client.get("/evidence/playground").json()
    assert pg["data_source"] == "synthetic"
    assert len(pg["candidates"]) > 10
    from cohab.services.matching.scoring import blend, harmonic_mean

    def client_rank(weights):
        scored = []
        for c in pg["candidates"]:
            wa = blend(weights, frozenset(pg["subject_important"]))
            wb = blend(weights, frozenset(c["important"]))
            ta = sum(wa[n] for n in c["present"])
            tb = sum(wb[n] for n in c["present"])
            s_ab = sum(wa[n] / ta * c["sim_to"][n] for n in c["present"])
            s_ba = sum(wb[n] / tb * c["sim_from"][n] for n in c["present"])
            scored.append((harmonic_mean(s_ab, s_ba), c["index"]))
        return [i for _, i in sorted(scored, key=lambda t: -t[0])][:10]

    assert client_rank(pg["weights"]) == pg["server_top10"]
    tilted = dict(pg["weights"])
    tilted["sleep_schedule"] *= 6
    total = sum(tilted.values())
    tilted = {k: v / total for k, v in tilted.items()}
    server = client.post(
        "/evidence/playground/rank", json={"seed": pg["seed"], "subject": pg["subject"], "weights": tilted}
    ).json()
    # The client only has the top-25 under default weights, so compare where
    # the server's new top-10 is inside that window.
    window = {c["index"] for c in pg["candidates"]}
    if set(server["top10"]) <= window:
        assert client_rank(tilted) == server["top10"]
    assert client.post(
        "/evidence/playground/rank", json={"seed": 7, "subject": 0, "weights": {"nope": 1}}
    ).status_code == 422


def test_dryrun_roundtrip_through_tables_and_delete(db_session: Session) -> None:
    before_r = {r.rater_id for r in load_raters(db_session, include_synthetic=True)}
    before_p = {p.pair_id for p in load_pairs(db_session, include_synthetic=True)}
    write_dryrun(db_session, n_raters=6, n_pairs=5)
    assert all(not r.is_synthetic for r in load_raters(db_session))  # excluded by default
    raters = [r for r in load_raters(db_session, include_synthetic=True) if r.rater_id not in before_r]
    pairs = [p for p in load_pairs(db_session, include_synthetic=True) if p.pair_id not in before_p]
    assert len(raters) == 6 and len(pairs) == 5
    assert all(r.is_synthetic and len(r.trials) == 40 for r in raters)
    # The exported records feed the analysis unchanged.
    d = fitting.build_choice_data(raters)
    assert len(d.y) > 100
    counts = delete_study_data(db_session, synthetic_only=True)
    assert counts["raters"] >= 6 and counts["pairs"] >= 5
    assert db_session.scalar(select(func.count()).select_from(StudyRater).where(StudyRater.is_synthetic.is_(True))) == 0
