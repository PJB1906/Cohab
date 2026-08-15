"""Template-based explanations — COHAB_MATCHING_SPEC.md §10.

Explanations are not computed separately; they render the per-attribute
directional scores already in the breakdown (PRD §6.4). Each card is built from
the **viewer's** direction — for viewer A, an attribute's score is `sim_a`, so
the copy states how well the candidate suits A ("…which suits you").

A card shows the three highest-scoring agreements (≥ 0.8) and the single lowest
divergence (< 0.5) — never only the positives (spec §10). Copy is provided for
the attributes the spec lists; others are omitted (a real product would add the
missing copy). A renderer returns None when it cannot state the difference
plainly, and that attribute is skipped rather than guessed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from cohab.services.matching.candidate import Candidate
from cohab.services.matching.scoring import MatchResult

AGREEMENT_THRESHOLD = 0.8  # spec §10
DIVERGENCE_THRESHOLD = 0.5  # spec §10
MAX_AGREEMENTS = 3


@dataclass(frozen=True)
class Card:
    attribute: str  # weight-vector key
    kind: str  # 'agreement' | 'divergence'
    text: str
    score: float


@dataclass(frozen=True)
class Explanation:
    agreements: list[Card]
    divergence: Card | None


# A renderer reads the viewer (a) and candidate (b) answers and returns copy.
Renderer = Callable[[Candidate, Candidate], "str | None"]


def _prettify(tag: str) -> str:
    return tag.replace("_", " ")


# --- value → label maps ----------------------------------------------------

_SLEEP_BOTH = {
    "early": "early risers", "regular": "on a regular schedule",
    "night_owl": "night owls", "varies": "flexible sleepers",
}
_SLEEP_ONE = {
    "early": "an early riser", "regular": "on a regular schedule",
    "night_owl": "a night owl", "varies": "an irregular sleeper",
}
_CLEAN = {"very_tidy": "very tidy", "moderate": "moderately tidy", "relaxed": "relaxed"}
_COST_BOTH = {
    "equal": "equally", "by_room": "by room size",
    "by_use": "by what each of you uses", "flexible": "flexibly",
}
_COST_ONE = {
    "equal": "everything equally", "by_room": "by room size",
    "by_use": "by usage", "flexible": "flexibly",
}
_SHARING_OTHER = {
    "communal": "is happy to share things", "ask_first": "asks before borrowing things",
    "separate": "keeps their things separate",
}
_SHARING_SELF = {
    "communal": "treat the flat as communal", "ask_first": "like to ask before borrowing",
    "separate": "keep your things separate",
}
_SHARING_OTHER_DIV = {
    "communal": "treats the flat as communal", "ask_first": "likes to ask first",
    "separate": "keeps their things separate",
}
_NOISE_OTHER = {
    "quiet": "keeps things quiet at home", "moderate": "keeps a normal noise level",
    "loud": "is lively at home",
}
_GUEST_OTHER = {
    "rarely": "rarely has guests over", "occasionally": "has guests over now and then",
    "often": "has guests over often", "partner_regular": "has a partner stay over regularly",
}
_GUEST_DIV = {
    "occasionally": "has guests over now and then", "often": "has guests over most weeks",
    "partner_regular": "has a partner stay over regularly",
}
_PAY_OTHER = {"early": "pays rent early", "on_time": "pays rent on time"}
_PAY_DIV = {
    "needs_grace": "sometimes needs a few days on rent",
    "needs_reminding": "would rather be reminded about rent",
}
_SOC_BOTH = {
    "friend": "a flatmate you'd spend time with",
    "friendly": "a friendly but independent household",
    "independent": "a polite, independent household",
}
_SOC_OTHER = {
    "friend": "would like the same",
    "friendly": "wants something friendly but independent",
    "independent": "would rather keep to themselves",
}
_LIFE = {
    "coursework": "focused on coursework", "exam_prep": "preparing for exams",
    "job": "working", "building": "building something of your own", "research": "doing research",
}
_DIET = {
    "veg": "vegetarian", "nonveg": "non-vegetarian", "eggetarian": "eggetarian",
    "vegan": "vegan", "jain": "Jain",
}


def _both(field: str, labels: dict[str, str], template: str) -> Renderer:
    """Similarity agreement: both share the value (given the ≥0.8 threshold)."""
    def render(a: Candidate, b: Candidate) -> str | None:
        label = labels.get(a.answer(field))
        return template.format(label=label) if label else None
    return render


def _other(field: str, labels: dict[str, str], template: str) -> Renderer:
    """Tolerance/absolute agreement: framed by the candidate's (B's) value."""
    def render(a: Candidate, b: Candidate) -> str | None:
        label = labels.get(b.answer(field))
        return template.format(name=b.name, label=label) if label else None
    return render


# --- agreement renderers (spec §10) ----------------------------------------

AGREEMENT_RENDERERS: dict[str, Renderer] = {
    "sleep_schedule": _both("sleep_schedule", _SLEEP_BOTH, "You're both {label}."),
    "cleanliness_level": _both("cleanliness_level", _CLEAN, "You both keep things {label}."),
    "cost_split_preference": _both("cost_split_preference", _COST_BOTH,
                                   "You'd both split rent and bills {label}."),
    "sociability": _both("sociability", _SOC_BOTH, "You're both looking for {label}."),
    "life_stage": _both("life_stage", _LIFE, "You're both {label}."),
    "sharing_norm": _other("sharing_norm", _SHARING_OTHER, "{name} {label}, which suits you."),
    "noise": _other("noise_behaviour", _NOISE_OTHER, "{name} {label}, which suits you."),
    "guests": _other("guest_frequency", _GUEST_OTHER, "{name} {label}, which suits you."),
    "payment_reliability": _other("payment_reliability", _PAY_OTHER, "{name} {label}."),
}


def _interests_agreement(a: Candidate, b: Candidate) -> str | None:
    shared = [t for t in (a.answer("interests") or []) if t in set(b.answer("interests") or [])]
    if not shared:
        return None
    tags = [_prettify(t) for t in shared[:2]]
    joined = " and ".join(tags)
    return f"You both mentioned {joined}."


def _notes_agreement(a: Candidate, b: Candidate) -> str | None:
    return "Your descriptions of what you're looking for line up closely."


AGREEMENT_RENDERERS["interests"] = _interests_agreement
AGREEMENT_RENDERERS["lifestyle_notes"] = _notes_agreement


# --- divergence renderers (spec §10) ---------------------------------------

def _sleep_div(a: Candidate, b: Candidate) -> str | None:
    sa, sb = _SLEEP_ONE.get(a.answer("sleep_schedule")), _SLEEP_ONE.get(b.answer("sleep_schedule"))
    return f"You're {sa} and {b.name} is {sb}." if sa and sb else None


def _cleanliness_div(a: Candidate, b: Candidate) -> str | None:
    sa, sb = _CLEAN.get(a.answer("cleanliness_level")), _CLEAN.get(b.answer("cleanliness_level"))
    return f"You keep things {sa}; {b.name} keeps them {sb}. Worth discussing." if sa and sb else None


def _cost_div(a: Candidate, b: Candidate) -> str | None:
    sa = _COST_ONE.get(a.answer("cost_split_preference"))
    sb = _COST_ONE.get(b.answer("cost_split_preference"))
    return f"You'd split {sa}; {b.name} would split {sb}. Worth discussing." if sa and sb else None


def _sharing_div(a: Candidate, b: Candidate) -> str | None:
    sa = _SHARING_SELF.get(a.answer("sharing_norm"))
    sb = _SHARING_OTHER_DIV.get(b.answer("sharing_norm"))
    return f"You {sa}; {b.name} {sb}. Worth discussing." if sa and sb else None


def _guests_div(a: Candidate, b: Candidate) -> str | None:
    sb = _GUEST_DIV.get(b.answer("guest_frequency"))
    return f"{b.name} {sb} — you'd prefer a quieter home. Worth discussing." if sb else None


def _payment_div(a: Candidate, b: Candidate) -> str | None:
    sb = _PAY_DIV.get(b.answer("payment_reliability"))
    return f"{b.name} {sb}." if sb else None


def _sociability_div(a: Candidate, b: Candidate) -> str | None:
    sa = _SOC_BOTH.get(a.answer("sociability"))
    sb = _SOC_OTHER.get(b.answer("sociability"))
    return f"You're looking for {sa}; {b.name} {sb}." if sa and sb else None


def _diet_div(a: Candidate, b: Candidate) -> str | None:
    sa, sb = _DIET.get(a.answer("diet")), _DIET.get(b.answer("diet"))
    return f"You're {sa} and {b.name} is {sb}." if sa and sb else None


DIVERGENCE_RENDERERS: dict[str, Renderer] = {
    "sleep_schedule": _sleep_div,
    "cleanliness_level": _cleanliness_div,
    "cost_split_preference": _cost_div,
    "sharing_norm": _sharing_div,
    "guests": _guests_div,
    "payment_reliability": _payment_div,
    "sociability": _sociability_div,
    "diet": _diet_div,
}


def build_explanation(subject: Candidate, candidate: Candidate, result: MatchResult) -> Explanation:
    """Cards for `subject` viewing `candidate`, from `subject`'s direction."""
    scores = {name: cell["sim_a"] for name, cell in result.breakdown.items()}

    # Agreements: highest-scoring templated attributes at or above threshold.
    agreements: list[Card] = []
    for name, score in sorted(scores.items(), key=lambda kv: kv[1], reverse=True):
        if score < AGREEMENT_THRESHOLD or name not in AGREEMENT_RENDERERS:
            continue
        text = AGREEMENT_RENDERERS[name](subject, candidate)
        if text:
            agreements.append(Card(name, "agreement", text, score))
        if len(agreements) == MAX_AGREEMENTS:
            break

    # Divergence: the single lowest templated attribute below threshold.
    divergence: Card | None = None
    for name, score in sorted(scores.items(), key=lambda kv: kv[1]):
        if score >= DIVERGENCE_THRESHOLD or name not in DIVERGENCE_RENDERERS:
            continue
        text = DIVERGENCE_RENDERERS[name](subject, candidate)
        if text:
            divergence = Card(name, "divergence", text, score)
            break

    return Explanation(agreements=agreements, divergence=divergence)
