"""Crude seed data for Phase 1 — COHAB_BUILD_PLAN.md §4.

Deterministic (fixed seed), ~500 rows, no correlation between matching
fields (budget, move-in date, questionnaire answers). Its only job is to
make Phase 2 (the matcher) testable against a non-trivial pool, including a
few unverified/suspended accounts for the eligibility filter to exclude.

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
USER_COUNT = 500
INSTITUTION_NAME = "Christ University"
EMAIL_DOMAIN = "christuniversity.in"
TODAY = date(2026, 8, 15)

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
ALLERGY_POOL = ["peanuts", "shellfish", "dairy", "gluten", "pollen", "dust_mites"]
LIFESTYLE_NOTE_SAMPLES = [
    "Working on my thesis and trying to keep a predictable routine.",
    "Between classes and a part-time internship, mostly home in the evenings.",
    "Into fitness and cooking, want a place that feels lived-in but calm.",
    "Quiet person who keeps to themselves most of the day.",
    "Enjoy having people over on weekends, otherwise pretty low-key.",
]

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


def random_questionnaire(rng: random.Random) -> dict:
    answers = {key: rng.choice(options) for key, options in QUESTIONNAIRE_OPTIONS.items()}
    answers["interests"] = rng.sample(INTERESTS_POOL, k=rng.randint(0, 5))
    answers["lifestyle_notes"] = rng.choice(LIFESTYLE_NOTE_SAMPLES) if rng.random() < 0.6 else None
    return answers


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


def make_preference_profile(rng: random.Random, user: User) -> PreferenceProfile:
    budget_min = rng.randint(6000, 20000)
    budget_max = budget_min + rng.randint(0, 8000)
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


def make_listing(rng: random.Random, user: User) -> Listing:
    rent = rng.randint(6000, 25000)
    return Listing(
        user=user,
        locality=rng.choice(LOCALITIES),
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

            session.add(make_preference_profile(rng, user))
            for weight in make_attribute_weights(rng, user):
                session.add(weight)
            if user.seeker_type == "has_place":
                session.add(make_listing(rng, user))

        session.commit()
        print(f"Seeded 1 institution, {USER_COUNT} users, and weight_set v2.")
    finally:
        session.close()


if __name__ == "__main__":
    seed()
