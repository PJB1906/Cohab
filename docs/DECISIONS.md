# Cohab — Engineering Decisions Log

A running record of design decisions taken during the build that are **not**
fixed by `COHAB_PRD.md` or `COHAB_MATCHING_SPEC.md` (the authoritative specs), or
that deliberately deviate from them. CLAUDE.md requires these to be recorded here
rather than diverging silently, so the report and viva can draw on them. Each
entry names the spec section it relates to and the code that implements it.

---

## Phase 2 — Matcher

### D-2.1 Severe-allergy constraint needs a schema field that does not exist yet

**Spec:** §2 — *"If A declares a severe allergy, B must not require that allergen
in the shared kitchen."* The rule is **asymmetric** (A's allergy vs B's kitchen
behaviour), so it needs two signals per person: what they are allergic to, and
what allergens they bring into / need in the shared kitchen.

**Gap:** the Phase 1 `preference_profile` schema carries only `severe_allergy`
(what a person is allergic to). There is no "cooks with / requires allergen"
column, so the constraint's second signal is unrepresented.

**Decision:** rather than invent a proxy (e.g. mapping the allergy onto `diet`,
which does not capture peanuts/shellfish/dairy/gluten), the matcher's
`Candidate` carries an explicit `kitchen_allergens` list. The constraint checks
`A.severe_allergy ∩ B.kitchen_allergens` in **both directions** and is fully unit
-tested. `kitchen_allergens` is **empty until Phase 4** adds the profile field and
its questionnaire item, so the constraint is coded and correct but **inert on
current data** — which is the honest behaviour, since we genuinely do not yet
collect the data it needs.

**Follow-up (Phase 4):** add a `kitchen_allergens` field to `preference_profile`
+ the profile CRUD, and populate `Candidate.from_orm` from it. Then the
constraint activates with no matcher change.

**Code:** `candidate.py` (`kitchen_allergens`), `eligibility.py`
(`Reason.SEVERE_ALLERGY`), `tests/matching/test_eligibility.py`.

### D-2.2 Importance blending is literal "× 1.5, remainder scaled"

**Spec:** §9 — *"attributes the user selected as most important are multiplied by
1.5, the remainder scaled down so the vector sums to 1"*; §3 — *"the rest are
scaled down proportionally so the vector still sums to 1."*

**Decision:** `blend()` boosts each selected attribute to exactly **1.5× its
default weight** and scales only the **unselected remainder** so the vector sums
to 1 — as written, rather than the common alternative of multiplying then
renormalising the *whole* vector (which would leave selected attributes at
`1.5×default / Σ`, i.e. not exactly 1.5×). The chosen reading gives the clean,
defensible property that a selected attribute's final weight is exactly 1.5× its
platform default. Degenerate cases (no remainder, or boost alone ≥ 1) fall back
to a plain full renormalisation.

**Code:** `scoring.py` (`blend`), `tests/matching/test_scoring.py`
(`test_blend_boosts_selected_to_exactly_1_5x_default`).

### D-2.3 Explanation cards are restricted to attributes the spec gives copy for

**Spec:** §10 provides agreement copy for ~11 attributes and divergence copy for
~8. It gives no copy for `chore_approach`, `communication_style`, `smoking`,
`alcohol`, `nonveg_cooking`, `daytime_presence`, `home_orientation`,
`budget_proximity`.

**Decision:** cards pick the top-3 agreements (≥ 0.8) and single divergence
(< 0.5) from **templated attributes only**; an attribute with no copy is skipped
rather than shown with invented wording. Cards are rendered from the **viewer's**
direction (`sim_a` for viewer A), so tolerance/absolute copy is framed by the
candidate's value ("…which suits you"), matching the §10 examples. A future
iteration can add the missing copy without touching the scoring.

**Code:** `explanations.py` (`AGREEMENT_RENDERERS`, `DIVERGENCE_RENDERERS`).

### D-2.4 Matcher input is a framework-free `Candidate`, not ORM objects

**Decision:** all scoring runs on a plain `Candidate` dataclass, adapted from the
`(User, PreferenceProfile, Listing)` triple by `Candidate.from_orm`. This keeps
the business logic importable and testable without FastAPI or a database
(CLAUDE.md architecture rule) and lets the unit tests use hand-written fixtures.

**Code:** `candidate.py`.

### D-2.5 Filter-yield finding on the crude seed, and how it is fixed

**Spec:** §11 tuning check 1; build plan §3 (*"find out your filter yield early"*).

**Finding (measured, not just predicted):** the median eligible pool is **≈ 4–5**
(min 0), well under the target of 10, with `budget_no_overlap` the dominant
exclusion by a wide margin. This is a property of the *crude, uncorrelated*
seeder, **not** the matcher or the constraints. Reproduce with
`python -m cohab.services.matching.report`.

**Sensitivity probe** (120 sample subjects, 500-row pool; read-only, throwaway):

| Change | Median eligible pool |
|---|---|
| Current (move-in 30 days) | 5 |
| Move-in 60 days | 9 |
| Move-in 90 days | 10 |
| **Budget constraint removed** (proxy for correlated budgets) | **21** |
| Budget removed + move-in 60 days | 40 |

Budget is the whole story: making budgets realistic ~4×'s the yield on its own,
while move-in has to stretch to 90 days just to reach 10. The crude seeder draws
budgets independently and uniformly (`seed.py`), so bands rarely overlap by
chance; real campus users cluster.

**Important — "realistic seed" is synthetic, not real customers.** Cohab has no
real users and is not expected to (PRD §6.6: every profile is synthetic, and
synthetic data *"validates the machine, not the theory"*). Phase 3's "realistic
seed" is simply an upgrade to the `seed.py` generator to draw **correlated**
distributions (budget by area, move-in clustered around term start, templated
notes) — deterministic and reproducible, buildable now, no customers required.

**Decision:** leave the matcher and **all** hard constraints unchanged in Phase 2.
Fix the yield in **Phase 3** by making the synthetic seed correlated, then
re-measure. `MOVE_IN_TOLERANCE_DAYS` (config, not a constant) is the cheap backup
lever if the correlated seed still falls short of 10; scoping the pilot to one
campus/area is the product-level backstop (build plan §3). No config change is
made now — we decide the move-in window against the Phase 3 number.

**What not to do:** do not weaken the real deal-breakers (`gender_preference`,
pets, smoking, city) to inflate the yield. Those exclusions are correct; padding
the number by loosening them just manufactures matches users reject.
