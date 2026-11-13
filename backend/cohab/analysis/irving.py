"""Irving's stable roommates algorithm, with incomplete preference lists.

SIMULATION ONLY. Cohab's product principle is "the system ranks and
explains, it never assigns". Irving's algorithm assigns; it appears in the
policy comparison purely as the classical reference point for what a
centrally optimal allocation would achieve (deck slide 27).

Phase 1: everyone proposes down their list; a holder keeps the best proposal
and rejects the rest; lists are truncated after the held proposal.
Phase 2: repeatedly find and eliminate rotations until every list has one
entry (a stable matching) or some list empties (no stable matching exists).

Reference: R. W. Irving (1985), "An efficient algorithm for the stable
roommates problem", J. Algorithms 6(4), 577-595. Incomplete lists are
handled by making acceptability mutual before Phase 1.
"""

from __future__ import annotations

from typing import Sequence


def stable_roommates(prefs: Sequence[Sequence[int]]) -> dict[int, int] | None:
    """`prefs[i]` lists acceptable partners for i, best first. Returns a
    stable matching as {i: partner} for everyone matched (people with empty
    reduced lists stay unmatched), or None when no stable matching exists."""
    n = len(prefs)
    # Mutual acceptability.
    acceptable = [set(p) for p in prefs]
    lists = [[j for j in prefs[i] if i in acceptable[j] and j != i] for i in range(n)]
    rank = [{j: r for r, j in enumerate(lists[i])} for i in range(n)]
    alive = [set(lst) for lst in lists]

    def remove(i: int, j: int) -> None:
        alive[i].discard(j)
        alive[j].discard(i)

    def first(i: int) -> int | None:
        for j in lists[i]:
            if j in alive[i]:
                return j
        return None

    def second(i: int) -> int | None:
        seen = 0
        for j in lists[i]:
            if j in alive[i]:
                seen += 1
                if seen == 2:
                    return j
        return None

    def last(i: int) -> int | None:
        for j in reversed(lists[i]):
            if j in alive[i]:
                return j
        return None

    # Phase 1.
    holds: dict[int, int] = {}  # holder -> proposer held
    free = list(range(n))
    while free:
        i = free.pop()
        while True:
            j = first(i)
            if j is None:
                break  # i exhausted their list: unmatched
            current = holds.get(j)
            if current is None or rank[j][i] < rank[j][current]:
                holds[j] = i
                # j rejects everyone worse than i.
                for k in [k for k in lists[j] if k in alive[j] and rank[j][k] > rank[j][i]]:
                    remove(j, k)
                if current is not None:
                    free.append(current)
                break
            remove(i, j)

    # Phase 2: rotation elimination.
    while True:
        p = next((i for i in range(n) if len(alive[i]) > 1), None)
        if p is None:
            break
        ps, qs = [p], []
        seen_at: dict[int, int] = {p: 0}
        while True:
            q = second(ps[-1])
            if q is None:
                return None
            qs.append(q)
            nxt = last(q)
            if nxt is None:
                return None
            if nxt in seen_at:
                start = seen_at[nxt]
                ps, qs = ps[start:], qs[start:]
                break
            seen_at[nxt] = len(ps)
            ps.append(nxt)
        # Eliminate: p_k now proposes to q_k = second(p_k), so q_k rejects
        # everyone it ranks below p_k (including its old holder p_{k+1}).
        nonempty_before = {i for i in range(n) if alive[i]}
        for k in range(len(ps)):
            q = qs[k]
            new_holder = ps[k]
            for x in [x for x in lists[q] if x in alive[q] and rank[q][x] > rank[q][new_holder]]:
                remove(q, x)
        if any(not alive[i] for i in nonempty_before):
            return None  # a list emptied during Phase 2: no stable matching

    matching: dict[int, int] = {}
    for i in range(n):
        if len(alive[i]) == 1:
            j = next(iter(alive[i]))
            if alive[j] == {i}:
                matching[i] = j
    return matching


def is_stable(prefs: Sequence[Sequence[int]], matching: dict[int, int]) -> bool:
    """No blocking pair: two mutually acceptable people who each prefer the
    other to their current partner (or are unmatched)."""
    rank = [{j: r for r, j in enumerate(p)} for p in prefs]
    n = len(prefs)
    for i in range(n):
        for j in prefs[i]:
            if j == i or i not in rank[j]:
                continue
            if matching.get(i) == j:
                continue
            i_prefers = i not in matching or rank[i][j] < rank[i][matching[i]]
            j_prefers = j not in matching or rank[j][i] < rank[j][matching[j]]
            if i_prefers and j_prefers:
                return False
    return True
