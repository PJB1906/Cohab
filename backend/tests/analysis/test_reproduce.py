"""`make reproduce` in quick mode, in memory: every analysis runs, every
output is tagged, and two runs give identical numbers."""

from __future__ import annotations

import json

from cohab.analysis.reproduce import decide_tier, run

EXPECTED = {
    "tier": "dryrun", "lab": "dryrun", "pairs": "dryrun", "rank_stability": "simulation",
    "policy_comparison": "simulation", "misreporting": "simulation", "power": "simulation",
    "fairness_synthetic": "simulation", "transfer": "public",
}


def test_tiers() -> None:
    assert decide_tier(45, 35) == "A"
    assert decide_tier(25, 16) == "B"
    assert decide_tier(45, 3) == "B"
    assert decide_tier(10, 0) == "C"
    assert decide_tier(10, 40) == "C"
    assert decide_tier(3, 0) == "D"


def test_quick_pipeline_is_complete_tagged_and_deterministic(tmp_path) -> None:
    a = run("dryrun-memory", quick=True, out=tmp_path / "a", write_db=False, publish=False, activate_dryrun_calibration=False)
    assert {k: v["data_source"] for k, v in a["results"].items()} == EXPECTED
    assert a["results"]["lab"]["payload"]["status"] == "ok"
    manifest = json.loads((tmp_path / "a" / "manifest.json").read_text())
    assert manifest["kinds"] == EXPECTED
    for kind in EXPECTED:
        saved = json.loads((tmp_path / "a" / f"{kind}.json").read_text())
        assert saved["data_source"] == EXPECTED[kind]
    b = run("dryrun-memory", quick=True, out=tmp_path / "b", write_db=False, publish=False, activate_dryrun_calibration=False)
    for kind in EXPECTED:
        assert a["results"][kind]["payload"] == b["results"][kind]["payload"], kind
