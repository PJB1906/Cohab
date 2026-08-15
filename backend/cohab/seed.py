"""Realistic seed data for Phase 3 — COHAB_BUILD_PLAN.md §4, §3.

Deterministic (fixed seed), ~1,500 rows (build plan §3: 1,000-2,000 for
tuning). Dev/test data only, never used in production or a demo (real
profiles come from the Phase 4 signup flow).

Upgraded in place from the Phase 1 crude seed (uniform, uncorrelated values,
~500 rows) once the matcher checkpoint was read (build plan §3: "upgrade the
seeder properly when you reach tuning"). The crude seed's own finding —
median eligible pool ~4-5 out of ~500, dominated by `budget_no_overlap` —
is a permanent record in docs/DECISIONS.md (D-2.5) and does not depend on
this file remaining runnable in its old form.

Three correlations were added, per build plan §3 / PRD §6.6 (filter-yield
analysis "depends on the marginal distributions of budget, locality and
move-in date, which can be modelled realistically"):

- **Budget by locality.** Each profile gets a latent `target_locality`
  (never persisted for `needs_place` members — v1 filters by city only,
  COHAB_MATCHING_SPEC.md §2) that shapes its budget band via
  `LOCALITY_BUDGET_RANGE`. `has_place` listings draw rent from the same
  table, keyed by their actual (persisted) `Listing.locality`. The ₹ ranges
  are **not sourced from any document** — they are proposed, plausible
  Bangalore-locality rent tiers, ordered relative to each other (Koramangala/
  Indiranagar/HSR pricier than Electronic City/Marathahalli/etc.).
- **Move-in clustered around a term start.** ~70% of profiles fall in a
  +/-10-day window around `TERM_START`, echoing PRD §11's "target one intake
  cohort... four-week window"; the rest spread over the next 120 days so the
  pool isn't artificially uniform either.
- **Templated, correlated lifestyle notes.** Composed from fragments keyed by
  `life_stage` and `sociability` (plus an optional `daytime_presence` clause
  and an optional interest mention) instead of five fixed strings, so
  TF-IDF/embedding similarity has real signal to find.

Questionnaire answers are drawn from weighted (non-uniform but
non-degenerate) distributions rather than uniformly — COHAB_MATCHING_SPEC.md
§11's tuning checklist calls out `cost_split_preference` by name as an
attribute that "will only discriminate if the seed generator gives its four
options a realistic spread rather than defaulting most profiles to
`flexible`." A few fields (smoking/alcohol tolerance vs behaviour, diet vs
non-veg cooking tolerance) are lightly conditioned on a related field so rows
don't come out self-contradictory, while keeping real variance.

Name pools are hand-curated for regional/religious/ethnic diversity
reflecting the real Christ University, Bangalore population (confirmed with
the user during Phase 1 planning): weighted toward Kerala/Malayali names
(~27%), with a small (~1%) international slice, mostly West/East African.
`course` values are drawn from real programme names published at
https://christuniversity.in/our-programmes/All/.

Run with: python -m cohab.seed
"""

import random
from datetime import date, datetime, timedelta, timezone

from cohab.db import SessionLocal
from cohab.models import Institution, Listing, PreferenceProfile, User, UserAttributeWeight, WeightSet
from cohab.models.preference import GENDER_PREFERENCES, PET_TOLERANCES
from cohab.models.user import GENDERS, SEEKER_TYPES

SEED = 42
USER_COUNT = 1500
INSTITUTION_NAME = "Christ University"
EMAIL_DOMAIN = "christuniversity.in"
TODAY = date(2026, 8, 15)
# PRD §11 cold-start plan: "target one intake cohort... four-week window."
TERM_START = TODAY + timedelta(days=15)

# --- Name pools -------------------------------------------------------
# Each group: (weight, male_first, female_first, surnames). Sikh surnames
# are handled specially (Singh/Kaur) below rather than via a shared pool.
NAME_GROUPS = [
    (
        0.10,
        "kerala_hindu",
        ["Arjun", "Aravind", "Vishnu", "Sreejith", "Anoop", "Karthik", "Gokul", "Nandakumar"],
        ["Anjali", "Divya", "Meera", "Athira", "Lekshmi", "Devika", "Sruthi", "Parvathy"],
        ["Nair", "Menon", "Pillai", "Kurup", "Warrier", "Namboothiri", "Panicker", "Nambiar"],
    ),
    (
        0.10,
        "kerala_christian",
        ["Thomas", "Varghese", "Jacob", "Binoy", "Cherian", "Abin", "Jerin", "Alex"],
        ["Anna", "Reshma", "Bincy", "Elizabeth", "Tessy", "Sherin", "Merin", "Alphonsa"],
        ["Kurian", "Mathew", "Joseph", "Chacko", "George", "Thomas", "Abraham", "Idiculla"],
    ),
    (
        0.07,
        "kerala_muslim",
        ["Muhammed", "Riyas", "Shameer", "Ashraf", "Nizamudheen", "Faisal", "Anas", "Suhail"],
        ["Fathima", "Ayisha", "Naseera", "Sadiya", "Rahmath", "Nasrin", "Shabana", "Rihana"],
        ["Kutty", "Musaliyar", "Haji", "Koya", "Ravuthar", "Baig", "Kunju", "Rawther"],
    ),
    (
        0.10,
        "tamil",
        ["Karthikeyan", "Suriya", "Bala", "Vignesh", "Dinesh", "Prasanna", "Arun", "Senthil"],
        ["Kavitha", "Lakshmi", "Priya", "Nithya", "Swathi", "Deepa", "Shalini", "Meena"],
        ["Subramaniam", "Krishnan", "Rajendran", "Muthu", "Chidambaram", "Natarajan", "Balasubramanian", "Iyer"],
    ),
    (
        0.08,
        "telugu",
        ["Sai", "Venkatesh", "Naveen", "Praveen", "Ravi", "Sriram", "Charan", "Manoj"],
        ["Sravani", "Padma", "Anitha", "Bhavya", "Keerthi", "Swapna", "Lakshmi", "Divya"],
        ["Reddy", "Naidu", "Rao", "Chowdary", "Sharma", "Prasad", "Varma", "Gupta"],
    ),
    (
        0.08,
        "kannada",
        ["Chetan", "Rakesh", "Manjunath", "Vinay", "Sharath", "Kiran", "Yashas", "Prasad"],
        ["Shreya", "Pooja", "Deepika", "Nayana", "Sindhu", "Rekha", "Anitha", "Bhoomika"],
        ["Gowda", "Hegde", "Shetty", "Rao", "Naik", "Kulkarni", "Bhat", "Achar"],
    ),
    (
        0.12,
        "hindi_belt_hindu",
        ["Rohan", "Aditya", "Rahul", "Vikas", "Amit", "Saurabh", "Ankit", "Deepak"],
        ["Priya", "Neha", "Pooja", "Kavita", "Anjali", "Shweta", "Ritu", "Nisha"],
        ["Sharma", "Verma", "Gupta", "Yadav", "Tiwari", "Mishra", "Chauhan", "Singh"],
    ),
    (
        0.06,
        "north_indian_muslim",
        ["Imran", "Faizan", "Zeeshan", "Danish", "Arbaz", "Salman", "Sohail", "Nadeem"],
        ["Ayesha", "Zara", "Sana", "Nazia", "Farheen", "Alia", "Shifa", "Rukhsar"],
        ["Khan", "Siddiqui", "Ansari", "Qureshi", "Sheikh", "Ali", "Beg", "Rizvi"],
    ),
    (
        0.06,
        "punjabi_sikh",
        ["Gurpreet", "Harpreet", "Jaspreet", "Manpreet", "Ranjit", "Baljeet", "Amandeep", "Karanveer"],
        ["Simran", "Navjot", "Amrit", "Rupinder", "Harleen", "Kirandeep", "Manveer", "Jasleen"],
        None,  # Singh / Kaur, handled specially
    ),
    (
        0.07,
        "bengali",
        ["Debashish", "Soumya", "Anirban", "Rajarshi", "Arka", "Subhro", "Rohit", "Ayan"],
        ["Ananya", "Debolina", "Riya", "Sohini", "Paromita", "Trisha", "Ishita", "Mou"],
        ["Banerjee", "Chatterjee", "Mukherjee", "Bose", "Sengupta", "Dasgupta", "Roy", "Ghosh"],
    ),
    (
        0.07,
        "marathi",
        ["Aniket", "Omkar", "Sujay", "Rohit", "Nikhil", "Suyash", "Abhijit", "Yash"],
        ["Sanika", "Snehal", "Manasi", "Aditi", "Pallavi", "Shraddha", "Gauri", "Mrunal"],
        ["Deshmukh", "Kulkarni", "Joshi", "Patil", "Kale", "Bhosale", "Gaikwad", "Sathe"],
    ),
    (
        0.06,
        "gujarati",
        ["Parth", "Jay", "Dhruv", "Kush", "Meet", "Yash", "Devang", "Nirav"],
        ["Riya", "Krupa", "Foram", "Dhriti", "Bhoomi", "Payal", "Urvi", "Zeel"],
        ["Patel", "Shah", "Mehta", "Desai", "Trivedi", "Joshi", "Gandhi", "Pandya"],
    ),
    (
        0.02,
        "northeastern",
        ["Bijoy", "Rikin", "Thangboi", "Kevichusa", "Wanglar", "Rahul", "Bendang", "Lalrin"],
        ["Momi", "Rimjhim", "Chubaakala", "Yasmin", "Iman", "Sonam", "Wandana", "Lalrem"],
        ["Gogoi", "Baruah", "Hmar", "Jamir", "Longkumer", "Marak", "Nongrum", "Lalrinawma"],
    ),
    (
        0.01,
        "international_african",
        ["Chinedu", "Emeka", "Kwame", "Kofi", "Abebe", "Tendai", "Olumide", "Sekou"],
        ["Chioma", "Amara", "Ama", "Abena", "Selam", "Fatou", "Ngozi", "Wanjiru"],
        ["Okafor", "Adeyemi", "Mensah", "Owusu", "Bekele", "Diallo", "Mwangi", "Osei"],
    ),
]

COURSES = [
    "BCom",
    "BCA",
    "BBA",
    "BA Economics",
    "BA English",
    "BA Psychology",
    "BA Journalism & Mass Communication",
    "BSc Physics Chemistry Mathematics",
    "BSc Computer Science Mathematics Statistics",
    "BA LLB",
    "MBA",
    "MSc Data Science",
    "MSc Statistics",
    "MSc Sustainable Development",
    "MSc Clinical Psychology",
    "MCA",
    "MA Economics",
    "PGDM",
]

LOCALITIES = [
    "Koramangala",
    "Indiranagar",
    "HSR Layout",
    "BTM Layout",
    "Whitefield",
    "Marathahalli",
    "JP Nagar",
    "Jayanagar",
    "Bannerghatta Road",
    "Electronic City",
    "Hebbal",
    "Kalyan Nagar",
]

# Proposed, not spec-derived (see module docstring): plausible per-person
# rent tiers by locality, ordered relative to each other, used to correlate
# budgets/rent instead of drawing them independently.
LOCALITY_BUDGET_RANGE: dict[str, tuple[int, int]] = {
    "Koramangala": (16000, 28000),
    "Indiranagar": (15000, 26000),
    "HSR Layout": (14000, 24000),
    "Jayanagar": (11000, 19000),
    "JP Nagar": (10000, 18000),
    "BTM Layout": (10000, 17000),
    "Kalyan Nagar": (10000, 17000),
    "Whitefield": (8000, 15000),
    "Marathahalli": (8000, 14000),
    "Electronic City": (7000, 13000),
    "Hebbal": (8000, 14000),
    "Bannerghatta Road": (7000, 13000),
}

AMENITIES = ["wifi", "furnished", "washing_machine", "parking", "power_backup", "gym", "housekeeping"]
INTERESTS_POOL = [
    "sports_fitness",
    "music",
    "gaming",
    "cooking",
    "reading",
    "film_series",
    "travel",
    "art_design",
    "technology",
    "volunteering",
    "photography",
    "outdoors",
]
INTEREST_LABELS = {
    "sports_fitness": "sport and fitness",
    "music": "music",
    "gaming": "gaming",
    "cooking": "cooking",
    "reading": "reading",
    "film_series": "films and shows",
    "travel": "travel",
    "art_design": "art and design",
    "technology": "tech",
    "volunteering": "volunteering",
    "photography": "photography",
    "outdoors": "the outdoors",
}
ALLERGY_POOL = ["peanuts", "shellfish", "dairy", "gluten", "pollen", "dust_mites"]

# --- Templated, correlated lifestyle notes (spec §3 Q18; §11 relies on real
# textual signal existing for the TF-IDF/embedding comparison) -------------

LIFESTAGE_FRAGMENTS: dict[str, list[str]] = {
    "coursework": [
        "Balancing coursework and trying to keep a steady weekly rhythm.",
        "Between lectures and assignments most of the week.",
        "Juggling classes and keeping a fairly regular schedule.",
    ],
    "exam_prep": [
        "Deep in exam preparation and need a predictable, quiet routine.",
        "Studying for a competitive exam, most days look the same.",
        "Heads-down on exam prep with long stretches of focused study.",
    ],
    "job": [
        "Working full-time and keeping fairly regular hours.",
        "Between office hours and winding down in the evenings.",
        "Working a day job, home most evenings.",
    ],
    "building": [
        "Building something of my own, so hours can be unpredictable.",
        "Working on a project of my own, odd hours and occasional late calls.",
        "Deep in building a startup, my schedule shifts around a lot.",
    ],
    "research": [
        "Working on research and thesis work, long stretches of quiet focus.",
        "Mostly buried in research, my day is fairly self-directed.",
        "Thesis work keeps me at my desk more than anywhere else.",
    ],
}

SOCIABILITY_FRAGMENTS: dict[str, list[str]] = {
    "friend": [
        "Would love a flatmate I actually spend time with.",
        "Hoping to find someone I get along with and hang out with.",
        "Looking for a home that feels more like friends than flatmates.",
    ],
    "friendly": [
        "Friendly at home, but happy for us to live our own lives.",
        "Happy to chat and share a meal now and then, otherwise independent.",
        "Keep things warm but everyone does their own thing.",
    ],
    "independent": [
        "Prefer to keep things polite and independent.",
        "Mostly keep to myself and value my own space.",
        "Looking for a quiet, low-key household.",
    ],
}

DAYTIME_FRAGMENTS: dict[str, list[str]] = {
    "out": ["Out of the house most of the day."],
    "partly": ["Home for part of the day, out for the rest."],
    "home": ["Mostly home during the day."],
}

# COHAB_MATCHING_SPEC.md §3 option lists, keyed as in `questionnaire` JSONB.
QUESTIONNAIRE_OPTIONS = {
    "sleep_schedule": ["early", "regular", "night_owl", "varies"],
    "noise_preference": ["strict", "moderate", "flexible"],
    "noise_behaviour": ["quiet", "moderate", "loud"],
    "cleanliness_level": ["very_tidy", "moderate", "relaxed"],
    "chore_approach": ["rota", "shared", "hired", "own_mess"],
    "sharing_norm": ["communal", "ask_first", "separate"],
    "guest_frequency": ["rarely", "occasionally", "often", "partner_regular"],
    "guest_tolerance": ["anytime", "with_notice", "weekends", "prefer_none"],
    "communication_style": ["direct_now", "calm_later", "message", "let_go"],
    "payment_reliability": ["early", "on_time", "needs_grace", "needs_reminding"],
    "cost_split_preference": ["equal", "by_room", "by_use", "flexible"],
    "diet": ["veg", "nonveg", "eggetarian", "vegan", "jain"],
    "nonveg_cooking_tolerance": ["fine", "prefer_not", "not_at_all"],
    "smoking_behaviour": ["none", "outside", "indoors"],
    "smoking_tolerance": ["fine", "outside_ok", "smoke_free"],
    # "Same structure for alcohol" — COHAB_MATCHING_SPEC.md §3 Q12 gives no
    # distinct token set, so the smoking tokens are reused literally.
    "alcohol_behaviour": ["none", "outside", "indoors"],
    "alcohol_tolerance": ["fine", "outside_ok", "smoke_free"],
    "life_stage": ["coursework", "exam_prep", "job", "building", "research"],
    "daytime_presence": ["out", "partly", "home"],
    "home_orientation": ["homebody", "balanced", "rarely"],
    "sociability": ["friend", "friendly", "independent"],
}

# Weighted, non-uniform but non-degenerate distributions (proposed, not
# spec-derived — see module docstring). Every option keeps meaningful mass;
# spec §11's tuning checklist names `cost_split_preference` specifically as
# an attribute that must not collapse onto `flexible`.
QUESTIONNAIRE_WEIGHTS: dict[str, list[float]] = {
    "sleep_schedule": [0.25, 0.40, 0.20, 0.15],
    "noise_preference": [0.25, 0.50, 0.25],
    "noise_behaviour": [0.35, 0.50, 0.15],
    "cleanliness_level": [0.25, 0.50, 0.25],
    "chore_approach": [0.25, 0.40, 0.10, 0.25],
    "sharing_norm": [0.30, 0.45, 0.25],
    "guest_frequency": [0.30, 0.40, 0.20, 0.10],
    "guest_tolerance": [0.25, 0.40, 0.20, 0.15],
    "communication_style": [0.25, 0.35, 0.25, 0.15],
    "payment_reliability": [0.30, 0.45, 0.15, 0.10],
    "cost_split_preference": [0.35, 0.20, 0.20, 0.25],
    "diet": [0.40, 0.35, 0.12, 0.05, 0.08],
    "life_stage": [0.35, 0.15, 0.20, 0.10, 0.20],
    "daytime_presence": [0.40, 0.35, 0.25],
    "home_orientation": [0.25, 0.50, 0.25],
    "sociability": [0.30, 0.45, 0.25],
}

# --- Light cross-attribute conditioning, so rows aren't self-contradictory
# (a heavy smoker asking for a smoke-free home, a vegan indifferent to
# non-veg cooking) while keeping real variance in the conditioned field. ---

SMOKING_TOLERANCE_WEIGHTS = {
    "indoors": [0.50, 0.40, 0.10],
    "outside": [0.35, 0.45, 0.20],
    "none": [0.25, 0.35, 0.40],
}  # keyed by smoking_behaviour -> [fine, outside_ok, smoke_free]

ALCOHOL_TOLERANCE_WEIGHTS = {
    "indoors": [0.50, 0.40, 0.10],
    "outside": [0.35, 0.45, 0.20],
    "none": [0.25, 0.35, 0.40],
}  # keyed by alcohol_behaviour -> [fine, outside_ok, smoke_free]

NONVEG_COOKING_TOLERANCE_WEIGHTS = {
    "vegan": [0.15, 0.35, 0.50],
    "jain": [0.15, 0.35, 0.50],
    "veg": [0.30, 0.45, 0.25],
    "eggetarian": [0.70, 0.25, 0.05],
    "nonveg": [0.70, 0.25, 0.05],
}  # keyed by diet -> [fine, prefer_not, not_at_all]


def random_name(rng: random.Random, gender: str) -> tuple[str, str]:
    weights = [g[0] for g in NAME_GROUPS]
    group = rng.choices(NAME_GROUPS, weights=weights, k=1)[0]
    _, label, male_first, female_first, surnames = group
    first_pool = male_first if gender == "male" else female_first if gender == "female" else male_first + female_first
    first = rng.choice(first_pool)
    if label == "punjabi_sikh":
        last = "Singh" if gender != "female" else "Kaur"
    else:
        last = rng.choice(surnames)
    return first, last


def _weighted_choice(rng: random.Random, key: str) -> str:
    options = QUESTIONNAIRE_OPTIONS[key]
    weights = QUESTIONNAIRE_WEIGHTS.get(key)
    if weights is None:
        return rng.choice(options)
    return rng.choices(options, weights=weights, k=1)[0]


def compose_lifestyle_note(rng: random.Random, answers: dict) -> str:
    parts = [
        rng.choice(LIFESTAGE_FRAGMENTS[answers["life_stage"]]),
        rng.choice(SOCIABILITY_FRAGMENTS[answers["sociability"]]),
    ]
    if rng.random() < 0.4:
        parts.append(rng.choice(DAYTIME_FRAGMENTS[answers["daytime_presence"]]))
    interests = answers.get("interests") or []
    if interests and rng.random() < 0.45:
        label = INTEREST_LABELS[rng.choice(interests)]
        parts.append(f"Into {label} outside of that.")
    return " ".join(parts)


def random_questionnaire(rng: random.Random) -> dict:
    answers = {key: _weighted_choice(rng, key) for key in QUESTIONNAIRE_OPTIONS}

    # Light conditioning so smoking/alcohol/diet tolerances aren't
    # independent of the matching behaviour (see module docstring).
    answers["smoking_tolerance"] = rng.choices(
        QUESTIONNAIRE_OPTIONS["smoking_tolerance"],
        weights=SMOKING_TOLERANCE_WEIGHTS[answers["smoking_behaviour"]],
        k=1,
    )[0]
    answers["alcohol_tolerance"] = rng.choices(
        QUESTIONNAIRE_OPTIONS["alcohol_tolerance"],
        weights=ALCOHOL_TOLERANCE_WEIGHTS[answers["alcohol_behaviour"]],
        k=1,
    )[0]
    answers["nonveg_cooking_tolerance"] = rng.choices(
        QUESTIONNAIRE_OPTIONS["nonveg_cooking_tolerance"],
        weights=NONVEG_COOKING_TOLERANCE_WEIGHTS[answers["diet"]],
        k=1,
    )[0]

    answers["interests"] = rng.sample(INTERESTS_POOL, k=rng.randint(0, 5))
    answers["lifestyle_notes"] = compose_lifestyle_note(rng, answers) if rng.random() < 0.7 else None
    return answers


# COHAB_MATCHING_SPEC.md §8 — weight set v2 (see the header/footer
# inconsistency noted in the Phase 1 plan; seeded as version 2).
DEFAULT_WEIGHTS = {
    "cleanliness_level": 0.11,
    "chore_approach": 0.06,
    "sharing_norm": 0.04,
    "sleep_schedule": 0.09,
    "noise": 0.09,
    "guests": 0.10,
    "payment_reliability": 0.08,
    "cost_split_preference": 0.03,
    "communication_style": 0.08,
    "budget_proximity": 0.06,
    "diet": 0.03,
    "nonveg_cooking": 0.03,
    "smoking": 0.03,
    "alcohol": 0.02,
    "life_stage": 0.04,
    "daytime_presence": 0.02,
    "home_orientation": 0.02,
    "sociability": 0.02,
    "interests": 0.02,
    "lifestyle_notes": 0.03,
}


def make_institution() -> Institution:
    return Institution(name=INSTITUTION_NAME, email_domain=EMAIL_DOMAIN)


def make_weight_set() -> WeightSet:
    return WeightSet(
        version=2,
        source="expert",
        weights=DEFAULT_WEIGHTS,
        published_at=datetime.now(timezone.utc),
        is_active=True,
    )


def make_user(rng: random.Random, institution: Institution, index: int) -> User:
    gender = rng.choice(GENDERS)
    seeker_type = rng.choice(SEEKER_TYPES)
    first, last = random_name(rng, gender)
    email = f"{first.lower()}.{last.lower()}{index}@{EMAIL_DOMAIN}"

    status_roll = rng.random()
    if status_roll < 0.90:
        verification_status, account_status = "verified", "active"
    elif status_roll < 0.95:
        verification_status, account_status = "unverified", "active"
    else:
        verification_status, account_status = "verified", "suspended"

    return User(
        institution=institution,
        email=email,
        password_hash="not-set",  # Phase 4 wires real auth; placeholder only.
        full_name=f"{first} {last}",
        gender=gender,
        seeker_type=seeker_type,
        verification_status=verification_status,
        account_status=account_status,
        course=rng.choice(COURSES) if rng.random() < 0.85 else None,
    )


def pick_target_locality(rng: random.Random) -> str:
    """Latent variable correlating a profile's budget and (if has_place) its
    listing — never persisted for `needs_place` members (spec §2: v1 filters
    by city only, not locality)."""
    return rng.choice(LOCALITIES)


def budget_band_for_locality(rng: random.Random, locality: str) -> tuple[int, int]:
    lo, hi = LOCALITY_BUDGET_RANGE[locality]
    centre = rng.randint(lo, hi)
    half_width = rng.randint(1000, 2500)
    budget_min = max(3000, centre - half_width)
    budget_max = centre + half_width
    return budget_min, budget_max


def make_preference_profile(rng: random.Random, user: User, target_locality: str) -> PreferenceProfile:
    budget_min, budget_max = budget_band_for_locality(rng, target_locality)

    # ~70% cluster around the term start (PRD §11 intake-cohort window);
    # the rest spread over the next 120 days.
    if rng.random() < 0.7:
        move_in_date = TERM_START + timedelta(days=rng.randint(-10, 10))
    else:
        move_in_date = TODAY + timedelta(days=rng.randint(0, 120))

    allergies = rng.sample(ALLERGY_POOL, k=1) if rng.random() < 0.2 else []

    return PreferenceProfile(
        user=user,
        city="Bangalore",
        budget_min=budget_min,
        budget_max=budget_max,
        move_in_date=move_in_date,
        gender_preference=rng.choice(GENDER_PREFERENCES),
        severe_allergy=allergies,
        has_pet=rng.random() < 0.1,
        pet_tolerance=rng.choice(PET_TOLERANCES),
        smoking_dealbreaker=rng.random() < 0.3,
        questionnaire=random_questionnaire(rng),
        text_vector=None,
        text_vector_kind=None,
    )


def make_attribute_weights(rng: random.Random, user: User) -> list[UserAttributeWeight]:
    if rng.random() < 0.2:
        return []  # skipped screen 6 — platform defaults apply
    chosen = rng.sample(list(DEFAULT_WEIGHTS.keys()), k=rng.randint(1, 3))
    return [
        UserAttributeWeight(user=user, attribute_name=name, is_selected_important=True)
        for name in chosen
    ]


def make_listing(rng: random.Random, user: User, target_locality: str) -> Listing:
    lo, hi = LOCALITY_BUDGET_RANGE[target_locality]
    rent = rng.randint(lo, hi)
    return Listing(
        user=user,
        locality=target_locality,
        rent_per_person=rent,
        deposit=rent * rng.choice([1, 2, 3]),
        room_type=rng.choice(["private", "shared"]),
        available_from=TODAY + timedelta(days=rng.randint(0, 120)),
        amenities=rng.sample(AMENITIES, k=rng.randint(0, len(AMENITIES))),
        photos=[],
        current_housemates=rng.randint(0, 3),
    )


def seed() -> None:
    rng = random.Random(SEED)
    session = SessionLocal()
    try:
        existing = session.query(Institution).filter_by(email_domain=EMAIL_DOMAIN).first()
        if existing is not None:
            print(f"Institution '{EMAIL_DOMAIN}' already seeded — skipping.")
            return

        institution = make_institution()
        session.add(institution)
        session.add(make_weight_set())
        session.flush()

        for i in range(USER_COUNT):
            user = make_user(rng, institution, i)
            session.add(user)
            session.flush()  # user.id needed by dependents below

            target_locality = pick_target_locality(rng)
            session.add(make_preference_profile(rng, user, target_locality))
            for weight in make_attribute_weights(rng, user):
                session.add(weight)
            if user.seeker_type == "has_place":
                session.add(make_listing(rng, user, target_locality))

        session.commit()
        print(f"Seeded 1 institution, {USER_COUNT} users, and weight_set v2.")
    finally:
        session.close()


if __name__ == "__main__":
    seed()
