"""
Single source of truth for the Cohab project schedule.

Both the Gantt chart (Figure 12.1) and the PERT/CPM network (Figure 12.2) are
generated from ACTIVITIES below, so the two figures can never disagree again.

Time is measured in whole weeks. ES/EF/LS/LF are in "weeks elapsed since project
start", i.e. ES=0 means the activity begins at the start of Week 1.
"""

# id: (label, duration_weeks, [predecessor ids])
ACTIVITIES = {
    "A": ("Synopsis / Proposal",             2, []),
    "B": ("SRS Document",                    2, ["A"]),
    "C": ("Architecture, DFD, UML",          2, ["B"]),
    "D": ("Auth & Verification Module",      1, ["C"]),
    "E": ("Preference Module",               1, ["C"]),
    "F": ("Matching & Ranking Engine",       3, ["E"]),
    "G": ("Chat & Safety Module",            2, ["D"]),
    "H": ("Feedback & Analytics Module",     2, ["E"]),
    "I": ("Integration",                     1, ["D", "F", "G", "H"]),
    "J": ("Unit & Integration Testing",      2, ["I"]),
    "L": ("Deployment",                      1, ["I"]),
    "K": ("Pilot with Students",             1, ["J", "L"]),
    "M": ("Refinement from Pilot Feedback",  1, ["K"]),
    "N": ("Final Report & Viva",             1, ["M"]),
}

# Presentation order (top-to-bottom on the Gantt chart)
ORDER = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "L", "K", "M", "N"]

# Which phase each activity belongs to (for Gantt colouring)
PHASE = {
    "A": "Requirement", "B": "Requirement",
    "C": "Design",
    "D": "Implementation", "E": "Implementation", "F": "Implementation",
    "G": "Implementation", "H": "Implementation", "I": "Implementation",
    "J": "Testing", "K": "Testing",
    "L": "Deployment", "M": "Deployment", "N": "Deployment",
}


def successors(aid):
    return [k for k, (_, _, preds) in ACTIVITIES.items() if aid in preds]


def compute():
    """Forward and backward pass. Returns {id: dict(es, ef, ls, lf, slack)}."""
    es, ef = {}, {}

    # Forward pass (topological by repeated relaxation - graph is small)
    remaining = set(ACTIVITIES)
    while remaining:
        progressed = False
        for aid in list(remaining):
            _, dur, preds = ACTIVITIES[aid]
            if all(p in ef for p in preds):
                es[aid] = max([ef[p] for p in preds], default=0)
                ef[aid] = es[aid] + dur
                remaining.discard(aid)
                progressed = True
        if not progressed:
            raise ValueError("Cycle in activity network")

    project_end = max(ef.values())

    # Backward pass
    ls, lf = {}, {}
    remaining = set(ACTIVITIES)
    while remaining:
        progressed = False
        for aid in list(remaining):
            _, dur, _ = ACTIVITIES[aid]
            succ = successors(aid)
            if all(s in ls for s in succ):
                lf[aid] = min([ls[s] for s in succ], default=project_end)
                ls[aid] = lf[aid] - dur
                remaining.discard(aid)
                progressed = True
        if not progressed:
            raise ValueError("Cycle in activity network")

    return {
        aid: dict(
            label=ACTIVITIES[aid][0],
            dur=ACTIVITIES[aid][1],
            es=es[aid], ef=ef[aid], ls=ls[aid], lf=lf[aid],
            slack=ls[aid] - es[aid],
        )
        for aid in ACTIVITIES
    }, project_end


def critical_path(sched):
    """Longest zero-slack chain from a start node to an end node."""
    crit = {a for a, v in sched.items() if v["slack"] == 0}
    starts = [a for a in crit if not ACTIVITIES[a][2]]
    best = []

    def walk(node, path):
        nonlocal best
        succ = [s for s in successors(node)
                if s in crit and sched[s]["es"] == sched[node]["ef"]]
        if not succ:
            if len(path) > len(best):
                best = list(path)
            return
        for s in succ:
            walk(s, path + [s])

    for s in starts:
        walk(s, [s])
    return best


if __name__ == "__main__":
    sched, end = compute()
    cp = critical_path(sched)
    print(f"Project duration: {end} weeks")
    print(f"Critical path: {' -> '.join(cp)}")
    print(f"Critical path duration check: {sum(sched[a]['dur'] for a in cp)} weeks")
    print()
    hdr = f"{'ID':<3}{'Activity':<34}{'Dur':>4}{'ES':>4}{'EF':>4}{'LS':>4}{'LF':>4}{'Slack':>6}  Weeks"
    print(hdr)
    print("-" * len(hdr))
    for aid in ORDER:
        v = sched[aid]
        wk = f"W{v['es']+1}" if v["dur"] == 1 else f"W{v['es']+1}-W{v['ef']}"
        print(f"{aid:<3}{v['label']:<34}{v['dur']:>4}{v['es']:>4}{v['ef']:>4}"
              f"{v['ls']:>4}{v['lf']:>4}{v['slack']:>6}  {wk}")
