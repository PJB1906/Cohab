"""Regenerate every v2 result from raw data (Cohab v2 plan W6: `make reproduce`).

    python -m cohab.analysis.reproduce                    # real study data + all simulations
    python -m cohab.analysis.reproduce --source dryrun    # the synthetic dry run instead
    python -m cohab.analysis.reproduce --quick            # small settings, for CI / smoke tests

Writes one JSON per analysis to docs/results/ (plus figures when matplotlib is
installed) and the same payloads to `analysis_run`, each tagged with its data
source. Fixed seeds throughout: two runs on the same inputs produce the same
numbers.

Publishing a fitted weight set and calibration is a separate, explicit step
(`--publish`), allowed only for real data at tier A or B.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from cohab.analysis import calibration, fairness, fitting, pair_analysis, power, reliability, simulation, stability, taste_sim, transfer
from cohab.analysis.simulate_raters import simulate_pairs, simulate_raters
from cohab.analysis.weights import EXPERT, EXPERT_STUDY, full_weight_set
from cohab.services.matching.population import synthetic_candidates
from cohab.services.matching.vectorised import Population
from cohab.services.study.export import PairRecord, RaterRecord
from cohab.services.study.instrument import STUDY_ATTRIBUTES

REPO = Path(__file__).resolve().parents[3]
DEFAULT_OUT = REPO / "docs" / "results"
SPEED_DATING = REPO / "data" / "public" / "speed_dating.csv"

# Gate 2 tiers (plan "If real data does not arrive"). The rater count sets
# the tier; complete roommate pairs are additionally required for tier A,
# and the pair analysis reports its own n regardless.
TIER_RULES = {"A": {"raters": 40, "pairs": 30}, "B": {"raters": 20}, "C": {"raters": 8}}


def decide_tier(n_raters: int, n_pairs: int) -> str:
    if n_raters >= 40 and n_pairs >= 30:
        return "A"
    if n_raters >= 20:
        return "B"
    if n_raters >= 8:
        return "C"
    return "D"


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True, timeout=5).strip()
    except Exception:  # noqa: BLE001
        return None


def _hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


class Sink:
    def __init__(self, out: Path, provenance: dict, write_db: bool) -> None:
        self.out = out
        self.provenance = provenance
        self.write_db = write_db
        self.results: dict[str, dict] = {}
        out.mkdir(parents=True, exist_ok=True)

    def put(self, kind: str, data_source: str, payload: dict) -> None:
        payload = json.loads(json.dumps(payload, default=_jsonable))
        self.results[kind] = {"data_source": data_source, "payload": payload}
        (self.out / f"{kind}.json").write_text(
            json.dumps({"kind": kind, "data_source": data_source, "provenance": self.provenance, "payload": payload}, indent=2),
            encoding="utf-8",
        )
        print(f"  wrote {kind} [{data_source}]", flush=True)


def _jsonable(o):
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.bool_,)):
        return bool(o)
    raise TypeError(type(o))


# --- study data --------------------------------------------------------------


def load_study(source: str) -> tuple[list[RaterRecord], list[PairRecord], str]:
    if source == "dryrun-memory":
        from cohab.analysis.dryrun_seed import DRYRUN_SEED, dryrun_truth

        return (
            simulate_raters(40, dryrun_truth(), seed=DRYRUN_SEED),
            simulate_pairs(30, EXPERT, signal=5.0, self_inflation=0.3, seed=DRYRUN_SEED),
            "dryrun",
        )
    from cohab.db import SessionLocal
    from cohab.services.study.export import load_pairs, load_raters

    with SessionLocal() as session:
        if source == "dryrun":
            raters = [r for r in load_raters(session, include_synthetic=True) if r.is_synthetic]
            pairs = [p for p in load_pairs(session, include_synthetic=True) if p.is_synthetic]
            return raters, pairs, "dryrun"
        return load_raters(session), load_pairs(session), "real"


def analyse_lab(raters: list[RaterRecord], tier: str, quick: bool) -> dict:
    kept, excluded = reliability.apply_exclusions([r for r in raters if r.trials])
    out: dict = {
        "n_raters_with_data": len([r for r in raters if r.trials]),
        "n_kept": len(kept),
        "exclusions": [asdict(e) for e in excluded],
        "reliability": reliability.reliability_summary(kept, n_boot=300 if quick else 2000),
    }
    if len(kept) < 8:
        out["status"] = "too_few_raters"
        return out
    d = fitting.build_choice_data(kept)
    cv = fitting.cross_validate(d, k=5, seed=0)
    out["cv"] = fitting.summarise_cv(cv, n_boot=300 if quick else 2000, seed=0)
    out["n_comparisons"] = int(len(d.y))
    out["n_no_preference"] = int(d.n_none)
    fit = fitting.fit_weights(d, cv.lam)
    boot = fitting.bootstrap_weights(d, cv.lam, n_boot=60 if quick else 500, seed=1)
    lo, hi = np.percentile(boot, [2.5, 97.5], axis=0)
    mult = fitting.bootstrap_multiplier(d, cv.lam, n_boot=40 if quick else 300, seed=2)
    out["weights"] = {
        "attributes": list(STUDY_ATTRIBUTES),
        "expert": EXPERT_STUDY.tolist(),
        "learned": fit.weights.tolist(),
        "ci_low": lo.tolist(),
        "ci_high": hi.tolist(),
        "lambda": cv.lam,
        "importance_multiplier": fit.multiplier,
        "importance_multiplier_ci": [float(np.percentile(mult, 2.5)), float(np.percentile(mult, 97.5))],
        "v1_importance_multiplier": fitting.V1_MULTIPLIER,
    }
    if tier == "B":
        w_cluster, c = fitting.fit_clusters(d, cv.lam)
        out["weights"]["cluster_fit"] = {"weights": w_cluster.tolist(), "clusters": list(fitting.CLUSTERS), "cluster_weights": c.tolist()}
    out["rank_task"] = {
        "expert_tau": _mean_ci(fitting.rank_task_taus(kept, EXPERT_STUDY, fitting.V1_MULTIPLIER)),
        "learned_tau": _mean_ci(fitting.rank_task_taus(kept, fit.weights, fit.multiplier)),
    }
    sizes = [n for n in (8, 15, 25, 35, 50) if n < len(kept)]
    out["learning_curve"] = fitting.learning_curve(d, sizes, repeats=2 if quick else 8, lam=cv.lam)
    out["calibration"] = calibration.cross_validated_calibration(kept, d, cv.lam)
    out["calibration_final_learned"] = calibration.final_calibration(kept, fit.weights, fit.multiplier)
    out["calibration_final_expert"] = calibration.final_calibration(kept, EXPERT_STUDY, fitting.V1_MULTIPLIER)
    out["_boot_samples"] = boot[: (50 if quick else 200)].tolist()
    out["status"] = "ok"
    return out


def _mean_ci(values: list[float]) -> dict:
    v = np.asarray([x for x in values if not np.isnan(x)])
    if v.size == 0:
        return {"mean": None, "ci": [None, None], "n": 0}
    rng = np.random.default_rng(0)
    boots = [rng.choice(v, size=v.size, replace=True).mean() for _ in range(1000)]
    return {"mean": float(v.mean()), "ci": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))], "n": int(v.size)}


# --- main --------------------------------------------------------------------


def run(source: str, quick: bool, out: Path, write_db: bool, publish: bool, activate_dryrun_calibration: bool) -> dict:
    t0 = time.time()
    provenance = {
        "git_commit": _git_commit(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "quick": quick,
        "source": source,
        "python": sys.version.split()[0],
    }
    sink = Sink(out, provenance, write_db)

    print("1/8 study data", flush=True)
    raters, pairs, study_source = load_study(source)
    provenance["study_input_hash"] = _hash([asdict(r) for r in raters] + [asdict(p) for p in pairs])
    kept_preview, _ = reliability.apply_exclusions([r for r in raters if r.trials])
    tier = decide_tier(len(kept_preview), len(pairs))
    sink.put(
        "tier",
        study_source,
        {"tier": tier, "raters_kept": len(kept_preview), "raters_total": len(raters), "complete_pairs": len(pairs), "rules": TIER_RULES},
    )

    print("2/8 Cohab Lab analysis", flush=True)
    lab = analyse_lab(raters, tier, quick)
    boot_samples = lab.pop("_boot_samples", None)
    sink.put("lab", study_source, lab)

    print("3/8 roommate pairs", flush=True)
    learned_full = full_weight_set(lab["weights"]["learned"]) if lab.get("status") == "ok" else None
    pairs_out = {"expert": pair_analysis.analyse_pairs(pairs, EXPERT, n_boot=300 if quick else 2000, n_perm=500 if quick else 5000)}
    if learned_full and len(pairs) >= 4:
        pairs_out["learned"] = pair_analysis.analyse_pairs(pairs, learned_full, n_boot=300 if quick else 2000, n_perm=500 if quick else 5000)
    sink.put("pairs", study_source, pairs_out)

    print("4/8 rank stability", flush=True)
    pop = Population.from_candidates(synthetic_candidates(300 if quick else 1000, seed=42, all_verified=True))
    stab = {"expert_prior": {}}
    for conc in ((50, 300) if quick else (20, 50, 100, 300, 1000)):
        samples = stability.dirichlet_prior_samples(EXPERT, 10 if quick else 30, conc, seed=conc)
        stab["expert_prior"][str(conc)] = stability.rank_stability(pop, EXPERT, samples)
    if boot_samples:
        fitted_samples = [full_weight_set(s) for s in boot_samples[: (10 if quick else 60)]]
        stab["learned_bootstrap"] = stability.rank_stability(pop, learned_full, fitted_samples)
    sink.put("rank_stability", "simulation", stab)

    print("5/8 policy simulation", flush=True)
    cfg = simulation.WorldConfig(n_agents=300 if quick else 1000, study_raters=30 if quick else 50)
    sink.put("policy_comparison", "simulation", simulation.compare_policies(cfg, runs=3 if quick else 200))
    sink.put(
        "misreporting",
        "simulation",
        {"rows": simulation.misreporting_sweep([0.0, 0.25, 0.5] if quick else [0.0, 0.1, 0.25, 0.5], runs=2 if quick else 30, n_agents=300 if quick else 600)},
    )

    print("6/8 power study", flush=True)
    curve = power.power_curve([10, 30] if quick else [10, 20, 30, 40, 60, 80], reps=2 if quick else 12, keys=["linear", "expert_true"] if quick else None)
    curve["minimum_raters_80pct"] = {s["key"]: power.minimum_raters(curve, s["key"]) for s in curve["scenarios"]}
    sink.put("power", "simulation", curve)

    print("6b taste learning", flush=True)
    sink.put("taste_learning", "simulation", taste_sim.run(n_members=20 if quick else 150, rounds=6 if quick else 12, pool=300 if quick else 500))

    print("7/8 fairness", flush=True)
    sink.put("fairness_synthetic", "simulation", fairness.audit(synthetic_candidates(400 if quick else 1500, seed=42, all_verified=True)))
    if source == "real":
        live = _live_pool()
        if live:
            sink.put("fairness_live", "real", fairness.audit(live))

    print("8/8 transfer test", flush=True)
    sink.put("transfer", "public", transfer.run(SPEED_DATING, n_boot=200 if quick else 1000))

    provenance["seconds"] = round(time.time() - t0, 1)
    (out / "manifest.json").write_text(
        json.dumps({"provenance": provenance, "kinds": {k: v["data_source"] for k, v in sink.results.items()}}, indent=2),
        encoding="utf-8",
    )
    try:
        from cohab.analysis.figures import render_all

        render_all(sink.results, out / "figures")
        print("  figures written", flush=True)
    except ImportError:
        print("  matplotlib not installed: skipping figures (pip install -r requirements-dev.txt)", flush=True)

    if write_db:
        _write_db(sink, provenance)
    if publish:
        _publish(lab, boot_samples, study_source, tier, raters)
    if activate_dryrun_calibration:
        _activate_dryrun_calibration(lab, study_source)
    print(f"done in {provenance['seconds']}s: tier {tier}, results in {out}")
    return {"tier": tier, "results": sink.results, "provenance": provenance}


def _live_pool():
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from cohab.db import SessionLocal
    from cohab.models import User
    from cohab.services.matching.candidate import Candidate

    with SessionLocal() as session:
        users = session.scalars(
            select(User).options(selectinload(User.preference_profile), selectinload(User.attribute_weights), selectinload(User.listing))
        ).all()
        return [
            Candidate.from_orm(u, u.preference_profile, u.listing)
            for u in users
            if u.preference_profile is not None and u.verification_status == "verified" and u.account_status == "active"
        ]


def _write_db(sink: Sink, provenance: dict) -> None:
    from cohab.db import SessionLocal
    from cohab.models import AnalysisRun

    with SessionLocal() as session:
        for kind, r in sink.results.items():
            session.add(AnalysisRun(kind=kind, data_source=r["data_source"], provenance=provenance, payload=r["payload"]))
        session.commit()
    print(f"  stored {len(sink.results)} analysis_run rows")


def _next_calibration_version(session) -> int:
    from sqlalchemy import func, select

    from cohab.models import CalibrationModel

    return (session.scalar(select(func.max(CalibrationModel.version))) or 0) + 1


def _publish(lab: dict, boot_samples, study_source: str, tier: str, raters) -> None:
    from sqlalchemy import update

    from cohab.db import SessionLocal
    from cohab.models import CalibrationModel, WeightSetUncertainty
    from cohab.services.matching.weight_sets import publish as publish_weights

    if study_source != "real" or tier not in ("A", "B") or lab.get("status") != "ok":
        print(f"  --publish refused: needs real data at tier A or B (have {study_source}, tier {tier})")
        return
    w17 = lab["weights"]["cluster_fit"]["weights"] if tier == "B" else lab["weights"]["learned"]
    with SessionLocal() as session:
        ws = publish_weights(session, full_weight_set(w17), source="fitted")
        session.add(WeightSetUncertainty(weight_set_id=ws.id, method="bootstrap_raters", samples=[full_weight_set(s) for s in boot_samples]))
        cal = lab["calibration_final_learned"]
        session.execute(update(CalibrationModel).where(CalibrationModel.is_active.is_(True)).values(is_active=False))
        session.add(
            CalibrationModel(
                version=_next_calibration_version(session),
                target="would_message",
                weight_set_id=ws.id,
                data_source="real",
                knots=cal["knots"],
                metrics=lab["calibration"]["calibrated"],
                is_active=True,
                published_at=datetime.now(timezone.utc),
            )
        )
        session.commit()
        print(f"  published weight_set v{ws.version} (fitted) and an active calibration")


def _activate_dryrun_calibration(lab: dict, study_source: str) -> None:
    """Demo only: attach the dry run's calibration (fitted on scores under
    the *active* expert weights) so the match screen can show tiers, each
    labelled as coming from a synthetic dry run."""
    from sqlalchemy import select, update

    from cohab.db import SessionLocal
    from cohab.models import CalibrationModel, WeightSet

    if study_source != "dryrun" or lab.get("status") != "ok":
        print("  --activate-dryrun-calibration needs --source dryrun")
        return
    with SessionLocal() as session:
        active = session.scalar(select(WeightSet).where(WeightSet.is_active.is_(True)))
        session.execute(update(CalibrationModel).where(CalibrationModel.is_active.is_(True)).values(is_active=False))
        session.add(
            CalibrationModel(
                version=_next_calibration_version(session),
                target="would_message",
                weight_set_id=active.id,
                data_source="dryrun",
                knots=lab["calibration_final_expert"]["knots"],
                metrics=lab["calibration"]["calibrated"],
                is_active=True,
                published_at=datetime.now(timezone.utc),
            )
        )
        session.commit()
        print(f"  activated DRY-RUN calibration for weight_set v{active.version}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Regenerate every Cohab v2 result")
    ap.add_argument("--source", choices=["real", "dryrun", "dryrun-memory"], default="real")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--no-db-write", action="store_true")
    ap.add_argument("--publish", action="store_true", help="publish fitted weights + calibration (real data, tier A/B only)")
    ap.add_argument("--activate-dryrun-calibration", action="store_true", help="demo only")
    args = ap.parse_args()
    run(args.source, args.quick, args.out, not args.no_db_write, args.publish, args.activate_dryrun_calibration)


if __name__ == "__main__":
    main()
