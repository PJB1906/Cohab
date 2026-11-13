"""Report figures from reproduce.py's results (matplotlib; dev dependency).

Every figure carries its data-source tag in the corner, so a dry-run or
simulated chart cannot be pasted into the report as if it were evidence.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

INK = "#1f2a37"
MUTED = "#6b7280"
EXPERT_C = "#9aa5b1"
LEARNED_C = "#2f6fdf"
ACCENT = "#d9822b"

SOURCE_LABEL = {
    "real": "Real study data",
    "dryrun": "SYNTHETIC DRY RUN — not evidence",
    "simulation": "SIMULATION — assumptions stated in report",
    "public": "Public dataset (speed dating)",
}


def _tag(fig, source: str) -> None:
    fig.text(0.99, 0.01, SOURCE_LABEL.get(source, source), ha="right", va="bottom", fontsize=8, color=ACCENT if source != "real" else MUTED)


def _save(fig, path: Path) -> None:
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path, dpi=160)
    plt.close(fig)


def weights_forest(lab: dict, source: str, path: Path) -> None:
    w = lab["weights"]
    names = w["attributes"]
    order = np.argsort(w["expert"])
    y = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(7, 6))
    learned = np.array(w["learned"])[order]
    lo, hi = np.array(w["ci_low"])[order], np.array(w["ci_high"])[order]
    ax.errorbar(learned, y + 0.15, xerr=[learned - lo, hi - learned], fmt="o", color=LEARNED_C, label="Learned (95% rater bootstrap)", capsize=2)
    ax.scatter(np.array(w["expert"])[order], y - 0.15, marker="s", color=EXPERT_C, label="Expert v2", zorder=3)
    ax.set_yticks(y, [names[i].replace("_", " ") for i in order])
    ax.set_xlabel("Weight (17 study attributes, sums to 1)")
    ax.legend(loc="lower right", frameon=False)
    ax.set_title("Attribute weights: learned vs expert", loc="left")
    _tag(fig, source)
    _save(fig, path)


def accuracy_ladder(lab: dict, rel: dict, source: str, path: Path) -> None:
    sc = lab["cv"]["scorers"]
    keys = ["random", "single_attribute", "uniform", "expert", "learned"]
    labels = ["Random", "Best single", "Uniform", "Expert", "Learned"]
    acc = [sc[k]["accuracy"] for k in keys]
    err = np.array([[sc[k]["accuracy"] - sc[k]["accuracy_ci"][0], sc[k]["accuracy_ci"][1] - sc[k]["accuracy"]] for k in keys]).T
    fig, ax = plt.subplots(figsize=(7, 3.6))
    colors = [EXPERT_C] * 3 + [INK, LEARNED_C]
    ax.bar(labels, acc, yerr=err, color=colors, capsize=3)
    if rel.get("noise_ceiling_accuracy"):
        ax.axhline(rel["noise_ceiling_accuracy"], color=ACCENT, ls="--", lw=1)
        ax.text(4.4, rel["noise_ceiling_accuracy"], " noise ceiling", va="center", color=ACCENT, fontsize=8)
    ax.set_ylim(0.4, 1.0)
    ax.set_ylabel("Held-out pairwise accuracy")
    ax.set_title("Accuracy ladder (grouped CV by rater)", loc="left")
    _tag(fig, source)
    _save(fig, path)


def reliability_diagram(cal: dict, source: str, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(4.6, 4.6))
    ax.plot([0, 1], [0, 1], color=MUTED, lw=1, ls=":")
    for key, color, label in (("raw_score_as_probability", EXPERT_C, "Raw score"), ("calibrated", LEARNED_C, "Isotonic")):
        bins = cal[key]["bins"]
        ax.plot([b["mean_p"] for b in bins], [b["observed"] for b in bins], "o-", color=color, label=f"{label} (ECE {cal[key]['ece']:.3f})")
    ax.set_xlabel("Predicted P(would message)")
    ax.set_ylabel("Observed share")
    ax.legend(frameon=False, loc="upper left")
    ax.set_title("Reliability (out-of-fold)", loc="left")
    _tag(fig, source)
    _save(fig, path)


def power_curves(pw: dict, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    for s in pw["scenarios"]:
        xs = [r["n_raters"] for r in s["rows"]]
        ax.plot(xs, [r["p_learned_reliably_better"] for r in s["rows"]], "o-", label=s["label"], lw=1.5)
    ax.axhline(0.8, color=MUTED, ls=":", lw=1)
    ax.set_xlabel("Raters")
    ax.set_ylabel("P(learned reliably beats expert)")
    ax.set_ylim(-0.02, 1.02)
    ax.legend(fontsize=7, frameon=False)
    ax.set_title("Power: how many raters the study needs", loc="left")
    _tag(fig, "simulation")
    _save(fig, path)


def policy_bars(pc: dict, path: Path) -> None:
    t = pc["table"]
    pols = ["random", "expert", "learned", "oracle"]
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.4))
    for ax, metric, label in zip(axes, ("welfare_per_agent", "match_rate", "top10_overlap_with_oracle"), ("Welfare per agent", "Match rate", "Top-10 overlap with oracle")):
        means = [t[p][metric]["mean"] for p in pols]
        err = np.array([[t[p][metric]["mean"] - t[p][metric]["ci95"][0], t[p][metric]["ci95"][1] - t[p][metric]["mean"]] for p in pols]).T
        ax.bar(pols, means, yerr=err, color=[EXPERT_C, INK, LEARNED_C, ACCENT], capsize=3)
        ax.set_title(label, fontsize=10)
    fig.suptitle(f"Policy comparison, {pc['runs']} seeded runs (mean ± 95% CI)", x=0.01, ha="left")
    _tag(fig, "simulation")
    _save(fig, path)


def permutation_hist(pairs: dict, source: str, path: Path) -> None:
    perm = pairs["permutation"]
    edges = perm["histogram_edges"]
    fig, ax = plt.subplots(figsize=(6, 3.4))
    ax.stairs(perm["histogram"], edges, fill=True, color=EXPERT_C, label="Same people, randomly re-paired")
    ax.axvline(perm["real_mean"], color=LEARNED_C, lw=2, label=f"Real pairs (p = {perm['p_value_one_sided']:.3f})")
    ax.set_xlabel("Mean Cohab score")
    ax.legend(frameon=False, fontsize=8)
    ax.set_title("Do real roommates score higher than random pairings?", loc="left")
    _tag(fig, source)
    _save(fig, path)


def fairness_ratios(fair: dict, path: Path) -> None:
    rows = []
    for grouping, g in fair["groupings"].items():
        for r in g["table"]:
            rows.append((f"{grouping}: {r['group']}", r["exposure_ratio"], r["pass_rate_ratio"], r["flag"]))
    fig, ax = plt.subplots(figsize=(7, 0.32 * len(rows) + 1))
    y = np.arange(len(rows))
    ax.axvspan(*fair["parity_band"], color="#e5f4e4")
    ax.scatter([r[1] for r in rows], y, color=LEARNED_C, label="Exposure ratio", zorder=3)
    ax.scatter([r[2] for r in rows], y, color=INK, marker="x", label="Stage 1 pass-rate ratio", zorder=3)
    ax.set_yticks(y, [r[0] for r in rows], fontsize=8)
    ax.axvline(1, color=MUTED, lw=1)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    ax.set_title("Fairness: group ratio to overall (band 0.8–1.25)", loc="left")
    _tag(fig, "simulation")
    _save(fig, path)


def render_all(results: dict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    lab = results.get("lab")
    if lab and lab["payload"].get("status") == "ok":
        src = lab["data_source"]
        weights_forest(lab["payload"], src, out / "weights_forest.png")
        accuracy_ladder(lab["payload"], lab["payload"]["reliability"], src, out / "accuracy_ladder.png")
        reliability_diagram(lab["payload"]["calibration"], src, out / "reliability_diagram.png")
    if "power" in results:
        power_curves(results["power"]["payload"], out / "power_curves.png")
    if "policy_comparison" in results:
        policy_bars(results["policy_comparison"]["payload"], out / "policy_comparison.png")
    pairs = results.get("pairs")
    if pairs and pairs["payload"]["expert"].get("status") == "ok":
        permutation_hist(pairs["payload"]["expert"], pairs["data_source"], out / "pairs_permutation.png")
    if "fairness_synthetic" in results:
        fairness_ratios(results["fairness_synthetic"]["payload"], out / "fairness_ratios.png")
