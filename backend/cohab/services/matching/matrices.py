"""Scoring matrices and constants — the numeric heart of the matcher.

Every value here is transcribed from COHAB_MATCHING_SPEC.md and cited to its
section. Per spec §1, no magic constant may live in the matcher that is not
written down in that spec; this module is the one place those numbers live.

Layout:
- SIMILARITY_MATRICES  — symmetric, diagonal 1.0 (spec §4)
- TOLERANCE_MATRICES   — asymmetric, rows = A's preference, cols = B's behaviour
                         (spec §5)
- PAYMENT_RELIABILITY  — absolute, depends only on B's value (spec §6)
- ordinal_similarity / jaccard_similarity / budget_similarity  — continuous and
                         set helpers (spec §4, §7)
- config constants     — MOVE_IN_TOLERANCE_DAYS, BUDGET_SPREAD (spec §2, §7)
"""

# --- Config constants (spec §2, §7) ----------------------------------------

# Spec §2: "single biggest lever on filter yield", a starting guess to tune in
# Phase 3. Config value, never a bare literal in the filter.
MOVE_IN_TOLERANCE_DAYS = 30

# Spec §7: a ₹15,000 midpoint gap scores zero; ₹2,000 scores 0.87.
BUDGET_SPREAD = 15000


# --- Similarity matrices (spec §4) — symmetric, diagonal 1.0 ----------------

SIMILARITY_MATRICES: dict[str, dict[str, dict[str, float]]] = {
    # spec §4 sleep_schedule — `varies` never scores 1.0 even against itself.
    "sleep_schedule": {
        "early":     {"early": 1.00, "regular": 0.70, "night_owl": 0.20, "varies": 0.60},
        "regular":   {"early": 0.70, "regular": 1.00, "night_owl": 0.60, "varies": 0.75},
        "night_owl": {"early": 0.20, "regular": 0.60, "night_owl": 1.00, "varies": 0.60},
        "varies":    {"early": 0.60, "regular": 0.75, "night_owl": 0.60, "varies": 0.80},
    },
    # spec §4 cleanliness_level — very_tidy/relaxed = 0.15, harshest cell.
    "cleanliness_level": {
        "very_tidy": {"very_tidy": 1.00, "moderate": 0.60, "relaxed": 0.15},
        "moderate":  {"very_tidy": 0.60, "moderate": 1.00, "relaxed": 0.60},
        "relaxed":   {"very_tidy": 0.15, "moderate": 0.60, "relaxed": 1.00},
    },
    # spec §4 chore_approach.
    "chore_approach": {
        "rota":     {"rota": 1.00, "shared": 0.65, "hired": 0.60, "own_mess": 0.25},
        "shared":   {"rota": 0.65, "shared": 1.00, "hired": 0.70, "own_mess": 0.45},
        "hired":    {"rota": 0.60, "shared": 0.70, "hired": 1.00, "own_mess": 0.55},
        "own_mess": {"rota": 0.25, "shared": 0.45, "hired": 0.55, "own_mess": 1.00},
    },
    # spec §4 communication_style — two `let_go` score 0.55, not 1.0.
    "communication_style": {
        "direct_now": {"direct_now": 1.00, "calm_later": 0.75, "message": 0.45, "let_go": 0.30},
        "calm_later": {"direct_now": 0.75, "calm_later": 1.00, "message": 0.70, "let_go": 0.50},
        "message":    {"direct_now": 0.45, "calm_later": 0.70, "message": 1.00, "let_go": 0.60},
        "let_go":     {"direct_now": 0.30, "calm_later": 0.50, "message": 0.60, "let_go": 0.55},
    },
    # spec §4 cost_split_preference — two `flexible` score 0.75, not 1.0.
    "cost_split_preference": {
        "equal":    {"equal": 1.00, "by_room": 0.45, "by_use": 0.50, "flexible": 0.85},
        "by_room":  {"equal": 0.45, "by_room": 1.00, "by_use": 0.70, "flexible": 0.85},
        "by_use":   {"equal": 0.50, "by_room": 0.70, "by_use": 1.00, "flexible": 0.85},
        "flexible": {"equal": 0.85, "by_room": 0.85, "by_use": 0.85, "flexible": 0.75},
    },
    # spec §4 sociability — symmetric; friend/independent = 0.25 floor.
    "sociability": {
        "friend":      {"friend": 1.00, "friendly": 0.70, "independent": 0.25},
        "friendly":    {"friend": 0.70, "friendly": 1.00, "independent": 0.70},
        "independent": {"friend": 0.25, "friendly": 0.70, "independent": 1.00},
    },
    # spec §4 diet — deliberately shallow; veg/nonveg floor 0.50.
    "diet": {
        "veg":        {"veg": 1.00, "nonveg": 0.50, "eggetarian": 0.80, "vegan": 0.80, "jain": 0.75},
        "nonveg":     {"veg": 0.50, "nonveg": 1.00, "eggetarian": 0.80, "vegan": 0.40, "jain": 0.35},
        "eggetarian": {"veg": 0.80, "nonveg": 0.80, "eggetarian": 1.00, "vegan": 0.60, "jain": 0.55},
        "vegan":      {"veg": 0.80, "nonveg": 0.40, "eggetarian": 0.60, "vegan": 1.00, "jain": 0.70},
        "jain":       {"veg": 0.75, "nonveg": 0.35, "eggetarian": 0.55, "vegan": 0.70, "jain": 1.00},
    },
    # spec §4 life_stage.
    "life_stage": {
        "coursework": {"coursework": 1.00, "exam_prep": 0.70, "job": 0.65, "building": 0.55, "research": 0.75},
        "exam_prep":  {"coursework": 0.70, "exam_prep": 1.00, "job": 0.55, "building": 0.35, "research": 0.70},
        "job":        {"coursework": 0.65, "exam_prep": 0.55, "job": 1.00, "building": 0.75, "research": 0.65},
        "building":   {"coursework": 0.55, "exam_prep": 0.35, "job": 0.75, "building": 1.00, "research": 0.60},
        "research":   {"coursework": 0.75, "exam_prep": 0.70, "job": 0.65, "building": 0.60, "research": 1.00},
    },
}

# spec §4: daytime_presence and home_orientation use ordinal distance over their
# ordered option lists, `1 - |i - j| / (n - 1)`.
ORDINAL_ORDERS: dict[str, tuple[str, ...]] = {
    "daytime_presence": ("out", "partly", "home"),
    "home_orientation": ("homebody", "balanced", "rarely"),
}

# spec §4 interests: Jaccard over selected tags, floor 0.3 when either empty.
INTERESTS_EMPTY_FLOOR = 0.3

# spec §7 text: neutral score when either lifestyle_notes is empty.
TEXT_NEUTRAL = 0.5


# --- Tolerance matrices (spec §5) — asymmetric, rows = A pref, cols = B behav -

# Non-veg cooking (spec §5): the spec groups B's diet into three columns —
# {veg, vegan, jain} share the first column. Expanded here to direct diet keys.
_NONVEG_VEGLIKE = {"veg": 1.0, "vegan": 1.0, "jain": 1.0}  # placeholder, filled below

TOLERANCE_MATRICES: dict[str, dict[str, dict[str, float]]] = {
    # spec §5 guests — guest_tolerance (A) × guest_frequency (B).
    "guests": {
        "anytime":     {"rarely": 1.00, "occasionally": 1.00, "often": 0.95, "partner_regular": 0.90},
        "with_notice": {"rarely": 1.00, "occasionally": 0.90, "often": 0.70, "partner_regular": 0.60},
        "weekends":    {"rarely": 1.00, "occasionally": 0.80, "often": 0.40, "partner_regular": 0.30},
        "prefer_none": {"rarely": 1.00, "occasionally": 0.50, "often": 0.20, "partner_regular": 0.10},
    },
    # spec §5 sharing — sharing_norm (A) × sharing_norm (B); asymmetric.
    "sharing": {
        "communal":  {"communal": 1.00, "ask_first": 0.85, "separate": 0.55},
        "ask_first": {"communal": 0.90, "ask_first": 1.00, "separate": 0.85},
        "separate":  {"communal": 0.35, "ask_first": 0.90, "separate": 1.00},
    },
    # spec §5 smoking — smoking_tolerance (A) × smoking_behaviour (B).
    "smoking": {
        "fine":       {"none": 1.00, "outside": 1.00, "indoors": 0.90},
        "outside_ok": {"none": 1.00, "outside": 0.95, "indoors": 0.25},
        "smoke_free": {"none": 1.00, "outside": 0.60, "indoors": 0.00},
    },
    # spec §5 alcohol — "same structure, softer floors (0.15 rather than 0.00)".
    # Identical to smoking except the single 0.00 cell becomes 0.15.
    "alcohol": {
        "fine":       {"none": 1.00, "outside": 1.00, "indoors": 0.90},
        "outside_ok": {"none": 1.00, "outside": 0.95, "indoors": 0.25},
        "smoke_free": {"none": 1.00, "outside": 0.60, "indoors": 0.15},
    },
    # spec §5 non-veg cooking — nonveg_cooking_tolerance (A) × diet (B).
    "nonveg_cooking": {
        "fine":       {"veg": 1.00, "vegan": 1.00, "jain": 1.00, "eggetarian": 1.00, "nonveg": 1.00},
        "prefer_not": {"veg": 1.00, "vegan": 1.00, "jain": 1.00, "eggetarian": 0.80, "nonveg": 0.45},
        "not_at_all": {"veg": 1.00, "vegan": 1.00, "jain": 1.00, "eggetarian": 0.55, "nonveg": 0.15},
    },
    # spec §5 noise — noise_preference (A) × noise_behaviour (B).
    "noise": {
        "flexible": {"quiet": 1.00, "moderate": 1.00, "loud": 0.85},
        "moderate": {"quiet": 1.00, "moderate": 0.85, "loud": 0.40},
        "strict":   {"quiet": 1.00, "moderate": 0.60, "loud": 0.10},
    },
}
del _NONVEG_VEGLIKE  # only documented the grouping; the matrix above is expanded


# --- Absolute scores (spec §6) — depend only on B's value ------------------

PAYMENT_RELIABILITY: dict[str, float] = {
    "early": 1.00,
    "on_time": 0.95,
    "needs_grace": 0.50,
    "needs_reminding": 0.25,
}


# --- Continuous / set helpers ----------------------------------------------

def ordinal_similarity(order: tuple[str, ...], a: str, b: str) -> float:
    """spec §4: 1 - |i - j| / (n - 1) over an ordered option list."""
    i, j = order.index(a), order.index(b)
    n = len(order)
    return 1.0 - abs(i - j) / (n - 1)


def jaccard_similarity(a: list[str] | None, b: list[str] | None) -> float:
    """spec §4 interests: |A ∩ B| / |A ∪ B|, floor 0.3 when either list empty."""
    set_a, set_b = set(a or []), set(b or [])
    if not set_a or not set_b:
        return INTERESTS_EMPTY_FLOOR
    union = set_a | set_b
    return len(set_a & set_b) / len(union)


def budget_similarity(mid_a: float, mid_b: float) -> float:
    """spec §7: max(0, 1 - |mid_a - mid_b| / BUDGET_SPREAD)."""
    return max(0.0, 1.0 - abs(mid_a - mid_b) / BUDGET_SPREAD)
