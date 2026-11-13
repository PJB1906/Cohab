"""What the studies ask and what they measure (Cohab v2 plan W2/W3).

The preference study measures one direction: given the rater's own answers,
which card would they rather live with. So each card shows only the card
person's *behaviour* (how they live), never their tolerances, and the
features are the existing directional scores S_k(rater -> card). Showing a
card's tolerances would invite the reverse question (would they put up with
me?), which the features do not encode.

Budget, interests and free text are held out of the cards: the study is about
lifestyle compatibility, and those three keep their expert weights in any
fitted weight set (docs/DECISIONS.md D-14.6).
"""

from __future__ import annotations

from cohab.seed import QUESTIONNAIRE_OPTIONS, QUESTIONNAIRE_WEIGHTS

CONSENT_VERSION = "lab-2026-11-v1"
PAIR_CONSENT_VERSION = "pairs-2026-11-v1"

# The rater answers all 21 lifestyle fields (the 18 required plus the four
# tier-2 items), so every attribute's directional score is defined.
RATER_FIELDS: tuple[str, ...] = (
    "sleep_schedule", "noise_preference", "noise_behaviour", "cleanliness_level", "chore_approach",
    "sharing_norm", "guest_frequency", "guest_tolerance", "communication_style", "payment_reliability",
    "cost_split_preference", "diet", "nonveg_cooking_tolerance", "smoking_behaviour", "smoking_tolerance",
    "alcohol_behaviour", "alcohol_tolerance", "life_stage", "daytime_presence", "home_orientation", "sociability",
)

# Fields shown on a card and varied by the design: the card person's behaviour.
CARD_FIELDS: tuple[str, ...] = (
    "cleanliness_level", "chore_approach", "sharing_norm", "sleep_schedule", "noise_behaviour",
    "guest_frequency", "payment_reliability", "cost_split_preference", "communication_style", "diet",
    "smoking_behaviour", "alcohol_behaviour", "life_stage", "daytime_presence", "home_orientation", "sociability",
)

# The 17 attributes the study can estimate (order = the weight table's order).
# `diet` (the card field) drives two of them: `diet` and `nonveg_cooking`.
STUDY_ATTRIBUTES: tuple[str, ...] = (
    "cleanliness_level", "chore_approach", "sharing_norm", "sleep_schedule", "noise", "guests",
    "payment_reliability", "cost_split_preference", "communication_style", "diet", "nonveg_cooking",
    "smoking", "alcohol", "life_stage", "daytime_presence", "home_orientation", "sociability",
)
HELD_OUT_ATTRIBUTES: tuple[str, ...] = ("budget_proximity", "interests", "lifestyle_notes")

OPTIONS: dict[str, list[str]] = {k: list(v) for k, v in QUESTIONNAIRE_OPTIONS.items()}
POPULATION_WEIGHTS: dict[str, list[float]] = {k: list(v) for k, v in QUESTIONNAIRE_WEIGHTS.items()}

# Design sizes (proposed; see docs/COHAB_HUMAN_STUDY.md §3 for the reasoning).
N_PAIR_TRIALS = 32
N_REPEATS = 4
N_ATTENTION = 3
N_RANK = 1
N_VARIED = 5  # fields that differ between the two cards of a pair trial
RANK_CARDS = 6
MIN_REPEAT_GAP = 6

# W3 — roommate-pair validation.
# Items most open to flattering self-report (deck limitation 3): each person
# also says how they think their roommate would answer them.
GAMEABLE_FIELDS: tuple[str, ...] = (
    "cleanliness_level", "payment_reliability", "noise_behaviour", "guest_frequency", "chore_approach",
)

# Outcome items, each on a 1-5 scale where 5 is the better outcome.
OUTCOME_ITEMS: dict[str, str] = {
    "overall_satisfaction": "Overall, how satisfied are you living with this person?",
    "would_live_again": "Would you choose to live with them again?",
    "conflict_rarity": "How rarely do you two have disagreements about the home?",
    "cleanliness_conflict": "How rarely do cleanliness or chores cause friction?",
    "noise_sleep_conflict": "How rarely do noise or sleep schedules cause friction?",
    "guests_conflict": "How rarely do guests or partners cause friction?",
    "sharing_conflict": "How rarely does sharing food or belongings cause friction?",
    "money_conflict": "How rarely does money or rent cause friction?",
}
# Which outcome item corresponds to which attribute cluster (for the
# attribute-level analysis in pair_analysis.py).
OUTCOME_ATTRIBUTE_MAP: dict[str, tuple[str, ...]] = {
    "cleanliness_conflict": ("cleanliness_level", "chore_approach"),
    "noise_sleep_conflict": ("sleep_schedule", "noise"),
    "guests_conflict": ("guests",),
    "sharing_conflict": ("sharing_norm",),
    "money_conflict": ("payment_reliability", "cost_split_preference"),
}
SATISFIED_THRESHOLD = 4.0  # mean of the two people's overall_satisfaction


def validate_rater_answers(answers: dict) -> list[str]:
    """Problems with a rater's questionnaire; empty means valid."""
    problems = []
    for f in RATER_FIELDS:
        v = answers.get(f)
        if v is None:
            problems.append(f"{f}: required")
        elif v not in OPTIONS[f]:
            problems.append(f"{f}: {v!r} is not an option")
    extra = set(answers) - set(RATER_FIELDS)
    if extra:
        problems.append(f"unexpected fields: {sorted(extra)}")
    return problems


def validate_important(important: list[str]) -> list[str]:
    if len(important) > 3:
        return ["at most three important attributes"]
    unknown = [a for a in important if a not in STUDY_ATTRIBUTES]
    return [f"unknown attribute {a!r}" for a in unknown]
