import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from schedule import ORDER, PHASE, compute, critical_path

sched, END = compute()
CP = set(critical_path(sched))

PHASE_BAR = {
    "Requirement":    "#4A90D9",
    "Design":         "#2FA88A",
    "Implementation": "#E8A33D",
    "Testing":        "#9B6FC7",
    "Deployment":     "#E2664F",
}
PHASE_BAND = {
    "Requirement":    ("#EAF2FB", 0, 4),
    "Design":         ("#E7F5F1", 4, 6),
    "Implementation": ("#FDF3E3", 6, 11),
    "Testing":        ("#F2EBF9", 11, 14),
    "Deployment":     ("#FBEBE8", 14, 16),
}

fig, ax = plt.subplots(figsize=(12.4, 6.4))

# Phase background bands
for name, (colour, start, end) in PHASE_BAND.items():
    ax.axvspan(start, end, color=colour, zorder=0)

for row, aid in enumerate(ORDER):
    v = sched[aid]
    y = len(ORDER) - row - 1
    phase = PHASE[aid]
    is_crit = aid in CP
    ax.barh(
        y, v["dur"], left=v["es"], height=0.55,
        color=PHASE_BAR[phase],
        edgecolor="#B23B2E" if is_crit else "#5A5A5A",
        linewidth=1.8 if is_crit else 0.7,
        zorder=3,
    )
    # Slack float shown as a hollow trailing bar
    if v["slack"] > 0:
        ax.barh(
            y, v["slack"], left=v["ef"], height=0.55,
            color="none", edgecolor="#9A9A9A",
            linewidth=0.8, linestyle=(0, (2, 2)), zorder=2,
        )

ax.set_yticks(range(len(ORDER)))
ax.set_yticklabels([f"{aid}: {sched[aid]['label']}" for aid in reversed(ORDER)],
                   fontsize=9)
ax.set_xticks(range(0, END + 1))
ax.set_xticklabels([""] + [f"W{i}" for i in range(1, END + 1)], fontsize=8.5)
ax.set_xlim(0, END)
ax.set_ylim(-0.7, len(ORDER) - 0.3)
ax.set_xlabel("Even Trimester 2026\u20132027 (Weeks)", fontsize=10, labelpad=8)
ax.set_title("Gantt Chart \u2013 Project Schedule (Cohab)",
             fontsize=12, fontweight="bold", pad=12)

ax.grid(axis="x", color="white", linewidth=0.9, zorder=1)
ax.set_axisbelow(False)
for spine in ("top", "right"):
    ax.spines[spine].set_visible(False)
ax.tick_params(axis="y", length=0)

legend = [Patch(facecolor=c, edgecolor="#5A5A5A", label=f"{n} Phase")
          for n, c in PHASE_BAR.items()]
legend.append(Patch(facecolor="white", edgecolor="#B23B2E", linewidth=1.8,
                    label="On Critical Path"))
legend.append(Patch(facecolor="white", edgecolor="#9A9A9A",
                    linestyle="--", label="Available Slack"))
ax.legend(handles=legend, loc="upper center", bbox_to_anchor=(0.5, -0.13),
          ncol=4, fontsize=8.5, frameon=False)

plt.tight_layout()
plt.savefig("../images/image15.png", dpi=200, bbox_inches="tight",
            facecolor="white")
print(f"Gantt written: {END} weeks, {len(ORDER)} activities, "
      f"{len(CP)} on critical path")
