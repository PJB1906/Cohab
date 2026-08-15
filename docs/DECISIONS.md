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

---

## Phase 3 — Realistic seed, tuning, embeddings

### D-3.1 Seed generator upgraded in place, with proposed (not spec-derived) budget tiers

**Spec:** build plan §3/§4 Phase 3 ("upgrade the seeder properly when you
reach tuning"); PRD §6.6 (filter-yield analysis "depends on the *marginal
distributions* of budget, locality and move-in date, which can be modelled
realistically").

**Decision:** `seed.py` was upgraded in place rather than forked into a
parallel module — the crude-seed finding (D-2.5) is already a permanent
record independent of whether the file that produced it still runs, and the
build plan's own wording is "upgrade," not "add a second seeder." Volume
raised from 500 to 1,500 rows (build plan §3: 1,000–2,000 for tuning).

Three correlations were added: **budget by locality** (a latent
`target_locality`, unpersisted for `needs_place` members since v1 filters by
city only — spec §2 — shapes the budget band via `LOCALITY_BUDGET_RANGE`;
`has_place` listings draw rent from the same table); **move-in clustered
around a `TERM_START`** (~70% within ±10 days, echoing PRD §11's "one intake
cohort... four-week window"); and **templated, correlated lifestyle notes**
(composed from `life_stage`/`sociability`/`daytime_presence` fragments so
TF-IDF/embeddings have real signal, instead of five fixed strings).

**The `LOCALITY_BUDGET_RANGE` ₹ figures are proposed, not sourced from any
document** — plausible Bangalore per-person rent tiers, ordered relative to
each other (Koramangala/Indiranagar/HSR pricier than Electronic
City/Marathahalli/etc.), flagged as such in the module docstring. Likewise
the per-attribute `QUESTIONNAIRE_WEIGHTS` (non-uniform but non-degenerate
categorical distributions — spec §11 item 6 specifically warns
`cost_split_preference` must not collapse onto `flexible`) and the light
cross-attribute conditioning (smoking/alcohol tolerance vs behaviour, diet
vs non-veg cooking tolerance, so rows aren't self-contradictory) are
proposed generator design, not spec numbers.

**Code:** `cohab/seed.py`.

### D-3.2 Tuning checkpoint: yield fixed by the correlated seed alone, no config or weight change made

**Spec:** §11's tuning checklist, run via the new `cohab/services/matching/tuning.py`.

**Measured** (60-subject sample, 1,500-profile pool, weight_set v2):

| Check | Result |
|---|---|
| Filter yield | median **34.5** (min 1, max 314) — clears spec §11's 10 and PRD §2's 15 |
| Dominant exclusion | `budget_no_overlap`, as expected once overall yield is healthy |
| Score distribution | 0.518–0.883, 100% inside spec's [0.35, 0.90]; 57% inside [0.70, 0.80] |
| Directional spread | median 0.042; only 26% of pairs near-zero (<0.02) |
| Ablation (`sharing_norm`, `home_orientation`, `sociability`, `cost_split_preference`) | none hit the "never moves the ranking" threshold; `sharing_norm`/`home_orientation` changed the #1 pick for 3/15 and 5/15 sample subjects despite their low weights (0.04, 0.02) |

**Decision:** `MOVE_IN_TOLERANCE_DAYS` stays at **30** — D-2.5 already
identified uncorrelated budgets, not the tolerance window, as the yield
problem; the correlated seed (D-3.1) confirms that diagnosis directly, so
there is nothing left to widen. `weight_set` stays at **v2** — the ablation
gives no clean signal to zero out or reweight any of the four attributes
spec §11 flagged as worth scrutiny; the sample (15 subjects) is also too
small a basis to publish an immutable weight_set version on. Per CLAUDE.md,
this is recorded as a measured-and-considered non-change rather than left
implicit.

**Open, not acted on:** the score distribution's 57% concentration in
[0.70, 0.80], while still within spec's healthy range, is compressed. This
may simply be inherent to a ~20-attribute weighted sum with mostly
gentle-floored matrices (a single bad attribute is diluted across the
whole vector) rather than a defect — flagged for the Phase 9 evaluation
chapter rather than adjusted here.

**Code:** `cohab/services/matching/tuning.py`.

### D-3.3 TF-IDF vs `EmbeddingSimilarity` comparison

**Spec:** §7 (`TfidfSimilarity` in v1, `EmbeddingSimilarity` swapped in "once
the pipeline is proven end-to-end"); PRD §7 ("the comparison between the two
becomes a reportable result").

**Decision:** `EmbeddingSimilarity` (`all-MiniLM-L6-v2`, spec §7/PRD §15)
implements the same `TextSimilarity` protocol as `TfidfSimilarity`, model
loaded lazily so importing the module never requires `sentence-transformers`
or a model download — tests inject a fake encoder (`test_text.py`) and stay
hermetic. `TfidfSimilarity` remains the default powering the main tuning
report (fast, no install risk); `EmbeddingSimilarity` runs only in the
report's isolated comparison section, over a bounded sample of pairs, since
each call is a real transformer forward pass.

**Measured** (150 sampled pairs of profiles with non-empty
`lifestyle_notes`): Pearson r(TF-IDF, embedding) = **0.694** — correlated but
meaningfully different — mean |difference| = **0.301**. The largest
disagreements are paraphrases TF-IDF scores near 0 (no shared vocabulary)
that the embedding model scores 0.6+ (e.g. "working a day job, home most
evenings" vs. "working full-time and keeping fairly regular hours" —
tfidf=0.04, embed=0.61). This is the reportable result PRD §7 asks for:
embeddings catch semantic equivalence TF-IDF structurally cannot, which is
the case for swapping it in once time allows (build plan §2), while TF-IDF
remains the safe v1 default with no install/network dependency.

**Code:** `cohab/services/matching/text.py` (`EmbeddingSimilarity`),
`tests/matching/test_text.py`, `cohab/services/matching/tuning.py` (§7).
