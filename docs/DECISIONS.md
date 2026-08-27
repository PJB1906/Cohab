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

**Resolved in Phase 4:** `kitchen_allergens` (`JSONB NOT NULL DEFAULT '[]'`)
added to `preference_profile`; `Candidate.from_orm` reads it; no change to
`eligibility.py` was needed — the constraint was already correct, just
inert. Confirmed by the Phase 4 matcher-reviewer pass. Still inert on the
*seeded* pool (`cohab/seed.py` never populates it, only `severe_allergy`),
which is fine — it's real only once real profile saves populate it.

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

### D-2.6 Block-aware eligibility filtering exists but has no live caller yet

**Spec:** §2 — neither party may be blocked by the other.

**Status:** `passes_hard_constraints`/`EligibilityFilter` already accept a
`blocked_pairs` param and correctly exclude a pair in either direction
(`eligibility.py`, `Reason.BLOCKED`, unit-tested since this phase) — the
constraint itself is coded and correct. But no live caller passes real block
data into it: `MatchesService.get_matches` (Phase 4) constructs its matcher
with no `blocked_pairs` argument, so the default (`None`) means Stage 1
currently cannot actually exclude a blocked user from anyone's live match
list, even once a `user_block` row exists. `UserBlock` itself has existed in
the schema since Phase 1 but nothing writes to it yet either — there is no
block/report UI or endpoint.

**Not a Phase 2 bug** — this phase's own scope is the constraint logic
against hand-written fixtures, and `eligibility.py`'s own comment already
flagged the gap ("data wired in Phase 7"). Recorded here explicitly, rather
than left as only a code comment, per CLAUDE.md's rule that gaps like this
belong in the running decisions log — found missing from it while reviewing
before the Phase 6 commit.

**Follow-up (Phase 7):** wire a real `blocked_pairs` set (derived from
`UserBlock` rows for the requesting user) into `MatchesService`'s matcher
construction once blocking has a live write path, so the schema-level
guarantee spec §2 requires actually holds at the API layer, not just in the
unit-tested function.

**Resolved in Phase 7 — see D-7.4/D-7.5 below.** `services/safety.py` gives
`UserBlock` its first live write path (`BlockService.block`/`.unblock`, via
`POST`/`DELETE /blocks`), and `MatchesService.get_matches` now sets
`self.ranker.filter.blocked_pairs` from `blocked_pairs_for(session,
subject_user.id)` before ranking — the exact wiring this follow-up asked
for. `get_explanation`/`express_interest` additionally gained a per-pair
`ensure_pair_active` guard, which D-2.6 itself didn't anticipate (it only
scoped Stage 1 filtering) — without it, a pair could still open an existing
`match_id`'s explanation or re-express interest after blocking each other,
even though neither would appear in the other's `GET /matches` any more.
Confirmed by `tests/api/test_matches.py::test_blocked_candidate_excluded_from_matches`,
which (unlike Phase 2's unit tests) exercises the real HTTP path end to end.

**Code:** `cohab/services/matching/eligibility.py` (`Reason.BLOCKED`),
`tests/matching/test_eligibility.py`; `cohab/services/safety.py`,
`cohab/services/matches.py`, `cohab/services/match_access.py`
(`PairBlocked`, `ensure_pair_active`), `cohab/models/safety.py`
(`UserBlock`, now written).

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

### D-3.4 `text_vector`/`text_vector_kind` still unpersisted — first written in Phase 4

**Spec/plan:** CLAUDE.md ("Text embeddings are computed once on profile save
and cached. Never encode inside the match request path"); build plan §4
Phase 4 (profile CRUD).

**Status:** both `TfidfSimilarity` and `EmbeddingSimilarity` are fit and run
**in memory**, at `tuning.py`/`report.py` run time, exactly as Phase 2 left
them. No row anywhere yet writes `text_vector`/`text_vector_kind` to
`preference_profile`. This is correct for Phase 3 — there is no profile-save
endpoint for the cache-on-save rule to attach to — but it means the rule is
still unimplemented, not just untested, and Phase 4's profile-save handler
has to write this cache for the first time rather than merely wire an
existing path.

**Code:** `cohab/services/matching/text.py`; not yet: `cohab/api/` (Phase 4),
`cohab/models/preference_profile.py`.

**Resolved in Phase 4 — see D-4.4 below for the write *and* read side.** The
write side alone (populating the columns) would have left the rule cosmetic;
D-4.4 records why the scorer had to change too.

---

## Phase 4 — Auth, verification, profile/listing CRUD, matches API

### D-4.1 `seeker_type` and `gender` collected at registration, not a separate post-verification step

**Spec:** PRD §8.1's onboarding sequence diagram shows seeker-type
declaration as its own screen, after OTP verification and before the
questionnaire.

**Gap:** the Phase 1 schema has `user.seeker_type` `NOT NULL` with no
default (`models/user.py`), so a literal reading of the diagram needs a
migration to make it nullable, plus a new `PATCH` endpoint for the
standalone step. `gender` is `NOT NULL` too, with no screen in PRD §9 that
collects it at all.

**Decision (confirmed with the user, Phase 4 planning):** both are collected
in `POST /auth/register` alongside email/name/password, not as a separate
step. Treats the PRD sequence diagram as a simplification rather than a
literal contract — consistent with how `gender` already has to be collected
up front for the identical structural reason, and avoids a nullable-column
migration for a workflow difference with no scoring consequence (Stage 1/2
only ever read the final, settled value).

**Code:** `cohab/services/auth.py` (`AuthService.register`), `cohab/api/schemas.py`
(`RegisterRequest`).

### D-4.2 Listing CRUD built in Phase 4, extending the build plan's "profile CRUD" bullet

**Spec:** build plan §4 Phase 4 lists "profile CRUD" only; `listing` is a
separate entity (PRD §5.2).

**Decision (confirmed with the user, Phase 4 planning):** `GET/PUT /listing`
ships alongside `GET/PUT /profile` in this phase, not deferred to Phase 5.
Without it a `has_place` user has no way to reach the state
`Candidate.from_orm` needs (it reads `user.listing` for the effective budget
band, `candidate.py`) — `has_place` would be a structurally dead seeker type
in the API surface this phase ships. Listing CRUD is a small, independent
addition (an 8-column table, no scoring logic) so pulling it forward costs
little.

**Code:** `cohab/services/listing.py`, `cohab/api/listing.py`.

### D-4.3 Institution resolution by email-domain suffix, not exact equality

**Spec:** not specified — `institution.email_domain` (PRD §5.2) is a bare
string with no stated matching rule.

**Decision (confirmed with the user, Phase 4 planning):** the part of an
email after `@` resolves to an institution if it equals `email_domain` *or*
ends with `"." + email_domain`, so a departmental subdomain
(`msds.christuniversity.in`) resolves to the `christuniversity.in` row. Real
institutional addresses carry a department subdomain; exact-match alone
would reject genuine institutional accounts.

**Code:** `cohab/services/auth.py` (`_resolve_institution`),
`tests/api/test_auth.py::test_register_rejects_subdomain_of_a_registered_domain`.

### D-4.4 Wiring the text-vector cache into scoring — the read side, not just the write side

**Spec:** CLAUDE.md / spec §7: "computed at profile save and cached. Never
encode inside the match request path." D-3.4 flagged that neither the write
nor the read side existed yet.

**Decision:** closing this required three coordinated changes, not one:

1. **Write side.** A single `TfidfSimilarity` is fit **once per process**, at
   FastAPI startup, over whatever `lifestyle_notes` exist in the DB at that
   moment (`cohab/main.py` lifespan handler). `TfidfSimilarity.encode(text)`
   (transform-only, no fit) populates `text_vector`/`text_vector_kind` on
   every `PUT /profile`. New vocabulary appearing after that startup is
   out-of-vocabulary until the next restart — a documented limitation, not a
   bug; a periodic refit is Phase-8-shaped work (alongside the weight-set
   recompute job already noted there), not built now.
2. **Read side.** Before this phase, `attributes.py`'s `_notes` scorer always
   called `ctx.text_similarity.similarity(raw_a, raw_b)` — a live transform of
   raw text — regardless of whether a cache existed, because nothing ever
   populated the cache to prefer. It now prefers cosine over the two
   candidates' cached `text_vector`s (`matrices.vector_cosine_similarity`,
   new) when both sides carry one of the same `text_vector_kind`, and only
   falls back to the raw-text transform when a cache is missing or the kinds
   differ (covers pool members saved before this feature, and keeps
   `report.py`/`tuning.py`'s whole-pool offline fitting working unchanged).
   Without this half, the cache columns would have been written but never
   read — cosmetic, not load-bearing (matcher-reviewer finding).
3. **Live API never falls back to a live transform.** The `_notes` fallback
   still calls into a `TextSimilarity`, and the live API deliberately wires
   that fallback to `NeutralTextSimilarity()` rather than the shared
   `TfidfSimilarity` instance (`cohab/api/matches.py`). With every `PUT
   /profile` now populating the cache, the only remaining callers of a live
   raw-text transform are the offline `report.py`/`tuning.py` scripts, which
   fit their own pool-scoped vectorizer per run — that's correct there and
   would be the one live-request-path encode this whole change was meant to
   remove if it weren't kept neutral instead.

**Two related robustness fixes made while wiring this** (matcher-reviewer
findings): `TfidfSimilarity.similarity()` used to raise `RuntimeError` if
called before `.fit()`; it now degrades to the neutral score, since an unfit
vectorizer is reachable live-API state (a brand-new, near-empty pilot
database) and not only a caller bug. `vector_cosine_similarity` degrades to
neutral on a vector-length mismatch rather than raising, since two `tfidf`
vectors cached under vectorizers fit in different process lifetimes (a
server restart) can legitimately have different vocabulary sizes despite
sharing the `"tfidf"` kind tag.

**Code:** `cohab/main.py`, `cohab/services/matching/text.py`,
`cohab/services/matching/matrices.py` (`vector_cosine_similarity`),
`cohab/services/matching/attributes.py` (`_notes`), `cohab/api/matches.py`.

### D-4.5 OTP storage shape and delivery

**Spec:** PRD §8.1 names the flow (`POST /auth/register` → email OTP →
`POST /auth/verify`) but not the storage or hashing scheme; build plan §4
says "email-OTP verification."

**Decision:** `verification_record` gained `otp_hash`, `otp_expires_at`,
`otp_attempts` (migration `1221949ea658`). The OTP is hashed with
HMAC-SHA256 keyed on `SECRET_KEY`, not `bcrypt` — deliberately a different,
cheaper primitive than password hashing: a 6-digit code is short-lived
(`OTP_TTL_MINUTES`, proposed: 10) and rate-limited (`OTP_MAX_ATTEMPTS`,
proposed: 5), so the actual defence is the attempt cap, not hash cost.
Delivery goes through an `OTPSender` protocol (mirroring `TextSimilarity`'s
swap-behind-an-interface pattern) with `ConsoleOTPSender` — logs the code —
as the only implementation: this project has no SMTP credentials configured,
so a real email sender is a documented future swap-in. `SESSION_TTL_DAYS`
(14), `OTP_LENGTH` (6) are likewise proposed values, not sourced from any
document.

**Code:** `cohab/core/config.py`, `cohab/core/security.py`,
`cohab/services/otp.py`, `cohab/services/auth.py`, migration
`1221949ea658_phase_4_auth_fields.py`.

### D-4.6 `match_score` upsert-on-read, and the reproducibility question it defers

**Spec:** PRD §7.1 Stage A ("compute on read... no caching") describes the
scoring architecture; PRD §8.1's onboarding sequence diagram separately shows
`M->>DB: Persist match scores` after scoring. The two aren't the same
instruction and this phase had to reconcile them.

**Decision:** `GET /matches` still recomputes Stage 1 + Stage 2 fresh on
every call (Stage A, cheap at pilot pool sizes) but **upserts** a
`match_score` row per eligible pair rather than leaving the table empty: a
row is required for `GET /matches/{id}/explanation` to have something stable
to read and for `state`/`interested_by_*` to have somewhere to live (PRD
§8.2's lifecycle). The upsert refreshes score/breakdown/`weight_set_id` but
never touches `state` or `interested_by_*`, so a rescore can't silently erase
a user's recorded interest.

Because `MatchRanker.rank()` always scores with `a=subject` but
`match_score` requires canonical `user_id_a < user_id_b` storage (PRD §5.2:
`CHECK (user_id_a < user_id_b)`, one row per unordered pair), a new pure
function `flip()` (`cohab/services/matching/canonical.py`) rearranges an
already-computed `MatchResult` — scores, and each breakdown cell's
`sim_a/sim_b` and `w_a/w_b` — into the other party's viewpoint. It's used
both to canonicalise a result before storage and to reconstruct a stored
row from whichever party didn't originally request the score. Matcher-reviewer
verified `flip` is correct for every attribute type the matcher produces
(similarity/tolerance/absolute/continuous/semantic) and is its own inverse.

**Left open, not solved here:** always-refresh-on-read is only safe while a
single `weight_set` is active. CLAUDE.md's immutability guarantee — an
explanation shown once must remain reproducible — has nothing to violate yet
because Phase 8 hasn't published a second `weight_set` version. Once it does,
unconditionally overwriting a `viewed`-or-later row's `breakdown` on every
`GET /matches` would retroactively change an explanation a user has already
seen, which is exactly what immutability forbids. Revisit then: candidates are
"never refresh past `state='suggested'`" or "always refresh, but keep a
version history instead of overwriting." Not decided now because there is no
evidence yet to decide between them — Phase 8's own recompute-job design is
where that evidence will exist.

`GET /matches`'s default `limit=10` is a proposed value — neither PRD nor
spec sets one; PRD's `rank_matches(user, limit)` signature (§7.1) takes it
as caller-supplied with no default given.

**Code:** `cohab/services/matching/canonical.py`, `cohab/services/matches.py`,
`cohab/api/matches.py`, `tests/matching/test_canonical.py`,
`tests/api/test_matches.py`.

---

## Phase 5 — Core UI

### D-5.1 §13 wireframe reference resolved to PRD §9 + the two root-level mockups

**Spec:** build plan §4 Phase 5 says "Follow the §13 wireframes and the
desktop/mobile mockups." The PRD's current §13 is "Open questions", not
wireframes — the screen table is §9.

**Decision:** treated PRD §9 (screens 1–8) as the authoritative content
contract for this phase, and `Cohab Desktop.html` / `Cohab Prototype.html`
(bundled Claude-artifact exports at the repo root, decompressed to read —
gzip+base64 JS payloads, not plain HTML) as the visual/interaction
reference. Both mockups encode `COHAB_MATCHING_SPEC.md` §3/§10 almost
verbatim (the 12 conflict questions and the "Worth discussing" divergence
copy match word-for-word), confirming they were built from that document.

**Two content gaps found in both mockups, resolved rather than copied:**
1. Neither mockup asks a `needs_place` user for budget, move-in date, gender
   preference, pets, allergies, or the smoking dealbreaker — all Stage-1
   hard constraints (spec §2) that `PUT /profile` requires, and which the
   `has_place` listing screen collects but nothing else does. Resolved by
   giving the required-questionnaire screen a preamble section ("Where and
   when are you looking") ahead of the 12 conflict questions. `city` stays
   fixed to the schema default (`"Bangalore"`) and isn't user-facing —
   single-campus pilot, PRD §3.1.
2. Signup mockups collect name/email/phone only, then a *separate* screen
   after OTP verification for seeker type, and never collect `gender`. This
   contradicts **D-4.1**: `gender`/`seeker_type` are collected in
   `POST /auth/register` itself. Resolved by making sign-up a short wizard —
   pick "I need a place"/"I have a place" first, then name/email/gender
   /password, then OTP — one `POST /auth/register` call at the end.
3. Both mockups show a header "Chat" link and an "Open chat" button on match
   detail. Chat (`services/chat.py`, `api/chat.py`) does not exist yet —
   only its table (`models/chat.py`) was pre-designed in Phase 1. Omitted
   from this phase's UI entirely rather than linking to nothing; match
   detail's only action is "Express interest".
4. Spec §3 Q12 says the alcohol sub-question is "same structure" as smoking
   but gives no alcohol-specific labels, and `matrices.py`'s `alcohol`
   tolerance matrix already reuses smoking's exact option codes
   (`none`/`outside`/`indoors`, `fine`/`outside_ok`/`smoke_free`). The
   questionnaire screen writes parallel display labels for those same codes
   applied to drinking — proposed copy, not spec text.

**Code:** `frontend/src/features/auth/`, `frontend/src/features/onboarding/`.

### D-5.2 Three small, additive API extensions, confirmed with the user

**Gap:** building the match-list and match-detail screens against the
Phase 4 API surface exposed three real holes: no way to restore a session on
page refresh, no endpoint for match detail's required "express interest"
action (PRD §9 row 8), and `MatchListItem`/`MatchExplanationResponse` didn't
carry the candidate's listing summary PRD §9 row 8 also requires ("listing
if applicable").

**Decision (confirmed with the user):** closed all three in this phase
rather than shipping dead UI elements or deferring to Phase 6:
- `GET /auth/me` — thin passthrough of the existing `get_current_user`
  dependency.
- `POST /matches/{id}/interest` — `MatchesService.express_interest` sets
  whichever `interested_by_a`/`interested_by_b` flag is the caller's side
  (reusing the same `user_id_a < user_id_b` canonical ordering as
  `_upsert`), and transitions `state`: `suggested`/`viewed` → `interested`;
  both flags set → `mutual` (PRD §8.2). No new columns — `MatchScore` has
  carried both since Phase 1 and nothing had ever written to them. Only
  models the two transitions anything in this phase can produce; there's no
  reject/expire endpoint yet, so the rest of the lifecycle isn't simulated.
- `MatchListItem` gained `seeker_type`/`city`/`budget_min`/`budget_max`
  /`avatar_url` (already on `Candidate`, zero extra query cost).
  `MatchExplanationResponse` gained `state`, `candidate_course`,
  `candidate_avatar_url`, and an optional `listing` block populated from the
  candidate's `Listing` row when `seeker_type == "has_place"`.

**Code:** `cohab/api/auth.py` (`GET /me`), `cohab/services/matches.py`
(`express_interest`, `MatchExplanationResult.listing`/`.state`),
`cohab/api/matches.py`, `cohab/api/schemas.py` (`MatchListingSummary`,
`ExpressInterestResponse`), `tests/api/test_auth.py`,
`tests/api/test_matches.py`.

### D-5.3 Photo uploads, added mid-phase per user feedback — local disk, no object store

**Gap:** neither a profile-photo field nor a working way to populate
`Listing.photos` existed. Raised during this phase's plan review; the user
asked for both a property/listing and a profile photo.

**Decision:** no object-storage service exists anywhere in this stack, and
CLAUDE.md already defers Redis on "no new infra the pilot doesn't need"
grounds — same reasoning applied here rather than introducing S3/Cloudinary.
Uploads land on local disk under `UPLOAD_DIR` (default `backend/uploads/`,
gitignored), served back through a `/media` `StaticFiles` mount. Flagged as
a build-time choice, not spec-sourced; swapping in real object storage is a
documented future step if this goes past pilot scale.

`POST /uploads/image` takes `kind: "avatar" | "listing"`. `kind="avatar"`
writes `user.avatar_url` immediately in the same call — an avatar isn't part
of the onboarding wizard's single-`PUT /profile` batch, so applying it on
upload is simpler than holding it in client state. `kind="listing"` only
returns the URL; the frontend holds it in its listing draft and saves it
with the existing `PUT /listing`. Validates content-type (`jpeg`/`png`
/`webp`) and a proposed 5 MB cap; no resizing/thumbnailing — a documented
gap, not built for the pilot. `user.avatar_url` is a new nullable column
(migration `1298c43d216d`); `Listing.photos` already existed (Phase 1) and
needed no schema change, only a way to populate it.

**Code:** `cohab/services/uploads.py`, `cohab/api/uploads.py`,
`cohab/core/config.py` (`UPLOAD_DIR`, `MAX_UPLOAD_MB`), `cohab/main.py`
(`/media` mount), `cohab/models/user.py` (`avatar_url`),
`cohab/services/matching/candidate.py` (`avatar_url`/`course` passthrough),
migration `1298c43d216d_phase_5_avatar_url.py`, `tests/api/test_uploads.py`.

### D-5.4 Importance-weighting tile set corrected against the real attribute registry

**Gap:** the Desktop mockup's screen-6 tile set (`WT` array) uses display
ids (`cleanliness`, `payment`, `chores`, `communication`, `split`) that
don't match any real `weight_set` attribute name — `PUT /profile` validates
`important_attributes` against `attributes.py`'s `ATTRIBUTES` registry
(`cleanliness_level`, `payment_reliability`, `chore_approach`,
`communication_style`, `cost_split_preference`), so the mockup's ids would
have 400'd. Worse, its "Smoking and alcohol" tile only ever sends
`smoking` — `alcohol` (a distinct, separately-weighted spec §8 attribute)
has no tile at all, and neither does `sleep_schedule` despite being one of
the largest Tier 1 weights (0.09).

**Decision:** rebuilt the tile set from `attributes.py`'s registry directly:
all of Tier 1 except `budget_proximity` (already enforced as a hard
constraint — not a meaningful "priority" to weight separately) plus
`life_stage` and `sociability` from Tier 2 — 15 tiles, every id a real,
independently-selectable attribute name.

**Code:** `frontend/src/data/questionnaire.ts` (`WEIGHT_TILES`).

### D-5.5 Full attribute breakdown shows scores, not raw answers

**Gap:** the mockups' match-detail breakdown table has a "You" / "[Name]"
column pair showing each side's actual questionnaire answer alongside the
score. `GET /matches/{id}/explanation`'s `breakdown` field only ever
carried `{sim_a, sim_b}` per attribute (COHAB_MATCHING_SPEC.md §9) — never
either party's raw answer. That level of detail exists only for the
top-3-agreements-plus-1-divergence the API already renders as finished
sentences (`agreements`/`divergence`, D-2.3).

**Decision:** the full breakdown renders attribute name + type (a static
lookup mirroring `attributes.py`, not per-user data) + the directional
scores, with a note when `sim_a`/`sim_b` diverge by more than 0.15 — real
data throughout, rather than fabricating plausible-looking "you said X"
values the API was never asked to expose. Extending the API to carry raw
answers is a larger, privacy-relevant decision (should a candidate's exact
answer to every question be visible, or only the ones already selected for
agreement/divergence copy?) left for a future phase, not decided here.

**Code:** `frontend/src/data/attributes.ts`, `frontend/src/components/AttributeRow.tsx`.

### D-5.6 `ConsoleOTPSender`'s output was silently going nowhere outside pytest

**Found while verifying this phase's UI end-to-end in a real browser** (not
just against `TestClient`, where pytest's `caplog` force-captures log
records regardless of level). `ConsoleOTPSender.send()` (`services/otp.py`)
logs the OTP via `logging.getLogger("cohab.otp").info(...)`, but nothing in
the app ever configured the root logger — `uvicorn`'s default logging setup
only attaches handlers to its own `uvicorn`/`uvicorn.error`/`uvicorn.access`
loggers, not root. Confirmed live: `curl`-triggering `POST /auth/register`
against a plain `uvicorn cohab.main:app` produced the access-log line but no
OTP line anywhere. The registration flow was unusable outside the test
suite since Phase 4 — masked because Phase 4 had no browser-based
verification step to surface it.

**Decision:** `cohab/main.py` now calls `logging.basicConfig(level=logging.INFO,
format="%(name)s: %(message)s")` at import time, giving the root logger a
handler before `cohab.otp` (or any other app logger) ever fires. Minimal,
standard-library fix — no new dependency, no change to `ConsoleOTPSender`
itself, which was already correct.

**Code:** `cohab/main.py`.

---

## Phase 6 — Chat and contact sharing

### D-6.1 `user.phone_number` added at registration — a schema gap `contact_share` needed closed

**Spec:** PRD §9 screen 1 ("States plainly that the phone number stays
private until both parties opt in"); §10 ("Phone numbers and addresses are
absent from every response until two consent rows exist").

**Gap:** no phone-number field existed anywhere in the schema — not on
`User`, not on `preference_profile` — despite `contact_share` (built Phase
1, unused until now) existing specifically to reveal one. Missed in Phases
1/4/5 because nothing exercised the reveal path until this phase.

**Decision (confirmed with the user, Phase 6 planning):** `user.phone_number`
(nullable `String`, migration `1eac5ce1061c`), collected in
`POST /auth/register` alongside `gender`/`seeker_type`/`course` — same
precedent as D-4.1, and the field a real user already sees privacy language
about at sign-up (PRD screen 1). Optional at the schema level (mirrors
`course`) so existing seeded/test accounts without one don't need a backfill.

**Code:** `cohab/models/user.py`, `cohab/api/schemas.py`
(`RegisterRequest`/`UserOut`), `cohab/services/auth.py`,
`frontend/src/features/auth/SignUpWizard.tsx`, migration
`1eac5ce1061c_phase_6_phone_number.py`.

### D-6.2 Chat encryption at rest implements what Phase 1 flagged as deferred

**Spec:** PRD §10: "Chat is encrypted at rest under a server-held key, and
is not end-to-end encrypted." `models/chat.py`'s `Message.body_encrypted`
carried a comment since Phase 1 saying plaintext was fine for then because
"the encryption mechanism is a Phase 6 concern."

**Decision:** `Fernet` (symmetric, authenticated) keyed by
`sha256(SECRET_KEY)` — same reasoning as D-4.5's OTP HMAC: this app has
exactly one server-held secret already required at deploy time, and
standing up separate key-management infra for a pilot is what CLAUDE.md's
Redis-deferral logic argues against generally. New dependency:
`cryptography` (not pulled in transitively by `pyjwt`/`bcrypt`, which don't
need it for HS256/bcrypt). PII detection and abuse flagging run on plaintext
before encryption, obviously — only the stored `body_encrypted` column is
ciphertext.

**Code:** `cohab/core/crypto.py`, `cohab/services/chat.py`,
`tests/core/test_crypto.py`.

### D-6.3 PII detection interrupts the send; abuse flagging never does

**Spec:** PRD §9.1's own wording contrasts the two: item 1 (PII) says
"interrupt" the send; item 2 (abuse) says "flag for review; does not block
outright, to avoid suppressing legitimate conversation."

**Decision:** `ChatService.send_message` raises `PIIDetected` **before**
persisting anything when a phone number/email/handle is detected and the
pair hasn't fully exchanged contact yet (item 1's own qualifier: "before
`contact_share` consent exists"); the API returns a 422 with a structured
`{"detail": "pii_detected", "message": "..."}` body rather than a plain
string, and the frontend renders a dialog with "Edit," "Use Share Contact
instead," and "Send anyway" (`confirm: true` resend) rather than silently
sending or hard-blocking forever — the PRD's warning copy is a redirect, not
an absolute prohibition, and a false positive (e.g. "call me at the leasing
office ext. 4021") needs an escape hatch. Abuse content, by contrast, is
always persisted with `flagged=True` for Phase 7's moderation queue and
never blocks. Both `flagged`/`pii_detected` are deliberately excluded from
`MessageOut` — internal moderation signals, not shown to the user whose
message it is.

**Code:** `cohab/services/pii.py` (regex heuristic — phone/email/handle,
documented as MVP-not-exhaustive, same framing as `TfidfSimilarity`),
`cohab/services/moderation.py` (`KeywordAbuseFlagger`, same
swap-behind-a-protocol pattern as `TextSimilarity`/`OTPSender`),
`cohab/services/chat.py`, `cohab/api/chat.py`, `cohab/api/schemas.py`
(`MessageOut`), `frontend/src/api/chat.ts`
(`PiiInterruptError`), `frontend/src/features/chat/ChatThread.tsx`.

### D-6.4 A chat "thread" is a state flip on `match_score`, not a new entity; rate limits are DB-query-based

**Spec:** PRD §8.2's lifecycle (Mutual → Chatting: "thread created");
§9.1 item 3 (rate limits, "the mechanical precondition for both spam and
harassment").

**Decision:** `message.match_score_id` already ties every message to an
unordered pair (Phase 1 schema) — PRD's "thread created" transition is
modelled as `mutual → chatting` flipping on first chat access
(`ChatService`'s `_open_thread`), not a row insert into a new table. Rate
limits (`CHAT_RATE_LIMIT_PER_ACCOUNT_PER_MIN` / `..._PER_THREAD_PER_MIN`,
proposed values, not spec-sourced) are enforced by counting `Message` rows
created in the last 60 seconds via an indexed query, not an in-process
dict — CLAUDE.md's single-uvicorn-worker pilot note already flags in-process
state as the thing that breaks first when scaling past one worker, and a DB
count costs nothing extra here since every send already writes a row.
`is_read` flips as a side effect of `GET /chat/{id}/messages` (whoever
fetches marks the other party's messages read) rather than a separate
endpoint — PRD's own estimate for this feature is "roughly a hundred
lines," and no read-receipt UI is speced for v1.

**Code:** `cohab/services/chat.py`, `cohab/services/contact_share.py`,
`cohab/core/config.py`.

### D-6.5 `you_expressed_interest` — found live, blocked the entire Mutual path in the UI

**Found while manually verifying this phase in a real two-account browser
session** (CLAUDE.md's UI-testing rule — same category of bug as D-5.6,
invisible to `TestClient`-only coverage). `MatchDetail.tsx`'s "already
expressed interest" check read the shared `MatchScore.state`
(`state !== 'suggested' && state !== 'viewed'`) rather than a per-viewer
flag. `state` flips to `"interested"` as soon as *either* party clicks —
so the *second* party's own "Express interest" button rendered as
"Interest sent" and disabled **before they had ever clicked it**. A match
could reach `Mutual` through the API (the existing
`test_express_interest_both_sides_transitions_to_mutual` covered that path
and passed), but never through the live UI, since the second party had no
way to register their own interest.

**Decision:** `GET /matches/{id}/explanation` now returns
`you_expressed_interest` — `row.interested_by_a`/`_b` resolved to whichever
side the caller is — and `MatchDetail.tsx` uses that instead of inferring
from `state`. `state` is still what gates chat availability (`canChat`),
which is correctly a shared, not per-viewer, concept.

**Also found in the same verification pass:** `ApiError`'s constructor
passed the server's `detail` field straight to `Error`'s `message`
parameter, which the JS `Error` constructor ToString-coerces — a plain
object (this phase's structured PII-interrupt body) silently became the
string `"[object Object]"`, so the frontend's PII-detection branch
(`isPiiWarning(err.message)`) never matched and the interrupt dialog never
rendered, even though the backend was correctly blocking the send (confirmed
independently via `tests/api/test_chat.py` and a direct server-side message
count during the live repro). Fixed by giving `ApiError` a second field,
`detail`, carrying the raw pre-coercion value for callers that need to
branch on structure; `message` is unchanged for the plain-string case every
other caller in the app already relies on.

**Code:** `cohab/services/matches.py` (`MatchExplanationResult
.you_expressed_interest`), `cohab/api/schemas.py`
(`MatchExplanationResponse`), `cohab/api/matches.py`,
`frontend/src/features/matches/MatchDetail.tsx`,
`frontend/src/api/client.ts` (`ApiError.detail`), `frontend/src/api/chat.ts`,
`tests/api/test_matches.py`
(`test_you_expressed_interest_is_per_viewer_not_shared_state`).

### D-6.6 Pre-commit review pass — six more findings, all fixed

**Requested by the user** before committing Phase 6 ("is there any bugs,
inconsistency, lack of feature or anything left"). A `/code-review high`
pass over the diff surfaced ten findings; four were judged non-issues at
pilot scale and left as-is (documented below), six were real and fixed:

1. **Abuse/PII regexes matched as unanchored substrings.** `rape` matched
   inside "grapes"/"therapeutic"; `insta` matched inside
   "instantly"/"instance". Both would have silently mis-flagged or
   mis-blocked ordinary sentences. Fixed with `\b` word-boundary anchors
   (`moderation.py`) and a redesigned handle pattern that requires either a
   whole-word app mention or an actual `/`/`:` separator before a handle
   (`pii.py`). New regression cases in `tests/test_moderation.py`/
   `tests/test_pii.py`.
2. **`express_interest` could regress state past Mutual.** No guard
   stopped a replayed `POST /matches/{id}/interest` (stale tab, client
   retry) from resetting `state` back to `"mutual"` even after the pair had
   already reached `chatting`/`contact_shared`. Fixed by only setting
   `mutual` when the current state hasn't already passed it. New test:
   `test_express_interest_replay_does_not_regress_state_past_mutual`.
3. **`decrypt_message`'s `ValueError` was uncaught in `list_messages`.** A
   corrupted row or rotated `SECRET_KEY` would 500 the whole thread — after
   the `is_read`/state mutations for that call had already committed.
   Fixed with `_safe_decrypt`, substituting a placeholder string per
   message rather than failing the request.
4. **Three parallel copies of "load a `MatchScore`, verify the caller is a
   party" existed** (`services/matches.py`, `services/chat.py`,
   `services/contact_share.py`), each with its own `MatchNotFound`/
   `NotAParty` pair — `api/chat.py` had to alias-import two of the three
   just to avoid a name collision. Consolidated `chat.py` and
   `contact_share.py` (the two Phase 6 files) onto one shared
   `services/match_access.py`; `services/matches.py` (Phase 4) is left
   independent — out of this phase's scope to retouch, and not itself part
   of this diff.
5. **`ContactShare.tsx` rendered a blank value** when both parties had
   consented but the other party had never set a phone number (nullable
   since D-6.1, e.g. older seeded accounts). Fixed with an explicit "They
   haven't added a phone number yet" fallback.
6. **`chat.py`'s module docstring slightly overclaimed REST-only
   permanence** ("REST polling is the only transport"), when CLAUDE.md's
   actual framing is that WebSocket is a documented later upgrade "once
   polling latency measurably degrades the experience" — a mis-sourced
   claim, not just imprecise wording (CLAUDE.md itself forbids "presenting
   an invented value as specified"). Reworded to match; documentation-only,
   no behaviour change.

**Left as-is, judged non-issues at this scale, not fixed:**
- Rate-limit check has a TOCTOU race under truly concurrent double-submits
  from the same sender — bypasses a soft 20/min cap by at most one message;
  not worth row-locking complexity for a pilot's generous headroom limit.
  Revisit if this ever moves past a single low-traffic pilot instance.
- `mutual -> chatting` flipping as a side effect of `GET
  /chat/{id}/messages` — raised as a REST-purity concern, but it's the
  identical, already-accepted pattern `GET /matches/{id}/explanation` uses
  for `suggested -> viewed` (D-4.6). Consistent with established
  convention; not planned to change.
- Polling refetches full message history every 3s without using the
  `since` param the endpoint already supports — real inefficiency at scale,
  but trivial cost for a pilot's per-thread message counts; adding
  incremental-merge complexity now would be designing for load that
  doesn't exist yet. Revisit alongside any future WebSocket work.

**Code:** `cohab/services/moderation.py`, `cohab/services/pii.py`,
`cohab/services/matches.py`, `cohab/services/chat.py`,
`cohab/services/contact_share.py`, `cohab/services/match_access.py` (new),
`cohab/api/chat.py`, `frontend/src/features/chat/ContactShare.tsx`,
`tests/test_pii.py`, `tests/test_moderation.py`,
`tests/api/test_matches.py`.

---

## Phase 7 — Safety and moderation

### D-7.1 Moderator auth is a flag on the caller's own account, not a second login flow

**Spec:** build plan §4 Phase 7 ("moderator admin view"); PRD §9 screen 13
("Moderator queue"). Neither names an auth mechanism — `moderator`
(`name`/`email`, no password) has existed since Phase 1 with no login path,
and `report.assigned_moderator_id` already FKs to it.

**Decision (confirmed with the user, Phase 7 planning):** `user.is_moderator`
(`Boolean NOT NULL DEFAULT false`) gates a new `require_moderator` dependency
(`api/deps.py`), layered on top of the existing `require_verified_user` — so
a moderator authenticates with the exact same session cookie as everyone
else. `moderator` is kept as the reviewer/audit entity `report
.assigned_moderator_id` already pointed at, given a new `user_id` FK
(`UNIQUE`, `NOT NULL` — the table has had no writer since Phase 1, so this
is safe with no backfill) so it's linked to a real account rather than a
freestanding name/email pair. `get_or_create_moderator` resolves — and, on
first use, creates — the caller's own `Moderator` row from their `User`
record, so there's no separate provisioning step beyond flipping the flag.
The alternative (a distinct `moderator.password_hash` and a second
`POST /moderation/login`) was rejected as doubling the auth surface for a
pilot with a handful of moderators, all of whom are already platform users.

**Code:** `cohab/models/user.py` (`is_moderator`), `cohab/models/safety.py`
(`Moderator.user_id`), `cohab/api/deps.py` (`require_moderator`),
`cohab/services/moderation_queue.py` (`get_or_create_moderator`), migration
`4b7c9f2a1d63_phase_7_safety.py`.

### D-7.2 Full PRD §8.3 report policy, not just CRUD + the state machine

**Spec:** PRD §8.3 ("This corrects the SRS...") lists four automations
beyond report CRUD and the `Open -> UnderReview -> Substantiated/Dismissed
-> ActionTaken` state machine: reports alleging threats/sexual harassment
escalate immediately and may suspend pending review; three or more
independent reports from unconnected users auto-suspend; report submission
is rate limited; repeated reports by one user against the same person
collapse into a single case.

**Decision (confirmed with the user, Phase 7 planning):** build the
complete policy this phase rather than deferring the automations. All four
live in `ReportService.file_report` (`services/safety.py`):

- **Duplicate collapse.** An existing `open`/`under_review` report from the
  same reporter against the same target is updated in place (`reason`,
  `details` overwritten with the new filing) rather than inserted as a
  second row — the same plain-overwrite "upsert" precedent as
  `MatchesService._upsert` (D-4.6), not an append/merge of the two
  filings' text. Only `open`/`under_review` collapse; a report that's
  already been through review is a closed case, and a fresh filing after
  that is treated as a new incident.
- **Escalation.** `ESCALATING_REASONS = (harassment, threats,
  sexual_harassment)` — PRD names the latter two; `harassment` is added to
  the pair, flagged here as proposed rather than spec text, since a
  plain-language harassment allegation is the same order of urgency and
  screen 11 gives no separate, narrower category for it. Escalating a
  report sets `escalated=True` and suspends the reported user
  (`account_status: active -> suspended`) immediately. Escalation is
  **monotonic** — a later, calmer duplicate filing from the same reporter
  never un-escalates an already-escalated case.
- **Volume auto-suspend.** `REPORT_AUTOSUSPEND_THRESHOLD = 3` — the one
  number PRD §8.3 actually gives ("three or more"). The count is of
  **distinct `reporter_id`s** with a report against the target whose status
  isn't `dismissed` (open/under_review/substantiated/action_taken all
  count; a report a moderator already reviewed and rejected shouldn't keep
  counting as evidence). PRD's "unconnected users" has no relationship
  graph in this schema to check against — distinct reporters is the honest
  proxy, not a literal implementation of "unconnected," and is recorded
  here as such rather than silently approximated.
- **Rate limit.** `REPORT_RATE_LIMIT_PER_DAY = 5` — proposed, not
  spec-sourced (PRD only says "rate limited"). Counts the reporter's own
  reports in the last 24h; a duplicate-collapse update doesn't consume the
  cap (only genuinely new cases do), so a reporter can always add detail to
  a case they've already opened.

Both suspend paths (escalation, volume) route through one `_maybe_suspend`
helper that only ever moves `active -> suspended` — it never downgrades an
existing `banned` sanction, and is a no-op if the account is already
suspended, so filing an *n*-th report against an already-actioned user is
harmless.

**Code:** `cohab/services/safety.py`, `cohab/core/config.py`
(`REPORT_RATE_LIMIT_PER_DAY`, `REPORT_AUTOSUSPEND_THRESHOLD`),
`cohab/models/safety.py` (`REPORT_REASONS`, `ESCALATING_REASONS`),
`tests/api/test_reports.py`.

### D-7.3 Finding and sanction recorded separately; a "pending review" suspension is provisional

**Spec:** PRD §8.3: "Finding and sanction are recorded separately, so the
audit trail shows what was concluded as well as what was done."

**Decision:** `Report.status` (already `substantiated`/`dismissed`
/`action_taken` since Phase 1) carries the **finding**; a new
`Report.sanction` column (`warn`/`suspend`/`ban`, nullable) carries the
**sanction**, set only on `action_taken` and left `NULL` on `dismissed`.
`ModerationService.resolve` requires a sanction whenever the finding is
`substantiated` (`SanctionRequired` otherwise) — `warn` is record-only
(no `account_status` change); `suspend`/`ban` write straight to
`account_status`.

**A gap found while writing this, not in the original plan:** PRD's own
wording for escalation is "may suspend **pending review**" — which implies
the suspension is provisional on the outcome of that review, not a
standing sanction. Without handling this, a report that turns out to be
groundless (`dismissed`) would leave its target permanently suspended with
no code path back to `active`, which is a real correctness bug, not a
nuance to defer. `ModerationService._maybe_reactivate` closes it: on
`dismissed`, if the reported user's account is `suspended` (never touches
`banned` — a concluded sanction, not a pending one) **and** no other
`open`/`under_review` report remains against them, it reactivates to
`active`. Left deliberately narrow — it only ever reads `account_status`
and other `Report` rows, never a report's own history, so it can't
misfire based on stale state from an unrelated case.

**Also decided while implementing `resolve`:** the method takes the calling
moderator as a parameter but, in an early draft, never used it — any
moderator could resolve any claimed report, not just the one who claimed
it. Reconsidered as a real gap rather than dropping the unused parameter:
claiming assigns responsibility for a case (PRD §8.3's own "moderator
claims"), and letting a second moderator close it out from under the first
invites two reviewers reaching different verdicts on the same case.
`resolve` now requires `report.assigned_moderator_id` to match the
caller's own `Moderator` row (`NotAssignedModerator` otherwise, mapped to
403). Not requested in the build-plan or PRD text — a judgement call made
during the build, recorded here per CLAUDE.md rather than left implicit.

**Left as-is, judged a non-issue at this scale, not fixed:** `claim()` has
a narrow TOCTOU race — two moderators claiming the same open report at the
exact same instant could both read `status == "open"` before either
commits, and both "succeed." Same class of gap the project already
accepted for chat's rate limit (D-6.6: "not worth row-locking complexity
for a pilot's generous headroom"); a handful of moderators reviewing a
pilot's report volume makes simultaneous claims on the identical report
implausible enough not to warrant the complexity now. Revisit if the
moderation team or report volume grows.

**Code:** `cohab/services/moderation_queue.py` (`ModerationService.resolve`,
`._maybe_reactivate`, `NotAssignedModerator`), `cohab/models/safety.py`
(`Report.sanction`), `tests/api/test_moderation.py`.

### D-7.4 `blocked_pairs` wired into `MatchesService` — closes D-2.6

See D-2.6 above (updated in place) for the full resolution. In summary:
`services/safety.py` gives `UserBlock` its first live write path, and
`MatchesService.get_matches` sets the ranker's `blocked_pairs` from it per
request — the eligibility-filter logic itself (`Reason.BLOCKED`) was
already correct and unit-tested since Phase 2; this phase is entirely about
giving it real data to run on.

### D-7.5 Blocking hides existing threads through one shared guard; unblock is blocker-only

**Spec:** PRD §10: blocking "removes the pair from each other's eligible
pool at Stage 1, hides existing threads, and cannot be undone by the
blocked party."

**Decision:** a new `PairBlocked` exception and `ensure_pair_active(session,
row)` helper in `services/match_access.py` — the module D-6.6 already
consolidated `chat.py`'s and `contact_share.py`'s shared
lookup-and-authorize logic onto — is called immediately after `load_match`
in `ChatService.send_message`/`.list_messages`,
`ContactShareService.get_status`/`.opt_in`, and
`MatchesService.get_explanation`/`.express_interest`. One code path for
"is this pair blocked", reused across all three services, rather than a
block check hand-rolled per call site.

`BlockService.unblock` (`DELETE /blocks/{blocked_id}`) only ever deletes a
row where `blocker_id` is the **caller's own** id — there is no endpoint
shape by which the blocked party can remove a block against them (the path
parameter names who's blocked, not who's asking to be unblocked by
someone else), so "cannot be undone by the blocked party" holds structurally,
not just by a permission check. Calling it with nothing of the caller's to
delete is a silent no-op (204), not an error — deliberately, so the
frontend never has to distinguish "already unblocked" from "never
blocked" as a failure case. Verified by
`tests/api/test_reports.py::test_unblock_only_works_for_the_blocker`.

**Code:** `cohab/services/match_access.py` (`PairBlocked`,
`ensure_pair_active`), `cohab/services/chat.py`,
`cohab/services/contact_share.py`, `cohab/services/matches.py`,
`cohab/services/safety.py` (`BlockService`), `cohab/api/chat.py`,
`cohab/api/matches.py`, `cohab/api/reports.py`,
`tests/api/test_chat.py::test_blocked_pair_cannot_read_or_send`.

### D-7.6 Moderator evidence is the reported user's flagged messages only, decrypted server-side

**Spec:** PRD §10: chat is "encrypted at rest under a server-held key... The
product promises moderation: that abusive content is detectable and that
reports about what was said can be acted on" — server-side readability
exists *for* moderation, which is what this phase is the first thing to
actually exercise. The evidence-scoping choice itself (flagged-only, not
the whole thread) is not spec-mandated — a decision made here, flagged as
such.

**Decision:** `ModerationService.list_flagged_evidence` queries
`Message.sender_id == report.reported_user_id AND Message.flagged.is_(True)`
— never the reporter's own messages, and never the reported user's
non-flagged ones. A moderator reviewing a report sees exactly the content
that was automatically flagged from the person being reported, not a
transcript of a private conversation the reporter is also a party to.
Broader disclosure (the full thread, on request, for a
`substantiated`/escalated case) is a plausible future extension but wasn't
asked for and isn't built here.

**Found while wiring this:** `services/chat.py` already had a private
`_safe_decrypt`/`_UNDECRYPTABLE_PLACEHOLDER` pair (D-6.6, item 3) for
exactly this "don't 500 the caller over one corrupted or wrong-key row"
problem, and the moderator evidence view needs the identical behaviour.
Rather than a second private copy in `moderation_queue.py` (which drifts —
e.g. someone changes the placeholder text in one file and not the other) or
reaching into another module's underscore-prefixed name, both were moved
into `core/crypto.py` as public `decrypt_message_safe`/
`UNDECRYPTABLE_PLACEHOLDER`, next to `decrypt_message` itself; `chat.py`
now imports the shared version instead of defining its own.

**Code:** `cohab/services/moderation_queue.py`
(`ModerationService.list_flagged_evidence`), `cohab/core/crypto.py`
(`decrypt_message_safe`), `cohab/services/chat.py` (updated to use it),
`tests/api/test_moderation.py::test_evidence_returns_only_flagged_messages_from_the_reported_user`.

### D-7.7 Live-verification findings: two stale-cache bugs and a migration round-trip gap, all fixed

**Found while manually verifying this phase in a real two-account browser
session** (CLAUDE.md's UI-testing rule — the same category of bug as
D-5.6/D-6.5/D-6.6, invisible to API-level tests since TanStack Query's
client-side cache doesn't exist in a `TestClient` run; driven with
Playwright rather than a person, but the same principle — actually render
the screens, don't just assert on HTTP responses). Verification also
surfaced one false alarm worth recording: an ambiguous `getByText(name)`
locator matched a same-named leftover account from an earlier verification
pass against this shared, never-reset dev DB, and briefly looked like a
regression in the real fix below until re-run with a `matchId`-scoped
navigation and unique per-run names.

1. **Blocking someone didn't refresh the match list before redirecting to
   it.** `BlockConfirmDialog`'s `onSuccess` navigated straight to
   `/matches` without touching the `['matches']` query cache — the
   just-blocked person rendered on screen for one frame regardless.
   TanStack Query's default `staleTime: 0` still paints the pre-block
   cached list synchronously on the fresh mount, before its own background
   refetch resolves; calling `invalidateQueries` alone (before `/matches`
   is even mounted) doesn't prevent that first paint, it only guarantees
   the refetch happens once mounted. Fixed by also stripping the blocked
   candidate directly via `queryClient.setQueryData` — the same pattern
   `MatchDetail.tsx`'s interest mutation already used — so the very first
   render is correct, not eventually correct.
2. **The identical gap existed on the escalating-report path.** An
   escalating reason (D-7.2) suspends the reported user immediately,
   server-side, which should also drop them from the reporter's list —
   `ReportDialog` had no cache handling at all. Fixed the same way, gated
   on the response's `escalated` flag (certain, since the backend only
   ever sets it when it actually suspended someone — not an inferred
   condition) so an ordinary, non-escalating report's harmless no-op
   filter never even runs.
3. **The migration's `downgrade()` broke a subsequent re-upgrade once any
   moderator had actually been created.** `DELETE FROM moderator` (added
   to keep `upgrade()`'s `ADD COLUMN user_id ... NOT NULL` valid on a
   re-upgrade — see D-7.1's migration) itself failed on
   `report.assigned_moderator_id`'s FK to `moderator` (nullable since
   Phase 1, `f0f781556f25`) if any report had been claimed. Fixed by
   nulling that column first. This was only caught by actually running
   `alembic downgrade -1` then `alembic upgrade head` against a database
   that had gone through real Phase-7 activity — reading the migration
   would not have surfaced it, since the table genuinely is empty on a
   first-ever upgrade.

**Code:** `frontend/src/features/safety/BlockConfirmDialog.tsx`,
`frontend/src/features/safety/ReportDialog.tsx`,
`backend/migrations/versions/4b7c9f2a1d63_phase_7_safety.py`.

### D-7.8 A blocked pair had no way back through the UI — added a "Blocked users" screen

**Found on a post-commit review pass, requested by the user** ("check if
there is any bugs, inconsistency, lack of feature... left"). PRD §10 says
blocking "cannot be undone by the blocked party" — which, read carefully,
implies the *blocker* can undo it, and `BlockService.unblock`
(`DELETE /blocks/{id}`) has existed since D-7.5 for exactly that. But
nothing in the frontend ever called it: once blocked, the other party's
match detail page 403s (`ensure_pair_active` inside `get_explanation`,
D-7.5), and there was no other screen a user could reach it from. A
mistaken block was, in practice, permanent from the UI's point of view,
even though the backend never intended that.

**Not in PRD §9's screen table** — this is new scope, so it was raised
with the user rather than built silently; they asked for it built now
rather than documented as deferred.

**Decision:** `GET /blocks` changed from returning bare `blocked_id`s to
full `BlockedUserOut` (`id`, `full_name`, `avatar_url`) — a "who have I
blocked" list needs to show *who*, not a UUID. `BlockService.list_blocked`
now returns the actual `User` rows (a join, not a second query per id).
New route `/blocked` (linked from `AppShell`'s nav, next to Matches) lists
them with an Unblock button per row; unblocking updates the cache directly
(`setQueryData`) and invalidates `['matches']`, the same pattern D-7.7's
fixes established, so the person becomes available again without a manual
reload. Verified live: block someone, confirm they render by name (not an
id) on `/blocked`, unblock, confirm the list empties and they're eligible
again in a fresh `/matches` query — all with no console errors.

**Code:** `cohab/services/safety.py` (`BlockService.list_blocked`),
`cohab/api/schemas.py` (`BlockedUserOut`), `cohab/api/reports.py`,
`frontend/src/features/safety/BlockedUsers.tsx`,
`frontend/src/components/AppShell.tsx`, `frontend/src/App.tsx`,
`tests/api/test_reports.py`.

---

## Phase 8 — Feedback loop and analytics

### D-8.1 `_upsert` immutability fix — closes D-4.6, a prerequisite for publishing a second `weight_set` at all

**Spec:** CLAUDE.md's matching-design invariant: "Every `match_score` row
stores the `weight_set_id` it was computed under. Weight sets are immutable
once published... Without this, historical explanations are not
reproducible." D-4.6 (Phase 4) flagged that `MatchesService._upsert`
unconditionally overwrote `weight_set_id`/`score_ab`/`score_ba`
/`combined_score`/`breakdown` on *every* `GET /matches` call regardless of
the row's `state`, and deferred the fix to "whenever Phase 8 publishes a
second `weight_set` version" — harmless with exactly one version in
existence, which was true through Phase 7.

**Decision:** `_upsert` now only refreshes those five fields while
`row.state == "suggested"`. Once a row has been viewed (or moved further),
it is frozen — a later rescore under a newly-published `weight_set` no
longer touches it. This had to land *before* `weight_sets.publish` (D-8.4)
could be considered safe to actually call against a live pool: without it,
publishing a second version would retroactively change every not-yet-
`suggested` match's explanation on its next `GET /matches`, which is exactly
what the immutability guarantee forbids.

**Verified by** `tests/api/test_matches.py
::test_publishing_a_new_weight_set_leaves_an_already_viewed_match_untouched`
— views a match (state → `viewed`), publishes a second `weight_set`, calls
`GET /matches` again and asserts the viewed row's `weight_set_id`
/`breakdown`/`combined_score` are byte-for-byte unchanged, then resets the
same row to `"suggested"` and confirms a further call *does* pick up the new
version — proving the guard is state-gated, not a blanket freeze.
Deliberately exercises only the live API path, not `recompute` itself:
`recompute` walks every verified/active user in this suite's shared,
~1,500-row dev-seeded pool (the `LARGE_LIMIT`/"tests share that pool" 
precedent `tests/api/test_matches.py` already documents), and doing that
once per test run turned out to cost the entire rest of the suite's runtime
several times over (D-8.5's own "expensive, run off-peak" framing, taken
literally) — appropriate for the manual verification pass, not a suite
meant to run on every green-test commit. Since `recompute` drives this exact
`_upsert` call with no logic of its own (D-8.5), the live-API test already
covers the behaviour that matters.

**Code:** `cohab/services/matches.py` (`MatchesService._upsert`).

### D-8.2 Lifecycle endpoints: `confirm-move-in` and `reject`, closing the Phase 6/7 follow-up

**Spec:** PRD §8.2's lifecycle diagram: `ContactShared -> Cohabiting: move-in
confirmed`; `Viewed -> Rejected: dismisses`; `Chatting -> Rejected: either
withdraws`. No code path reached either terminal state before this phase —
flagged as an open follow-up since Phase 6/7 (`services/matches.py`'s own
comment: "there's no reject/expire endpoint yet"). Outcome logging (this
phase's headline deliverable) has nothing to attach to without them, so
building both was confirmed with the user as in-scope for Phase 8 rather
than a separate phase.

**Decision:** `MatchesService.confirm_move_in` requires `state ==
"contact_shared"` and sets `cohabiting_since` (new column, D-8.3) exactly
once; `MatchesService.reject` covers *both* diagram edges with one
transition (`{viewed, interested, mutual, chatting, contact_shared} ->
rejected`) since both are "one party unilaterally ends it" — the diagram's
two-edges-one-meaning distinction wasn't worth two endpoints. Both reuse a
new `_load_pair_row` helper, factored out of the near-identical load/
authorize preamble `express_interest` and `get_explanation` each had their
own copy of (same class of consolidation as D-6.6 item 4's
`match_access.py`, scoped here to `MatchesService` itself rather than a new
shared module). `Interested -> Expired` (14-day no-response timeout) is
**not** built — PRD's diagram doesn't tag that edge "outcome logged," so
nothing in this phase depends on it; left as a follow-up, most naturally a
future addition to the recompute job (D-8.5) rather than a user-facing
endpoint.

**Code:** `cohab/services/matches.py` (`InvalidStateTransition`,
`_load_pair_row`, `confirm_move_in`, `reject`), `cohab/api/matches.py`,
`tests/api/test_matches.py`;
`frontend/src/features/matches/MatchDetail.tsx`,
`frontend/src/features/matches/RejectConfirmDialog.tsx`.

### D-8.3 Feedback cadence reconciled against the "reports once" invariant; outcome taxonomy proposed

**Spec:** CLAUDE.md: `feedback`: `UNIQUE (score_id, submitted_by)` — "each
participant reports once," a schema invariant in place unused since Phase 1.
PRD §9 screen 12: "Outcome feedback — Triggered at 30 and 90 days after
Cohabiting," which read literally implies two check-ins per participant.
`models/feedback.py`'s own comment (since Phase 1) flagged that the outcome
taxonomy itself "isn't specified anywhere in the docs."

**Decision — cadence:** "triggered at 30 and 90 days" is read as a
*reminder cadence* for one eventual report, not two mandatory submissions.
`FeedbackService.pending_for` surfaces a `cohabiting` match once 30 days
have elapsed since `cohabiting_since` and stops surfacing it the moment that
user has submitted — a user who hasn't answered by day 30 is still "due" at
day 90 (nothing distinguishes the two checkpoints), one who answered at day
30 is never asked again. `FeedbackService.submit` itself imposes **no**
elapsed-time requirement — only `state in ("cohabiting", "rejected")` — so a
voluntary early report (e.g. moved out after two weeks) is never refused;
PRD names no reason to block one, and an early failure is itself
informative for Phase 9's survival analysis. No schema change, and no
tension with the `UNIQUE` constraint, which was never actually the
obstacle — the two readings only looked incompatible before the cadence/
submission distinction was made explicit.

**Decision — taxonomy** (proposed, not spec-sourced, per CLAUDE.md's rule
against presenting an invented value as specified): framed around PRD's
stated primary metric (90-day cohabitation survival, a right-censored
duration problem, Kaplan-Meier per §12).
- `rejected` match → `outcome ∈ {"not_pursued", "incompatible", "other"}`,
  `cohabitation_duration_days` always `NULL`.
- `cohabiting` match → `outcome ∈ {"still_together", "moved_out"}`.
  `cohabitation_duration_days` is **computed server-side** from
  `cohabiting_since` for `"still_together"` (never trusts a client-supplied
  figure for the case the server can derive itself); accepted from the
  client only for `"moved_out"`, since the move-out date isn't otherwise
  observable. This gives Phase 9's Kaplan-Meier estimator exactly the
  event/censoring pair it needs, straight off this table.

Not enforced as a DB `CHECK` — same precedent as `Report.reason`
(`REPORT_REASONS`, D-7.x): a proposed, not spec-fixed vocabulary, and here
additionally state-dependent (which subset is valid depends on the match's
`state`, which a flat table-level `CHECK` can't express), so validation
lives in `FeedbackService.submit` instead.

**New column:** `MatchScore.cohabiting_since` (nullable `datetime`,
migration `dccee11a7103`) — anchors both the cadence check above and the
survival duration; set once by `confirm_move_in` (D-8.2), never overwritten.

**Code:** `cohab/models/feedback.py` (`REJECTED_OUTCOMES`,
`COHABITING_OUTCOMES`), `cohab/models/matching.py` (`cohabiting_since`),
`cohab/services/feedback.py`, `cohab/api/feedback.py`,
`tests/api/test_feedback.py`;
`frontend/src/features/matches/FeedbackDialog.tsx`.

### D-8.4 `weight_set` publish mechanism built; no fitted v3 published

**Spec:** PRD §6.5's three-tier weight-refinement table places tier-2
*fitted* weights (regularised logistic regression over real outcomes) at
**v2/post-pilot**, needing "a few hundred labelled outcomes." This phase is
the first to collect any outcome data at all (D-8.3), so there is nothing
yet to fit against.

**Decision:** built only the versioning machinery —
`weight_sets.publish(session, weights, source)` validates the vector sums to
~1 and `source` is a known `WEIGHT_SET_SOURCES` value, deactivates whatever
is currently active (`UPDATE ... WHERE is_active` — plural on purpose, so a
prior inconsistency can't leave two rows simultaneously active), and inserts
a new immutable, active row. No function anywhere ever updates an existing
row's `weights` — immutability is structural, not a convention callers have
to remember. No statistical fitting logic is built this phase; tier 2 stays
a documented future step, gated on real outcome volume existing.

**Code:** `cohab/services/matching/weight_sets.py`, `tests/api/test_weight_sets.py`.

### D-8.5 The periodic recompute job is a thin driver over `MatchesService.get_matches`, not a parallel reimplementation

**Spec:** build plan §4 Phase 8 ("the periodic recompute job"); PRD §7.1's
Stage B invalidation table names the specific event this handles: "a new
weight set is published → rescore everything — expensive, run off-peak."

**Decision:** rather than reimplementing Stage 1 + Stage 2 + upsert from
scratch, `recompute.py` loads every verified/active user and calls the
*same* `MatchesService.get_matches(user, limit=3000)` the live API uses —
so it inherits D-8.1's immutability guard for free (a `suggested` row
refreshes, a viewed-or-later row doesn't) with no duplicated logic to drift
out of sync. It fits its own `TfidfSimilarity` over the whole pool
(`Candidate.lifestyle_notes`), the same offline-fitting precedent
`report.py`/`tuning.py` already established (D-4.4 item 3's carve-out: the
live API never encodes text in the request path, but an explicitly offline
batch job is exactly the allowed exception). Run manually
(`python -m cohab.services.matching.recompute`) — no scheduler dependency
introduced, consistent with CLAUDE.md's Redis/infra-deferral stance and the
project's existing "run it yourself" precedent for `report.py`/`tuning.py`.
This does **not** move the system to Stage B — PRD §7.1's own migration
trigger (p95 latency or pool size) hasn't been measured as reached, so
`GET /matches` still computes on read; the job only keeps `match_score`
caught up between calls, and incidentally materialises it broadly enough
for the analytics dashboard (D-8.6) to query directly.

The core logic (`recompute(session)`) takes a caller-supplied session rather
than owning its own, specifically so the D-8.1 regression test could drive
it directly against the test suite's SAVEPOINT-backed `db_session` fixture
instead of a real `SessionLocal()` — `main()` is the only caller that
constructs one.

**Code:** `cohab/services/matching/recompute.py`.

### D-8.6 Institutional analytics dashboard built at minimal, pilot-appropriate scope — a deliberate v1/v2 scope tension, confirmed with the user

**Spec:** PRD §4 lists "Institutional analytics dashboard" under **v2 —
after the pilot**, and §9's v1 screen table (screens 1–13) has no dashboard
screen at all. The build plan names it explicitly in Phase 8's own line
item, and PRD §3.2's Dr Sathya persona frames *some* aggregated, anonymised
visibility as "the reason institutions cooperate with the pilot," calling
it "low priority for v1" rather than excluded from it — the two documents
don't actually agree on this one.

**Decision (confirmed with the user, Phase 8 planning):** build the minimal
reading rather than either extreme. `GET /analytics/summary` returns plain
aggregate counts already implied by tables that exist — members by
`verification_status`/`account_status`, the match-state funnel
(`GROUP BY state` over `match_score`), report volume by status — gated by
the existing `require_moderator` dependency (D-7.1), introducing no new
institution-admin actor. No per-user drill-down, no exports, no survival
curve: full Kaplan-Meier analysis over `feedback` is Phase 9's evaluation
chapter by name (PRD §12), not this screen. Recorded here explicitly because
it is, admittedly, v2-labelled PRD scope built during the v1 pilot phase —
a deliberate call, not an oversight, made because the build plan asked for
it by name and the persona section itself doesn't rule it out.

**Code:** `cohab/services/analytics.py`, `cohab/api/analytics.py`,
`tests/api/test_analytics.py`;
`frontend/src/features/analytics/AnalyticsDashboard.tsx`,
`frontend/src/App.tsx`, `frontend/src/components/AppShell.tsx`.

### D-8.7 Live-verification finding: the feedback dialog unmounted itself before showing its own success screen

**Found while manually verifying this phase in a real two-account browser
session** (CLAUDE.md's UI-testing rule; the same category of bug as
D-5.6/D-6.5/D-7.7, invisible to API-level tests since the bug is entirely in
client-side query-cache interaction — driven with Playwright against system
Chrome rather than a person, same principle as D-7.7's Playwright pass:
actually render the screens). `MatchDetail.tsx` rendered `FeedbackDialog`
conditionally on `pendingHere` (`pending?.find((p) => p.match_id ===
matchId)`, from the live `['feedback', 'pending']` query). The dialog's own
`onSuccess` strips the just-submitted match from that same cache
(`setQueryData` + `invalidateQueries`, the established pattern from
D-7.7/ReportDialog) — which made `pendingHere` go `undefined` on the very
next render, unmounting `FeedbackDialog` entirely before its own internal
`mutation.isSuccess` branch (the "Thanks for letting us know" screen) ever
painted. Submitting feedback silently closed the dialog with no
confirmation shown, even though the submission itself had succeeded.

**Decision:** `MatchDetail` now captures the specific `PendingFeedbackOut`
into local state (`feedbackTarget`) at the moment "Give feedback" is
clicked, and renders `FeedbackDialog` off that captured value rather than
the live query result. The parent's cache invalidation still runs (so the
banner and `MatchList`'s pending section correctly stop listing the match),
but it no longer controls whether the dialog itself stays mounted — that's
`onClose` alone, fired by the user dismissing the success screen.

**Code:** `frontend/src/features/matches/MatchDetail.tsx`.

### D-8.8 `/code-review medium` pass — three real findings, all fixed

**Requested by the user** before committing Phase 8 ("check if there is any
bugs, inconsistency, lack of feature or anything left"), same precedent as
D-6.6. Four findings came back; three were real and fixed, one was already
covered.

1. **Rejected/cohabiting candidates reappeared in `GET /matches`.**
   `EligibilityFilter`/`passes_hard_constraints` had no notion of
   `match_score` at all — Stage 1 only ever checked profile-level hard
   constraints (spec §2) plus `blocked_pairs` (D-2.6/D-7.4). A pair whose
   `match_score.state` was `rejected` (via D-8.2's new endpoint) or
   `cohabiting` still passed Stage 1 on the very next `GET /matches` call
   and got re-suggested, directly contradicting `RejectConfirmDialog.tsx`'s
   own copy ("neither of you can pick this back up from here"). Fixed by
   adding `settled_pairs` to `EligibilityFilter`/`passes_hard_constraints`
   (new `Reason.ALREADY_DECIDED`), populated per-request by
   `MatchesService._settled_pairs_for` — same shape and same per-subject
   scoping as `blocked_pairs`/`blocked_pairs_for`. Deliberately scoped to
   just `rejected`/`cohabiting`, the two states Phase 8 made reachable;
   whether `mutual`/`chatting`/`interested`/`contact_shared` pairs should
   *also* stop appearing in the generic ranked list is a pre-existing
   question from Phase 5 this finding doesn't extend to answering — no
   endpoint or test anywhere already assumed those states drop out of the
   list, so changing that now would be a wider, undiscussed behaviour
   change, not a Phase 8 bug fix.
2. **`express_interest` had no guard against the new terminal states.**
   Calling it on an already-`rejected` or already-`cohabiting` match
   silently set `interested_by_a`/`_b` with no visible effect on `state` —
   confusing (the UI could end up saying "Interest sent" about a match that
   was already over) rather than being rejected outright. Fixed with a
   guard mirroring `confirm_move_in`/`reject`'s own state checks
   (`InvalidStateTransition` → 409), covering `rejected`, `cohabiting`, and
   `expired` (the last unreachable today, included for when it isn't).
3. **`FeedbackService` re-implemented `match_access.load_match`.**
   `services/match_access.py`'s own docstring explains why it exists:
   `ChatService`/`ContactShareService` used to each keep their own
   lookup+authorize copy, "a fix made in one copy wouldn't apply to the
   other." `services/feedback.py` (new this phase) reintroduced exactly
   that pattern with a third copy plus a fourth `MatchNotFound`/`NotAParty`
   pair. Fixed by importing `match_access.load_match` directly;
   `api/feedback.py` now catches `match_access.MatchNotFound`/`.NotAParty`
   rather than a `services.feedback`-local pair. Deliberately does *not*
   also call `ensure_pair_active` (the blocking check `matches.py`/`chat.py`
   use) — feedback is a retrospective report on a match that's already
   over, and a block placed *after* a bad cohabitation shouldn't prevent
   reporting on it, unlike chat or contact-sharing, which are about
   ongoing interaction.
4. **`recompute.py` shipped with no test — not fully actionable at the
   suite's normal cost, partly addressed.** CLAUDE.md requires tests for
   everything in `services/matching/`. A full happy-path test is exactly
   the cost D-8.1 already found and removed from the automated suite
   (walking the whole shared dev pool). Added
   `tests/api/test_recompute.py::test_recompute_raises_when_no_active_weight_set`
   — cheap, real coverage for the one branch that doesn't require the
   full-pool walk. The happy path remains covered only by the one-time
   manual run recorded in D-8.1, not by an automated test; flagged here
   rather than silently left short of CLAUDE.md's rule.

**Code:** `cohab/services/matching/eligibility.py` (`Reason.ALREADY_DECIDED`,
`EligibilityFilter.settled_pairs`), `cohab/services/matches.py`
(`_settled_pairs_for`, `express_interest`'s new guard),
`cohab/services/feedback.py`, `cohab/api/feedback.py`,
`tests/matching/test_eligibility.py`, `tests/api/test_matches.py`,
`tests/api/test_recompute.py`.

---

## Phase 9 — Evaluation and polish

Build plan §4 Phase 9 ("filter yield, score distribution, attribute
ablation, precision@k... two charts and a table"); PRD §15 "Evaluation —
v1" (ranking metrics, ablation, distributional analysis, Kaplan-Meier
survival analysis); PRD §6.6 (what synthetic data can and cannot validate).
New report script `cohab/services/matching/evaluation.py`
(`python -m cohab.services.matching.evaluation`), three new tested modules
(`ranking_metrics.py`, `recovery.py`, `survival.py`), and
`docs/COHAB_EVALUATION.md` — the narrated writeup PRD §14's roadmap names
("Evaluation, report, demo"). Follows `report.py`/`tuning.py`'s established
shape: pure, tested primitives aggregated by an untested, manually-run
stdout script.

### D-9.1 Precision@k/NDCG@10 ground truth is a recovery experiment, not behavioural labels

**Spec:** PRD §6.6 — synthetic-data performance figures (precision@k, NDCG,
accuracy) "must never be reported as evidence that the matching works,"
except as a **recovery experiment**: "plant a known compatibility function
in the generator, confirm the matcher recovers it — this validates the
implementation." PRD §6.5 separately names the alternative this rules out:
real interaction outcomes (`match_score.state`, `feedback.outcome`) are "the
label problem" — a *pursued* label records a click, not compatibility — and
in any case there is almost no real interaction volume yet (Phases 6–8's
own data is a handful of manually-created rows from live-verification
passes).

**Decision:** `recovery.py` constructs, for a real subject, synthetic
candidates whose ground-truth ordering is known *by construction*: 17 of
the 20 scored attributes (`PERTURBABLE_ATTRIBUTES`) can be swapped to the
value the already spec-sourced matrices in `matrices.py` (§4 similarity, §5
tolerance, §6 absolute, plus the ordinal attributes' ordered lists) record
as *least compatible* with the subject's own answer — no new compatibility
model invented, purely a lookup against numbers already in the codebase.
`budget_proximity`, `interests` and `lifestyle_notes` are excluded:
`budget_proximity` needs a numeric offset that must stay inside Stage 1's
band-intersection test or the candidate is excluded rather than merely
scored lower; `interests` (Jaccard) needs a controlled-overlap tag set;
`lifestyle_notes` has no matrix at all (its similarity is TF-IDF/embeddings,
already separately validated in D-3.3). `build_graded_pool` builds 5
relevance grades (0/25/50/75/100% of the 17 attributes deviated) × 6
candidates each = 30 per subject, sized so the top-2-grade "relevant" set
(12 candidates) exceeds `k=10` — a perfect precision@10 is achievable, not
capped by construction. `evaluation.py` runs the real, unmodified
`CompatibilityMatcher`/`MatchRanker` pipeline over each subject's 30
candidates and checks whether it recovered the construction order via
`ranking_metrics.py`'s `precision_at_k`/`ndcg_at_k` (pure functions, no
prior implementation existed anywhere in this codebase). Precision is
reported at k=5 and k=10 — PRD §15 fixes NDCG@10 by name but leaves
precision@k's k unspecified; 5 and 10 are proposed, matching
`report.py`/`tuning.py`'s existing `TOP_K = 10` convention.

**Rejected alternative:** extend `seed.py` with a hidden latent
"compatibility trait" that generates correlated answers, using
trait-distance as ground truth. Rejected as *more* speculative than the
chosen approach, not less — it would require inventing a new synthetic
personality-generation model, whereas reusing the already-spec-sourced
matrices invents nothing new; it tests the implementation's wiring
(eligibility → directional scoring → harmonic mean → sort), which is
exactly PRD §6.6's legitimate target, without any new claim about what
makes roommates compatible.

**Measured** (20 subjects, weight_set v3): precision@5 = **1.000**,
precision@10 = **0.990**, NDCG@10 = **0.998** — near-perfect recovery, the
expected result of a correctly-implemented pipeline against a ground truth
built from its own scoring primitives. Restated per PRD §6.6: this is a
positive result about the implementation's wiring, **not** evidence that
similar-on-these-attributes roommates cohabit more successfully in reality.
Full narrative in `docs/COHAB_EVALUATION.md` §4.

**Code:** `cohab/services/matching/recovery.py`, `ranking_metrics.py`,
`evaluation.py` (`_print_recovery_experiment`), `tests/matching/
test_recovery.py`, `tests/matching/test_ranking_metrics.py`.

### D-9.2 Stage-1 self-conflict in `perturb_candidate` — found in four rounds, against the real seeded DB, not the unit tests

**Spec:** COHAB_MATCHING_SPEC.md §2 (Stage 1 hard constraints);
CLAUDE.md's "read the matching code properly" / run-it-yourself rule.

**The bug, and why unit tests couldn't catch it.** The first version of
`perturb_candidate` copied every Stage-1 field (`gender`,
`gender_preference`, `seeker_type`, `has_pet`, `pet_tolerance`,
`severe_allergy`, `kitchen_allergens`, `smoking_dealbreaker`,
`verification_status`, `account_status`) unchanged from the subject, on the
reasoning that identical Stage-1 fields trivially clear Stage 1. That
reasoning is false: several of `eligibility.py`'s checks are *symmetric
self-comparisons* — true of a subject against an identical copy of
themselves — whenever the subject's own profile has one of a handful of
real, valid shapes:

- a subject whose `gender_preference` excludes their own `gender` (e.g.
  seeking only the opposite gender) — `_gender_pref_satisfied(a.gender_pref,
  b.gender)` fails when `b.gender == a.gender` but `a.gender_pref` isn't
  `a.gender` or `"any"`;
- a `has_place` subject — `BOTH_HAVE_PLACE` fires against any candidate
  sharing that `seeker_type`, including itself;
- a subject who owns a pet but can't tolerate a roommate's own
  (`has_pet=True, pet_tolerance="cannot_live_with_pets"`) — a real, valid
  combination, not a data error;
- a subject with `smoking_dealbreaker=True` who already smokes indoors
  themselves — also real and valid;
- an unverified or suspended subject — `NOT_VERIFIED_OR_ACTIVE` checks only
  the *candidate's* state, so a self-clone with the subject's own
  not-yet-verified state fails it too.

Running the experiment against the seeded dev DB (not the fixture-driven
unit tests, whose defaults — `gender_preference="any"`,
`seeker_type="needs_place"`, no pet, `smoking_dealbreaker=False`,
`verification_status="verified"` — happen to avoid every one of these)
surfaced this progressively: precision@5/@10/NDCG@10 first landed at
exactly 0.300 (the fraction of sampled subjects that happened to clear
Stage 1 by luck), traced field by field over several live runs to gender,
then `seeker_type`, then pets/allergies/smoking. The
`verification_status`/`account_status` gap was not caught by a live run at
all — `evaluation.py` only ever samples already-verified/active subjects
(`_is_valid_subject`), so it was latent rather than live — and was instead
found by a `/code-review high` pass's removed-behaviour audit before this
phase was committed.

**Decision:** `perturb_candidate` now overrides all ten of these fields to
values that can never trip any of `eligibility.py`'s mutual checks —
`gender`/`gender_preference` resolved so the forward direction is satisfied
by construction and the reverse by `gender_preference="any"`;
`seeker_type="needs_place"` (never excluded by `BOTH_HAVE_PLACE` regardless
of the subject's own type); `has_pet=False, pet_tolerance="comfortable"`;
`severe_allergy=[], kitchen_allergens=[]`; `smoking_dealbreaker=False`, plus
(for subjects who *do* have the dealbreaker set) dropping `"smoking"` from
the perturbable attribute set and forcing the candidate's own
`smoking_behaviour="none"`, since an unperturbed grade-4 candidate would
otherwise inherit the subject's own real (possibly self-conflicting)
behaviour; `verification_status="verified", account_status="active"`. None
of these ten fields has a Stage-2 scoring role (`attributes.py`'s registry
never reads any of them), so neutralising all of them costs nothing.
`evaluation.py`'s `_select_recovery_subjects` additionally checks
`passes_hard_constraints(subject, perturb_candidate(subject, 0.0, rng))`
before including a subject, skipping (and counting, not erroring) any that
still fail — this should never fire given the neutralisation above (and
doesn't, on the current dev DB), but is kept as a safety net against a
*future* `eligibility.py` check this list hasn't caught up with yet, so a
gap like this degrades to a visible, counted skip rather than a silently
biased 0 score.

**Not solved, deliberately:** there is no structural mechanism tying this
field list to `eligibility.py`'s actual checks — it's necessarily
maintained by inspection, the same way it was built. A property-style test
that could catch this automatically (e.g. iterating every `Reason` and
asserting a corresponding safeguard) would need to run against real,
diverse profile shapes to be meaningful, which conflicts with
`services/matching/`'s deliberate DB-free, fast-unit-test architecture
(CLAUDE.md) — the empirical, run-it-against-real-data discovery process
this decision documents is a consequence of that architecture choice, not
an oversight it's cheap to close. Recorded here so a *sixth* Stage-1 field
added to `eligibility.py` in a future phase is a known risk to check against
this list, not a surprise.

**Code:** `cohab/services/matching/recovery.py`
(`_gender_that_clears_stage_one`, `perturb_candidate`),
`cohab/services/matching/evaluation.py` (`_select_recovery_subjects`),
`tests/matching/test_recovery.py` (six regression tests, one per field
group, each naming the exact `eligibility.py` check it closes).

### D-9.3 Kaplan-Meier hand-rolled; per-pair feedback reconciliation policy; a `moved_out`-without-duration bug found by code review

**Spec:** PRD §15 ("a right-censored survival problem... the Kaplan–Meier
estimator is the correct treatment"); PRD line 53 (the primary outcome).

**Decision — hand-rolled, not `lifelines`.** `survival.py`'s
`kaplan_meier` is a ~30-line standard product-limit estimator, tested
against a hand-computed fixture (worked in the test file's own comments).
Matches this project's established minimal-dependency stance (D-4.5's OTP
HMAC over a heavier scheme, D-6.2's `Fernet` over standing up key-management
infra) rather than a new survival-analysis dependency for one estimator
that's easy to verify and defend directly.

**Decision — per-pair reconciliation.** The survival unit is the *pair*
(`match_score`), not the individual — both parties may submit `feedback`
for the same match (`UNIQUE(score_id, submitted_by)` allows two rows), so
`_reconcile` collapses them to one observation: if *either* party reports
`moved_out`, the pair is an **event**, duration = the smaller of the
reported durations (the earlier-observed failure is correct); otherwise the
pair is **censored**, duration = the larger of the known
`still_together`/no-feedback-yet durations (the freshest observation).
Proposed, not spec-sourced — PRD/spec are silent on dual-report
reconciliation.

**Bug found by `/code-review high`, fixed before committing:** the original
`_reconcile` only counted a `moved_out` report as an event if it also
carried a `cohabitation_duration_days`. But that field is optional even for
`moved_out` at both the API schema (`schemas.py`) and
`FeedbackService.submit()` — a client can omit it. A `moved_out` report with
no duration fell through to the "nobody has submitted feedback yet" branch
and was silently counted as **censored** — a real relationship failure
misclassified as still-ongoing, understating events in the Kaplan-Meier
curve. Fixed with `_duration_for_moved_out`: any `moved_out` report is now
an event regardless of whether a duration was given, falling back to
`(feedback.submitted_at - cohabiting_since).days` — an upper bound on the
true move-out date, since the pair had already moved out by the time they
reported it — when the client-supplied figure is absent. Found by review,
not a live run: the dev DB has no `feedback` rows at all yet, so this
couldn't have surfaced empirically either way. `_reconcile` (previously
DB-loading glue only) is now directly unit-tested against six hand-built
cases, including this one.

**Code:** `cohab/services/matching/survival.py` (`kaplan_meier`,
`_reconcile`, `_duration_for_moved_out`, `load_cohabitation_observations`),
`tests/matching/test_survival.py`.

### D-9.4 No fabricated survival data

**Spec:** CLAUDE.md ("do not present an invented value as specified"); PRD
§6.6's circularity trap, applied here to the metric PRD line 53 itself
flags as most sensitive to being reported honestly.

**Decision:** the survival chart (`docs/evaluation/survival_curve.png`) is
built **only** from whatever real `match_score`/`feedback` rows exist,
however few — on this dev DB, zero. `evaluation.py` reports the real N
plainly and cites PRD line 53's own acknowledgment that this metric "will
not be measurable inside the project timeline; the instrumentation is built
anyway" rather than padding the sample with synthetic "illustrative"
outcomes. This is deliberately the conservative default: inventing outcome
data for this one chart is the single place this phase could slide into
exactly the misrepresentation CLAUDE.md and PRD §6.6 both warn against.

**Code:** `cohab/services/matching/evaluation.py` (`_print_survival`,
`_save_survival_chart`).

### D-9.5 Ablation extended to all ~20 attributes, with two new statistics

**Spec:** matching-spec §11 item 6 named four attributes
(`sharing_norm`, `home_orientation`, `sociability`,
`cost_split_preference`) for *Phase 3's* tuning checklist specifically
("four to look at"); PRD §15 describes this phase's own scope more broadly
("ablation studies to measure each attribute's marginal contribution," no
restriction to four).

**Decision:** `evaluation.py`'s ablation section (`_print_ablation`) runs
`tuning.py`'s existing mechanism (zero one attribute's weight, re-rank,
compare) over the full `ATTRIBUTES` registry, and adds two statistics
beyond D-3.2's top-10-overlap/#1-changed: mean `|Δcombined_score|` and a
hand-rolled Spearman rank correlation (Pearson over ranks, reusing
`tuning.py`'s own `_pearson` — no new dependency).

**Measured, revisiting D-3.2 with a cleaner statistic:** the four spec §11
item 6 attributes' Spearman correlations (0.992–0.997) are among the
*least* disruptive of all 20 when zeroed — confirming D-3.2's Phase 3
non-change decision more cleanly than a 15-subject, overlap-only sample
could. Two findings surfaced that weren't visible before: `cleanliness_level`
(highest weight, 0.11) has the lowest Spearman (0.903) and top-10 overlap
(6.9/10) of any attribute, the expected shape for the highest-weighted term
in a weighted sum; `sleep_schedule` (weight 0.09, mid-table) changes the
**#1**-ranked candidate in 10/15 subjects, the highest rate of any
attribute despite unremarkable overall Spearman/overlap — flagged in
`docs/COHAB_EVALUATION.md` §3 for the report, not acted on here (a matching-
design question, not an evaluation-phase one).

**Code:** `cohab/services/matching/evaluation.py` (`_print_ablation`,
`_spearman`, `_rank_transform`).

### D-9.6 `tuning.py` left untouched; `evaluation.py` duplication accepted; a `/code-review high` pass, fixed vs. left as-is

**Spec:** build plan §4 Phase 9; CLAUDE.md ("one phase per session"). User
requested a check for "bugs, inconsistency or ambiguity" before committing,
same precedent as D-6.6/D-8.8.

**Decision — duplication.** `tuning.py` is Phase 3's dated checkpoint,
already cited with specific numbers in D-3.2 — changing its behaviour would
retroactively muddy that historical record. `evaluation.py` is a new,
independent script; it duplicates `tuning.py`'s `_load_candidates`,
`_is_valid_subject`, `_pearson`, the yield/score-distribution/ablation
printing structure, and spec-§11 threshold constants, rather than factoring
out a shared module. This is the same duplication `tuning.py` already
carries against `report.py` — an established pattern in this codebase, not
a new one introduced here.

**`/code-review high` findings, fixed:**

1. Missing type hints on `_load_candidates(session)`/`_print_survival
   (session)` — added `Session` (CLAUDE.md: "type hints on all service
   functions").
2. `_print_yield`/`_print_recovery_experiment` called `statistics.median`/
   `.mean` on a list that could be empty (no verified/active subjects, or
   every recovery-experiment subject skipped) — `StatisticsError` would
   crash the whole report past that point. Both now guard and print a
   plain "nothing to report" line instead.
3. `_print_score_distribution`'s p25/p75 fallback for samples under 4
   points reused `min`/`max` under the "p25"/"p75" label, misrepresenting
   them as quartiles; also contained a dead ternary branch
   (`quantiles[-1] if len(quantiles) > 1 else quantiles[0]` — always true
   given how `quantiles` is built). Rewritten to print "too few points for
   p25/p75" instead of a mislabelled figure.
4. D-9.2's `verification_status`/`account_status` gap and D-9.3's
   `moved_out`-without-duration gap (both above).

**`/code-review high` findings, left as-is (judged non-issues at this
scale, matching the precedent set by D-6.6/D-7.3/D-8.6's own "left as-is"
sections):**

- Several efficiency findings (Stage-1 eligibility re-filtered once per
  ablated attribute instead of cached; `MatchRanker.rank()`'s unused
  `Explanation` objects built and discarded inside the ablation loop;
  `_print_yield`/`_collect_scores` re-filtering the same subject slice
  twice; an N+1 `Feedback` query in `load_cohabitation_observations`; a
  loop-invariant recomputed per candidate in `build_graded_pool`). All are
  real, all match a pattern `tuning.py`/`report.py` already carry
  unaddressed at pilot data volumes, and this script is manually run
  offline, never on a request path. Fixing them here without also fixing
  the identical pattern in the older scripts would be inconsistent;
  revisit only if a future phase's data volume makes a multi-minute
  offline report genuinely painful.
- `recovery.py`'s three near-identical single-field perturbation-factory
  closures (`_similarity_perturbation`/`_ordinal_perturbation`/
  `_absolute_perturbation`) could be parameterised into one. Left as
  written — each is one line, already covered by dedicated tests, and the
  suggested generalisation trades a small amount of duplication for an
  extra layer of indirection with no behaviour change.
- `_print_ablation`'s `baseline_top10` is fully derivable from
  `baseline_scores` (same order, same source list) but stored separately.
  Low risk, not touched.

**Code:** all of `cohab/services/matching/{evaluation,recovery,survival,
ranking_metrics}.py` and their test files.

**Also:** `backend/requirements.txt` gains `matplotlib==3.10.7` (new
dependency — the two saved charts have no lighter-weight standard-library
alternative); `docs/evaluation/score_distribution.png` and
`docs/evaluation/survival_curve.png` are generated artifacts, regenerated by
each `evaluation.py` run, not hand-authored; `docs/COHAB_EVALUATION.md` is
the narrated "report" PRD §14's roadmap names, cross-referencing this
section rather than repeating it.

---

## Phase 10 — Post-Phase-9 hardening pass

A three-agent audit (matcher-reviewer + two general-purpose agents, one
backend one frontend), run after Phase 9 shipped, read this file in full and
reported 12 findings not already logged here. Three were clear bugs (fixed
with no new decision needed — a median-formatting regression in `report.py`,
missing `IntegrityError` handling on three racy check-then-insert writes, and
a frontend moderation-queue stale-cache gap in the same family already fixed
twice, D-7.7/D-8.7); the rest needed a decision, recorded as `D-10.1`
onward below.

### D-10.1 OTP recovery: an email-keyed resend endpoint, not a `user_id`-keyed one or a `register()` side effect

**Gap:** `AuthService.verify_otp` had no recovery path once
`otp_attempts >= OTP_MAX_ATTEMPTS` (5) or `otp_expires_at` passed
(`OTP_TTL_MINUTES`, 10) — it raises forever, and `register()`'s uniqueness
check (`auth.py`) rejects any repeat call for the same email regardless of
`verification_status`, so a user who never finishes verifying is
permanently stuck. Not spec-derived — PRD/matching spec are silent on OTP
recovery.

**Decision (confirmed with the user):** a new `POST /auth/resend-otp`,
keyed by **email**, not `user_id`. Two alternatives were considered and
rejected:
- A `user_id`-keyed endpoint (matching `verify_otp`'s own key) recovers the
  "code expired while the tab is still open" case, but not "closed the tab
  and came back later" — the frontend has no `user_id` to send at that
  point, only the email the user re-types.
- Letting `register()` itself re-issue a fresh OTP for an existing,
  still-unverified account conflates two different intents (sign up vs.
  resend) into one call and would have required loosening its uniqueness
  check, which is otherwise a clean, spec-independent invariant.

`AuthService.resend_otp(email)` (`auth.py`) looks the user up by email,
rejects a nonexistent account (`UserNotFound`, 404) or an already-verified
one (`AlreadyVerified`, 409), and otherwise regenerates the
`VerificationRecord` in place — fresh `otp_hash`/`otp_expires_at`,
`otp_attempts` reset to 0 — mirroring `register()`'s own OTP-issuing block.
It returns the `User`, and the route returns the same `RegisterResponse`
shape (`{user_id}`) `register()` does, **not** a bare 204: the frontend's
main use of this endpoint is recovering from a `register()` 409 with no
`user_id` of its own, so the response has to hand one back for the
subsequent `verify_otp` call to use.

`SignUpWizard.tsx`'s account-creation step now catches a 409 from
`register()` and calls `resend-otp` with the same email before giving up —
if that succeeds (account exists, still unverified), it proceeds straight
to the OTP screen with a "we've sent a fresh code" notice instead of
stopping at a dead-end error; only a second 409 (genuinely already
verified) surfaces as "log in instead." The OTP screen also gained a
plain "Resend code" button for the simpler in-session case (code expired
or attempts exhausted, tab still open).

**Code:** `cohab/services/auth.py` (`AuthService.resend_otp`,
`UserNotFound`, `AlreadyVerified`), `cohab/api/auth.py`,
`cohab/api/schemas.py` (`ResendOTPRequest`),
`tests/api/test_auth.py`; `frontend/src/api/auth.ts`,
`frontend/src/api/types.ts` (`ResendOtpRequest`),
`frontend/src/features/auth/SignUpWizard.tsx`.

### D-10.2 Uploaded image content is sniffed, not trusted from the declared `Content-Type`

**Gap:** `uploads.py`'s `save_image` validated only the client-supplied
`Content-Type` header against `ALLOWED_CONTENT_TYPES` — no check that the
bytes actually are what they claim to be — before writing to disk and
serving them back at `/media/<name>` through a plain `StaticFiles` mount
with no `X-Content-Type-Options` header. Not spec-sourced (PRD/spec don't
mention file validation at all).

**Decision:** `_sniff_image_type(contents)` (`uploads.py`) checks the
file's real magic bytes against the three formats `ALLOWED_CONTENT_TYPES`
already allows — JPEG (`FF D8 FF`), PNG (the 8-byte PNG signature), WebP
(`RIFF` at offset 0, `WEBP` at offset 8, since WebP is one of several
RIFF-container formats sharing the same 4-byte prefix). `save_image` now
rejects (`UnsupportedImageType`, the existing exception — no new one
needed) whenever the sniffed type doesn't match the declared
`Content-Type`, on top of the existing header and size checks. The magic-
byte signatures themselves are implementation detail, not sourced from any
document, same footing as `LOCALITY_BUDGET_RANGE` (D-3.1) and other
proposed constants flagged in their own module.

Separately, `/media` now goes through a small `_NoSniffStaticFiles`
subclass (`main.py`) that adds `X-Content-Type-Options: nosniff` to every
served response — defence in depth on the serving side, in case a future
upload path is added that doesn't route through `save_image`'s own check.

**Code:** `cohab/services/uploads.py` (`_sniff_image_type`,
`_MAGIC_SIGNATURES`), `cohab/main.py` (`_NoSniffStaticFiles`),
`tests/api/test_uploads.py`.

### D-10.3 N+1 on the moderation queue closed with query-site `selectinload`, not a `relationship()`-level `lazy=`

**Gap:** `Report.reporter`/`Report.reported_user` (`models/safety.py`) have
no eager-loading, and `api/moderation.py`'s `_summary`/`_detail` both
dereference `.reporter.full_name`/`.reported_user.full_name` per report —
two extra queries per row on every `GET /moderation/reports`. Distinct from
the N+1s already accepted in D-9.6: those are offline, manually-run scripts;
this is a live, moderator-facing endpoint that's realistically polled.

**Decision:** eager-load at the query call sites in
`moderation_queue.py` (`list_reports`, and `get_report` — switched from
`session.get`, which doesn't accept loader options, to an equivalent
`select`), via `selectinload(Report.reporter)` /
`selectinload(Report.reported_user)`, rather than adding
`lazy="selectin"` to the `relationship()` declarations themselves. No
`lazy=` precedent exists anywhere in `models/` — query-site loading is more
surgical, since it's this one endpoint that needs it, not necessarily every
future caller of `Report`. `selectinload` over `joinedload`: both are
to-one relationships here, so the fan-out risk `joinedload` usually avoids
`selectinload` on doesn't apply either way, but `selectinload` keeps the
base `Report` query itself un-joined and easier to read, and matches
`selectinload`'s established use elsewhere in this codebase's eager-loading
(offline scripts' `_load_candidates`) more closely than `joinedload` would.

**Code:** `cohab/services/moderation_queue.py` (`list_reports`,
`get_report`).

### D-10.4 `GET /matches?limit=` validation, and the ranker's tie-break, promoted from code comments to logged decisions

**Gap 1 (`/matches?limit=`):** `limit: int = 10` had no bounds — a negative
value wasn't rejected and flowed into `ranker.rank(subject, pool)[:limit]`,
which under Python slicing semantics silently drops candidates from the end
rather than erroring, instead of the intended 422.

**Decision:** `limit: int = Query(default=10, ge=1, le=5000)`
(`api/matches.py`) — the upper bound can't be a tight cap like 100, because
`recompute.py`'s `RECOMPUTE_LIMIT` and the test suite's `LARGE_LIMIT` both
already rely on `limit=3000` as an established "effectively unlimited"
convention for walking a pilot-scale pool in one pass; 5000 sits comfortably
above that existing usage while still rejecting a pathological value. Not
spec-sourced — PRD/spec don't set a limit or a default.

**Gap 2 (ranker tie-break):** `MatchRanker.rank`'s sort key
(`ranker.py`) — `-combined_score`, then `-min(score_ab, score_ba)`, then
`user_id` — has no basis in the matching spec and had never been logged as
a decision, unlike every other undocumented constant in this codebase.

**Decision:** the tie-break is kept as written — it isn't wrong, just
previously undocumented. Second key prefers the *less lopsided* pair (the
higher of the two directional scores' minimum) over one that scores well
for only one party, which is the same asymmetry-aware spirit as the
harmonic-mean combination itself (CLAUDE.md: "not the arithmetic mean,
which would hide a match that suits only one party" — extended here to
break ties the same way, not just to compute the primary score).
`user_id` last is purely for a stable, deterministic order when the first
two keys are equal; it carries no matching-quality meaning of its own.

**Code:** `cohab/api/matches.py`, `cohab/services/matching/ranker.py`,
`tests/api/test_matches.py`
(`test_get_matches_rejects_out_of_range_limit`).

### D-10.5 Screen-by-screen mockup fidelity review — two content fixes, two documented scope gaps, everything else confirmed consistent

**Method (user-directed — a visual comparison, not just a content/copy read).**
The two root-level mockups (`Cohab Desktop.html`, `Cohab Prototype.html`) were
rendered and driven with Playwright — `Cohab Desktop.html`'s 14-screen switcher
clicked through screen by screen, `Cohab Prototype.html`'s 17 phone-frame
tiles (`#s0`–`#s13` plus bonus `#sSaved`/`#sProfile`) scrolled to and
screenshotted individually — rather than relying on the earlier session's
text-only decode of the bundled artifact JS. The live app was screenshotted
the same way: two fresh accounts registered and matched through the real
`uvicorn`/`vite dev` stack (backend on `:8000`, frontend on `:5173`, `/api`
proxied per `vite.config.ts`), reaching match list/detail, chat, contact
share, report, block, and — as a second account flipped to
`is_moderator` — the moderation queue, report review and analytics screens.

One false alarm caught before it became a finding: a `fullPage` screenshot
of match detail appeared to show the sticky "Open chat" action bar
overlapping the middle of the attribute table. A viewport-only (non-stitched)
screenshot showed it rendering correctly, pinned to the bottom as intended —
Chromium's full-page screenshot stitching doesn't handle `position: fixed`
elements correctly, and this was a screenshot artifact, not a bug. (Same
category of caution D-7.7 already flagged: verify before filing, the shared
tooling can lie.)

**Confirmed consistent — re-checked, no new gap:**
- Screens 1–8 (auth through match detail): D-5.1/D-5.4/D-5.5's documented
  resolutions all still hold under a live screenshot, not just a code read —
  including D-5.5's "scores, not raw answers" breakdown table, verified
  rendering exactly as decided.
- **Chat screen — resolved, not a gap.** `Cohab Desktop.html`'s chat screen
  is a two-pane inbox (thread list + conversation), which the single-thread
  built `ChatThread.tsx` doesn't match. But `Cohab Prototype.html`'s *mobile*
  chat screen (`#s9`) is single-thread only, identical in structure to the
  built screen (back arrow, name header, overflow menu, message bubbles,
  composer) — checking only the desktop mockup would have wrongly flagged
  this. CLAUDE.md is explicit that mobile-first is the priority ("Build at
  the small breakpoint and widen — not the reverse"), so the built app
  correctly follows the mobile mockup; the desktop two-pane inbox was never
  built and shouldn't be, absent a decision to invest in a wider layout.
- Match detail's "Report this profile"/"Block" — the mockups show these as
  either two always-visible plain-text links (Desktop) or an overflow menu
  reaching Report only (Prototype, with Block only offered as a chained
  post-report step). The built `SafetyActions` component gives a single
  "Report or block" entry point with both options immediately visible in one
  small menu, reused identically on match detail and chat — arguably a
  reasonable synthesis of both mockups rather than a literal copy of either,
  and consistent with itself everywhere it appears.
- Blocked-users screen: no dedicated screen exists in either mockup (only an
  unlinked "Blocked people ›" placeholder in Prototype's bonus Profile tile)
  — already fully explained by **D-7.8** (new scope, raised with the user
  directly, built on request).
- Analytics dashboard: zero evidence of this screen in either mockup —
  already fully explained by **D-8.6**'s "deliberate v1/v2 scope tension"
  entry.
- Feedback screen's outcome taxonomy differs from the mockups' UX-facing
  categories (a friction-category picker or a 1–5 scale) — already a
  deliberate, documented design (**D-8.3**), built around PRD §12's
  Kaplan-Meier survival needs rather than the mockups' categories.

**Two known gaps, fixed this session (per the user's decisions, see top of
this Phase 10 section):**
1. Contact-share withdraw-before-mutual — built, verified rendering
   ("Cancel" appears under "Waiting for them…", disappears once withdrawn).
2. Report+block chaining — built, verified end-to-end (submitting a report
   renders "Also block {name}" on the success screen, opens the existing
   block-confirm dialog).

**Two real gaps found, left undocumented no longer — logged here as
deliberate deferrals, not built this session (out of a hardening pass's
scope; each is a genuine feature addition, not a screen-polish fix):**
1. **Match list has no filtering or sorting.** Both mockups' match-list
   screen has a working-looking filters sidebar (monthly rent range,
   locality checkboxes with per-locality counts, room type, move-in window,
   seeker type) and a sort control (Compatibility / Rent / Distance). The
   built `MatchList`/`MatchCard` screen has none of this — a plain ranked
   card list with no client-side or server-side filtering at all. This is a
   real, previously unflagged gap dating back to Phase 5 (not mentioned in
   D-5.1/D-5.2/D-5.4/D-5.5) — missed because Phase 5's review focused on
   content/data-shape gaps, not interactive chrome. Building it properly
   needs either a larger default fetch to filter client-side or new backend
   query parameters, plus real frontend filter state — a genuine feature,
   not a fix. Left for a future phase.
2. **Moderator queue is far simpler than the mockups' admin console.** Both
   mockups show filter tabs (Open/Under review/Escalated/Dismissed), a
   search box, an account-facts grid (verification status, prior report
   count, match count, contact-shares count, messages sent/flagged), richer
   evidence with per-message auto-flag badges, and a visible append-only
   action log. The built `ModerationQueue`/`ReportReview` is a two-bucket
   list and a plain claim/resolve form — everything the backend policy
   itself needs (D-7.1–D-7.8) is present, just not the fuller admin UI.
   Treated the same way D-8.6 already treats the analytics dashboard: a
   deliberate, pilot-scale minimal build, not an oversight — a handful of
   moderators reviewing a pilot's report volume don't yet need search or
   filter tabs. Revisit if moderation volume grows.

**One cosmetic gap, noted, not built (infra-scope, same reasoning as
D-4.5/D-5.3's "no new infra the pilot doesn't need"):** the login mockup
shows a "Forgot password?" link and a "Keep me logged in" checkbox; the
built login screen has neither. A real password-reset flow needs email
delivery, which doesn't exist (D-4.5: `ConsoleOTPSender` only) — building
the link without the flow behind it would be worse than omitting it. "Keep
me logged in" has no built behaviour to control either, since the session
cookie already lasts the full `SESSION_TTL_DAYS` regardless.

**Code:** `frontend/src/features/chat/ContactShare.tsx`,
`frontend/src/features/safety/{ReportDialog,SafetyActions}.tsx`,
`backend/cohab/services/contact_share.py`, `backend/cohab/api/chat.py` (the
two fixes above); no other code changed by this entry — the rest is
observation only.

### D-10.6 `/code-review high` pass over the whole hardening diff — six real findings fixed, two accepted as-is

**Requested by the user** before committing this hardening pass, same
precedent as D-6.6/D-8.8/D-9.6. Nine findings came back; one was refuted on
verification (a hypothesized `None` return from `BlockService.block()` —
its premise doesn't hold under Postgres, and the sole caller discards the
return value anyway), six were real and fixed, two are recorded here as
reviewed-and-accepted rather than fixed.

**Fixed:**

1. **Three more check-then-insert races, same family as findings #1-3 this
   diff already fixed, missed the first pass.** `MatchesService._upsert`
   (`match_score`'s pair-unique constraint), `FeedbackService.submit`
   (`feedback`'s `UNIQUE(score_id, submitted_by)`), and
   `get_or_create_moderator` (`moderator.user_id`'s unique constraint) all
   had the identical unguarded shape. `submit`/`get_or_create_moderator`
   use the same full-`session.rollback()` pattern as findings #1-3 (each
   runs standalone, nothing else to lose). `_upsert` needed a different
   shape: `MatchesService.get_matches` calls it once per ranked candidate
   inside **one transaction**, so a full rollback on a race would discard
   every other candidate's already-upserted row from the same batch, not
   just the racing one — a `session.begin_nested()` SAVEPOINT scopes the
   rollback to just that row instead. Fixing `_upsert` surfaced its own bug
   during implementation: the first attempt flushed the new row *before*
   `weight_set_id`/`score_ab`/etc. were populated (those were set later in
   the original code, right before the *existing* final flush), which
   turned every single new-match insert into a `NOT NULL` violation, not
   just races — caught immediately by the full test suite (26 failures),
   fixed by populating the row's fields before either the SAVEPOINT-guarded
   insert-flush or the plain existing-row-update-flush, via a shared
   `_refresh_if_suggested` closure so both paths apply the identical logic.
2. **`claim()`/`resolve()` re-lost the N+1 fix (D-10.3) via post-commit
   attribute expiry.** Both call the now-eager-loaded `get_report()`, but
   SQLAlchemy's default `expire_on_commit=True` expires every attribute on
   every session object after `self.session.commit()` — including the
   `reporter`/`reported_user` relationships just eager-loaded — so
   `api/moderation.py`'s `_detail()` re-triggered a fresh lazy load per
   relationship on next access, silently reintroducing the exact N+1 D-10.3
   closed, just on the two POST actions instead of the GET list. Fixed by
   returning a fresh `self.get_report(report_id)` after `commit()` instead
   of the now-expired in-memory object.
3. **`/auth/resend-otp` had no rate limit of its own.** Unauthenticated,
   and — unlike `verify_otp` — nothing bounded how often it could be
   called. Added `RESEND_OTP_COOLDOWN_SECONDS` (proposed, 30s,
   `core/config.py`), checked against the current record's implied issue
   time (`otp_expires_at - OTP_TTL_MINUTES`); a call inside the cooldown
   raises `ResendTooSoon` → 429. This is a narrower fix than the review
   finding's literal framing ("resets `otp_attempts`, turning the capped
   guess budget into unbounded brute force") — each resend also issues a
   **fresh** code, so an attacker's in-flight guesses against the old code
   are worthless the moment a resend succeeds regardless of the attempt
   counter; the real exposure the cooldown closes is unrate-limited
   spamming of the OTP delivery mechanism itself.
4. **`SignUpWizard`'s misleading error message on a non-409 resend
   failure.** The register()-409 recovery path's inner `catch` reported
   "This email is already registered" for *any* resend failure, including
   an unrelated 429 (finding #3, above) or a transient network/500 — now
   only a genuine second 409 gets that message; anything else surfaces its
   own `ApiError.message`.
5. **`report.py`'s median fix (finding #1) shipped without a test**,
   against CLAUDE.md's "tests for anything in `services/matching/`" rule.
   `report.py` itself has no other tests (a manually-run stdout script, per
   its own docstring) — added a minimal, dependency-free regression test
   (`tests/matching/test_report.py`) that mocks `MatchRanker` entirely and
   asserts `_print_yield` prints `median=2.5`, not `median=2`, for a
   four-subject sample — exercises the exact bug class without needing the
   DB-backed candidate pool the script itself runs against.

**Left as-is, judged acceptable at this scale — same precedent as
D-6.6/D-7.3/D-8.6's own "left as-is" sections:**

- **`/auth/resend-otp` is a partial account-enumeration oracle** (404
  unknown email / 409 already verified / 200 unverified). Real, but
  narrower than the review finding suggested: `register()` already leaks
  account existence via its own 409 (pre-existing, not introduced by this
  diff), and `resend-otp` is only ever called by the frontend *after*
  `register()`'s 409 has already confirmed the account exists — so the
  incremental new disclosure is specifically the verified/unverified
  distinction for an email already known to be registered. Closing it
  fully would mean `resend-otp` responding identically for "no such
  account" and "sent," which breaks the very recovery flow D-10.1 built it
  for (the frontend needs a real `user_id` back to reach the OTP screen).
  The new rate limit (finding #3, above) also throttles casual probing.
  Revisit if this moves past pilot scale with a real email backend.
- **`SignUpWizard`'s register()-409 recovery chains two API calls and
  branches the workflow on the second's result** — a genuine tension with
  CLAUDE.md's "the frontend never orchestrates business logic... the
  client issues intent-level requests, not step sequences." Not changed
  here: this exact shape was put to the user directly as a design choice
  (D-10.1's "email-based resend endpoint" question) and confirmed, not
  arrived at silently — reworking it into a single server-orchestrated
  intent-level call is a legitimate future improvement, but redoing an
  explicitly-confirmed decision mid-review wasn't this pass's call to make
  unilaterally.

**Code:** `cohab/services/matches.py` (`MatchesService._upsert`),
`cohab/services/feedback.py`, `cohab/services/moderation_queue.py`
(`get_or_create_moderator`, `claim`, `resolve`), `cohab/services/auth.py`
(`ResendTooSoon`), `cohab/api/auth.py`, `cohab/core/config.py`
(`RESEND_OTP_COOLDOWN_SECONDS`), `tests/api/test_auth.py`,
`tests/matching/test_report.py`;
`frontend/src/features/auth/SignUpWizard.tsx`.

---

## Phase 11 — Dual-mockup visual-parity pass (desktop + mobile), and Saved matches

**Requested by the user**, outside the 9-phase build plan and Phase 10's
hardening scope: rebuild the whole frontend to pixel-match two bundled
Claude-artifact mockups exactly — `Cohab Desktop.html` (13 screens, ≥1220px,
already loosely referenced in Phase 5, D-5.1) and `Cohab Prototype.html` (the
same 13 screens as a 360px mobile flow, not previously used at all). Both
were decompressed from their `__bundler/template` payload to literal
HTML/CSS and read screen-by-screen rather than approximated as Phase 5 did.

### D-11.1 Breakpoint: a custom `cohab-desktop: 1220px` token, not a stock Tailwind size

**Spec:** neither mockup states a breakpoint as such, but the desktop
mockup's own page wrapper is hard-coded `min-width:1220px`, and the mobile
mockup's phone frames are a fixed 360px canvas mock with no responsive logic
of its own (device-bezel/status-bar/home-indicator chrome around the real
content, itself excluded from the build).

**Decision:** added `--breakpoint-cohab-desktop: 1220px` to
`frontend/src/index.css`'s `@theme`, giving a `cohab-desktop:` Tailwind
variant, rather than reaching for `lg`/`xl` (1024/1280px) which correspond
to nothing in either mockup. Mobile is the unprefixed default throughout
(CLAUDE.md's mobile-first rule); `cohab-desktop:` classes bring in the
desktop layout. Screens close enough to reconcile with responsive classes on
one JSX tree use that; screens whose desktop/mobile structure is genuinely
different (questionnaire rail vs. stepped cards, match list sidebar vs.
scrolling chip row, match detail side panel vs. stacked column, chat
two-pane vs. single-thread, the nav shell itself) use two JSX branches
gated by `cohab-desktop:hidden`/`hidden cohab-desktop:block` rather than a
JS viewport check, avoiding layout flash and duplicated data-fetching.

**Code:** `frontend/src/index.css`.

### D-11.2 Score-band colours were already correct — the "extrapolation" comment was wrong, not the code

**Spec:** the mobile mockup's own overview panel states the band legend
verbatim ("Strong 80+ · Good 65-79 · Fair below 65"), and a 79%-scored match
card's progress-bar fill is literally `#7d9c92` — exactly `lib/score.ts`'s
existing `BAND_COLOR.Good`.

**Finding:** `lib/score.ts` already had the correct three-tier
Strong/Good/Fair thresholds and colours, but its own comment claimed the
colours beyond Strong were "a UI extrapolation, not sourced from either
mockup." That comment was stale/wrong — checked before acting on the
original plan's proposal to collapse it to a two-tier system, which would
have replaced correct code with a regression.

**Decision:** left the three-tier band logic unchanged; corrected only the
comment to cite the actual mockup source (mobile overview panel's legend +
the 79% card's bar fill).

**Code:** `frontend/src/lib/score.ts`.

### D-11.3 Saved matches — new scope beyond the PRD, confirmed with the user

**Spec:** not in `COHAB_PRD.md` or `COHAB_MATCHING_SPEC.md`. The mobile
mockup's bottom nav has a "Saved" tab (bookmark a match to compare later)
with no backend support anywhere in the app.

**Decision (confirmed with the user):** built as real new scope — a
`SavedMatch` model (`user_id`, `match_score_id`, `UNIQUE(user_id,
match_score_id)`), `SavedService` (`save`/`unsave`/`list_saved`, reusing
`match_access.load_match` for lookup+authorize and `matches.py`'s existing
explanation-building logic to avoid re-scoring), `POST/DELETE
/saved/{match_id}` + `GET /saved`, and a `SaveToggle` bookmark button on
`MatchCard`/`MatchDetail`. The save-toggle affordance itself has no mockup
source — the mockups only show the resulting Saved *list*, not the action
that populates it — a necessary small addition to make the feature
reachable. `unsave` deliberately doesn't call `load_match`/verify party
status (deletion scoped to `(user.id, match_id)` is a safe no-op either
way, keeping it a true idempotent delete rather than surfacing a spurious
403/404). `list_saved`/the save action deliberately do **not** flip
`match_score.state` from `suggested`→`viewed` — saving isn't viewing.
"Compare these two side by side" (mobile mockup) has no real screen behind
it in the mockup itself (a dead stub) — rendered visually present but
inert, not wired to fake navigation.

**Code:** `backend/cohab/models/saved.py`, `backend/migrations/versions/
2bb5bde5a3e4_saved_matches.py`, `backend/cohab/services/saved.py`,
`backend/cohab/api/saved.py`, `backend/tests/api/test_saved.py`;
`frontend/src/api/saved.ts`, `frontend/src/features/matches/SaveToggle.tsx`,
`frontend/src/features/matches/SavedList.tsx`.

### D-11.4 Chat list — a screen the app never had, needed by both mockups for different reasons

**Spec:** the desktop mockup's screen 9 always shows a thread list beside
the active conversation; the mobile mockup's bottom-nav "Chats" tab needs a
landing list before drilling into one thread. Neither the PRD nor the
pre-Phase-11 app had any such list — `ChatThread.tsx` only ever rendered a
single thread keyed by `matchId`.

**Decision:** built `ChatList.tsx` sourced entirely from the existing `GET
/matches` data (no new backend endpoint) filtered to `state` ∈
`{chatting, contact_shared}`. This required one small, additive backend
change: `MatchListItem` didn't actually carry `state` (only
`MatchExplanationResponse` did) — added `state: str` to
`MatchListEntry`/`MatchListItem`, populated from the `MatchScore` row
`MatchesService.get_get_matches()` already loads (zero extra queries), and
threaded the same field through `SavedMatchEntry`/`SavedMatchOut` since it
shares the same response shape. A genuine deviation from "no backend change
needed" — logged per CLAUDE.md rather than left implicit. Desktop and
mobile both navigate a row tap to the existing `/matches/:matchId/chat`
route rather than building nested `/chats/:matchId` routing or reaching
into `ChatThread`'s internals. No last-message snippet/timestamp/unread
indicator is shown — no such field exists on `MatchListItem` and none was
fabricated; each row shows city/budget instead. The mobile chat-list's
visual language (44px avatar, single summary line) has no dedicated mockup
frame (the prototype's own `s9` jumps straight to its one demo thread) —
adapted from the mobile mockup's own "Saved" screen row convention as the
closest analogous "condensed list row on mobile" pattern.

**Code:** `frontend/src/features/chat/ChatList.tsx`;
`backend/cohab/services/matches.py` (`MatchListEntry.state`),
`backend/cohab/api/schemas.py` (`MatchListItem.state`),
`backend/cohab/api/matches.py`, `backend/cohab/services/saved.py`
(`SavedMatchEntry.state`).

### D-11.5 Profile hub — built, real data where it exists, visibly-disabled where it doesn't

**Spec:** not in the PRD. The mobile mockup's fourth bottom-nav tab and the
desktop mockup's top-nav "Profile" link (which pointed nowhere in the live
app) both imply a settings hub screen that never existed.

**Decision (confirmed with the user):** built `ProfilePage.tsx` at a new
`/profile` route. Rows with a real backing feature link there ("Blocked
people" → existing `/blocked`; "Required/optional questions answered"
counts computed from real `ProfileOut.questionnaire` keys against
`REQUIRED_QUESTIONNAIRE_KEYS`, not fabricated — this data gap turned out to
be closeable, not a true gap). Rows with no backing feature ("Consent and
data", "Pause my profile") render visibly per the mockup's row language but
genuinely inert — muted, non-interactive, a "Coming soon" tag, no route, no
fake action. The desktop layout has no mockup source at all (none of the
13 desktop screens is a Profile screen) — built using the same card/`Eyebrow`
language as the desktop mockup's other single-column screens (Contact
Share/Report's `680–760px` max-width convention), a judgment call, not
extraction. `seeker_type` has no edit route anywhere in the app (set once
at registration) — rather than invent one, the hub only shows a "My
listing" row (real `/onboarding/listing`) for `has_place` users and omits a
seeker-type row entirely for `needs_place` users.

**Code:** `frontend/src/features/profile/ProfilePage.tsx`.

### D-11.6 Moderator queue and analytics stay desktop-only, as the mockup itself intends

**Spec:** the mobile mockup renders screen 13 once, at 1280px, with its own
overview text stating the exception explicitly: "moderators work at a desk
with evidence side by side, not on a phone." Confirmed with the user rather
than assumed.

**Decision:** no mobile/responsive layout for `/moderation`,
`/moderation/reports/:reportId`, `/analytics` — a dark-shell desktop-only
treatment (`cohab-dark-*` tokens: `#14201f` bar, `#4a5654`/`#3c4745`
borders, `#eceae5`/`#b6c0bd`/`#8d9996` text), with only a `min-width` +
horizontal-scroll guard so the table doesn't visually break if resized
narrow — not true mobile responsiveness, deliberately. `ModerationQueue.tsx`
and `ReportReview.tsx` build the dark bar inline rather than through the
shared `AppShell` (confirmed neither route was ever wrapped in `AppShell`
to begin with — the light header was only ever pulled in by those two
components importing it themselves, so dropping it created no
double-header). The mockup shows list+detail as one two-pane screen with
client-side selection; the app keeps them as the two separate routes it
already had (`/moderation` and `/moderation/reports/:reportId`) rather than
merging into one — each restyled faithfully to its half of the mockup. A
true single-route merge is a follow-up, not done in this pass, since it's a
routing-structure change, not a visual one.

**Code:** `frontend/src/features/moderation/ModerationQueue.tsx`,
`frontend/src/features/moderation/ReportReview.tsx`.

### D-11.7 Shared primitives consolidated, several judgment calls on merged patterns

**Decision:** built/fixed shared primitives once rather than per-screen:
`ui/dialog.tsx` (replacing six previously hand-copied modal wrappers —
desktop renders a centered panel, mobile a bottom-sheet/full-screen sheet
per the mobile mockup's outcome-feedback `✕`-dismiss pattern),
`OptionRadio.tsx`, `FactsGrid.tsx`, `Tab.tsx`, `Eyebrow.tsx`, `Logo.tsx`
(deduplicating wordmark+badge markup previously copy-pasted in `AppShell`/
`AuthPage`), `BottomNav.tsx`, `MobileStepHeader.tsx`, `ui/select.tsx`.

Two components each unify mockup treatments that never co-occur on a single
screen, rather than being screen-specific: `OptionRadio` merges desktop's
12px-radius rectangular row (15px ring dot) and mobile's 30px-radius pill
(18px ring dot) into one component sized via `cohab-desktop:` variants.
`MobileStepHeader` merges the mobile mockup's screen-2 header (step label +
minutes-left, no back arrow) and its screens 3/5/6 header (back arrow + step
label, no minutes-left) into one component with both fields optional.

The PII-warning banner (chat composer) is an **inline card**, not a
`Dialog`, on both breakpoints — both mockups show it `sc-if`-gated inline
above the composer, not as a modal overlay; the earlier hand-rolled
`fixed inset-0` PII modal was replaced accordingly rather than migrated onto
`Dialog` as originally planned for the other five modals.

The outcome-feedback screen's mobile 1–5 rating scale and desktop's 7-option
"biggest friction" chip set are **not the same question** (ordinal
"how well overall" vs. categorical "what went wrong") and neither has a
backing field on `FeedbackRequest` (which only has `outcome` and
`cohabitation_duration_days`) — rather than silently discard whichever one
doesn't map, both were omitted; only the real `outcome` chip question (both
mockups' "Are you still living together?") is implemented, using the
existing `COHABITING_OPTIONS`/`REJECTED_OPTIONS` unchanged. Report reasons
similarly stayed on the existing 8-value `ReportReason` enum from
`copy.ts` — the mockups' two-line reason descriptions are template
placeholders with no literal copy in either extract, so `OptionRadio` shows
single-line labels only rather than inventing sub-copy.

**Code:** `frontend/src/components/ui/dialog.tsx`,
`frontend/src/components/{OptionRadio,FactsGrid,Tab,Eyebrow,Logo,BottomNav,
MobileStepHeader}.tsx`, `frontend/src/components/ui/select.tsx`;
`frontend/src/features/chat/ChatThread.tsx` (inline PII banner);
`frontend/src/features/matches/FeedbackDialog.tsx`,
`frontend/src/features/safety/ReportDialog.tsx`.

### D-11.8 Known residual gaps from this pass, not fixed here

- No live browser/visual verification was performed in the session that
  built this — the Chrome browser-automation tool was unavailable in that
  environment. Verification was `tsc --noEmit` + `npm run build` (clean)
  plus the full backend suite (313/313 passing) after every change, and a
  curl-level smoke test confirming new routes mount and require auth
  (401, not 404). A real cross-browser, both-breakpoints visual walkthrough
  against the two mockups is still owed before calling this pixel-perfect
  in fact rather than in code.
- No unread-message-count data source exists yet, so `BottomNav`'s Chat tab
  badge never renders a number — would need either a new lightweight
  endpoint or client-side computation from existing `is_read` flags across
  threads.
- `ChatList.tsx` (desktop) has no live inline thread preview in its right
  pane (a static placeholder) — a real two-pane desktop experience needs
  `ChatThread.tsx` split into a route wrapper plus a presentational
  component taking `matchId` as a prop; not done here to avoid touching a
  file another part of this same pass was independently rebuilding.
- Moderator queue/report-review's list+detail split stays two routes
  instead of the mockup's single two-pane screen (D-11.6).
- A few desktop screens have no mockup source at all (Saved, Profile,
  Analytics) and used the existing token/card language by extension rather
  than literal extraction — flagged individually above, not silently
  presented as mockup-sourced.

### D-11.9 Real OTP email delivery via Resend, closing the placeholder D-4.5 flagged

**Spec/prior state:** D-4.5 built `ConsoleOTPSender` as the only
`OTPSender` (services/otp.py) — logs the code instead of emailing it — with
its own docstring flagging "a real email sender is a documented future
swap-in." Through Phase 10 this was never closed: sign-up only worked for
whoever could see the backend process's own console output, which is fine
for a single developer testing locally but not for anyone else, including a
real pilot user.

**Decision (confirmed with the user):** added `ResendOTPSender`
(services/otp.py), calling the Resend transactional-email API directly via
`httpx` (already a dependency) rather than adding an SDK — a single POST,
no reason for extra surface. `get_otp_sender()` (new) picks between it and
`ConsoleOTPSender` based on whether `RESEND_API_KEY` (core/config.py) is
set, so every existing call site (`cohab/api/auth.py`'s four
`AuthService(db, ConsoleOTPSender())` constructions) only needed swapping
to `get_otp_sender()` — no branching logic duplicated at each site. Chosen
over SMTP because the user already held a Resend account and explicitly
did not want the mail sent from their own personal address;
`OTP_SENDER_EMAIL` defaults to Resend's own shared sandbox address
(`onboarding@resend.dev`), not a personal one.

**Known limitation, not solved here:** Resend's sandbox sender only
delivers to the email address the Resend account itself was signed up
with, until a real sending domain is verified in the Resend dashboard.
`ResendOTPSender` has no way to detect this — a recipient other than the
account owner will surface as a Resend API error (`OTPDeliveryFailed`,
502 at the API layer) until that verification is done. This is a real
pilot blocker, not just a dev inconvenience: distinct student recipients
genuinely cannot receive their code until a domain is verified. Flagged
here rather than solved, since domain verification needs the user's own
DNS access to a domain they control (plausibly a `christuniversity.in`
subdomain, plausibly not — an institutional domain the user doesn't
administer isn't guaranteed to be available for this).

**Also acted on:** an API key was pasted into a shared screenshot during
this conversation — recommended the user regenerate it in the Resend
dashboard rather than reuse the exposed one. The key itself was never
typed into any file or command by the assistant; `RESEND_API_KEY` ships
as an empty placeholder in `.env.example`, meant to be filled into the
gitignored local `.env` directly by the user.

**Code:** `cohab/services/otp.py` (`ResendOTPSender`, `OTPDeliveryFailed`,
`get_otp_sender`), `cohab/core/config.py` (`RESEND_API_KEY`,
`OTP_SENDER_EMAIL`), `cohab/api/auth.py`, `.env.example`,
`tests/test_otp.py`.

## Phase 12 — motion layer

### D-12.1 A shared motion token set, not per-screen animation

**Spec:** Neither the PRD nor the matching spec says anything about motion;
the two root-level mockups are static images. This is proposed, not
specified.

**Decision:** all timings, easings and travel distances live in one place
(`frontend/src/lib/motion.ts`) and nothing animates with ad-hoc values.
The tokens are deliberately conservative — 16px of travel, `power3.out`,
0.28s/0.55s/0.9s, no overshoot or bounce — because the mockups' own visual
language is editorial and almost shadowless (a warm off-white page, one
deep-teal accent, 1px hairline borders). Motion that bounced or travelled
40px would read as a different product than the one the mockups describe.
The stagger is bounded (`boundedStagger`) so a long ranked list still
finishes arriving in under half a second rather than scaling with its
length.

**Library:** GSAP 3.13 + ScrollTrigger, chosen over CSS-only or the
IntersectionObserver-plus-classes approach because the scroll-driven
progress rule and the batched list reveals both need scrub/batch behaviour
that is genuinely awkward to hand-roll. Cost: ~+90 kB minified
(~+35 kB gzipped) on a mobile-first pilot — the production bundle went from
roughly 440 kB to 531 kB (163 kB gzipped). Flagged as a real trade-off,
accepted because the motion was explicitly requested.

**Code:** `frontend/src/lib/motion.ts`, `frontend/src/index.css` (motion
layer section), `frontend/src/components/motion/*`,
`frontend/src/hooks/useBarFill.ts`.

### D-12.2 Everything is additive and opt-in — no existing screen was restructured

The pass adds refs, `data-*` markers and wrapper components that render the
same element with the same classes; it does not move markup between
breakpoints or change any resting style. Concretely:

- `Progress` gained an `animate` prop that defaults to **off**, so the
  existing call sites that use a bar as a step indicator rather than a
  score kept rendering statically without being audited one by one.
- `Reveal` takes an `as` prop so a wrapper can *be* the grid/flex child
  rather than adding a nesting level that would change the layout.
- `AuthShell`'s marketing panel and the list stacks became the motion root
  themselves (same className passed through) for the same reason.
- `MatchDetail`'s mobile score bar was extracted into a local `ScoreBar`
  only because `useBarFill` is a hook and `pct` is computed after that
  component's loading/error early returns.

### D-12.3 Reveal targets are pre-hidden in CSS, gated on a JS-set flag

A scroll reveal has to start invisible, and doing that in JS means a frame
of settled content before GSAP's first tick. Doing it in plain CSS means a
blank page if the bundle ever fails to load. The rule is therefore scoped to
`html[data-motion='on']`, an attribute `lib/motion.ts` sets when it
evaluates — so a failed bundle, or a visitor with `prefers-reduced-motion`,
gets a fully visible page with no motion rather than an empty shell.

### D-12.4 Reduced motion skips animations outright rather than shortening them

`prefersReducedMotion()` is checked in every motion component before any
tween is built, and the CSS half of the same contract is a
`@media (prefers-reduced-motion: reduce)` block that forces the final state.
`CountUp` additionally renders its final value as its initial text content,
so the real number is what a screenshot, a copy-paste and assistive tech
all see — never a zero mid-count.

### D-12.5 Where motion was deliberately *not* added

- **The moderator queue table** (`ModerationQueue.tsx`) stays static. It is
  a dense triage table; staggering rows delays the work the screen exists
  for, and a wrapper element would break the bordered row flow.
- **`ChatThread` messages** have no entrance animation. Chat is REST
  polling for the pilot (CLAUDE.md, build plan Phase 6), so every poll
  re-renders the list — an entrance would re-fire on already-read messages.
  Worth revisiting when the WebSocket transport lands and arrivals become
  genuinely event-shaped.
- **`ChatList`'s desktop thread rail** is left alone; it is a compact
  sidebar list where per-row motion reads as noise. Only the mobile stack
  staggers.
- **Rent and budget figures** never count up. Only numbers that *are* the
  point of their block — a compatibility score, a moderator KPI — animate;
  a rent range should be readable the instant it paints.

### D-12.6 Two additions that go slightly beyond "motion"

Both are small and both were absent from the mockups, which draw no
interaction states at all:

- **A focus-visible ring** on every interactive element, in
  `--color-cohab-primary`. Every surface here is keyboard-reachable and a
  polish pass that only exists for mouse users is not one.
- **The `Cohab` wordmark is now an explicit labelled home link**
  (`aria-label="Cohab — go to your matches"`). It already navigated to
  `/matches` — which is where `/` redirects (`App.tsx`) — but it had no
  accessible name and no hover affordance.

### D-12.7 Verification, and what is still unverified

`tsc --noEmit` clean, `npm run build` clean, `oxlint` clean apart from one
pre-existing `OnboardingContext` fast-refresh warning that this pass did
not touch, and the production preview server serves both the page and the
hashed bundle (200). As in D-11.8, **no live browser walkthrough was
performed** — the same visual verification debt still stands, and it is
larger now: ScrollTrigger measures against layout, and this app applies
`zoom: 1.1` to `body` above 1220px (index.css). Chrome accounts for zoom in
`getBoundingClientRect`, so trigger positions should be correct, but that
is reasoned rather than observed and is the first thing to check in a real
desktop browser.

### D-12.8 A pre-hide scoping bug this pass introduced and then fixed

Worth recording because the failure mode is silent and the fix is
structural, not a one-line patch.

The card components carry the `data-reveal-item` marker, but the *container*
is what opts into motion by being a `RevealGroup`. The first version of the
CSS pre-hid every `[data-reveal-item]` on the page regardless. `SavedList`
renders two independent stacks — `MatchCard` on desktop, a local
`CondensedCard` on mobile — and only the desktop stack had been wrapped, so
the mobile saved-matches list was pre-hidden with nothing left to un-hide
it: a permanently blank screen, and one that neither `tsc` nor the build
nor the linter can see.

Fixed twice over: the mobile stack is now a `RevealGroup` too, and
`RevealGroup` stamps `data-reveal-root` on its own element so the pre-hide
rule can be scoped to `[data-reveal-root] [data-reveal-item]`. A marked item
outside a group now renders normally without motion, instead of
disappearing. The same class of mistake can no longer blank content.

**Code:** `frontend/src/features/matches/SavedList.tsx`,
`frontend/src/components/motion/RevealGroup.tsx`, `frontend/src/index.css`.

### D-12.9 Mockup screen inventory, checked against the decoded mockup rather than assumed

The desktop mockup is a bundled page (base64 + gzip in
`Cohab Desktop.html`); its DOM template was decoded and its headings
enumerated, then each was traced to a source file. All sixteen screens have
a counterpart: landing/login, create account, six-digit code, seeker type,
listing form, the twelve required questions, the optional depth questions,
importance weights, match list with filters sidebar, match detail with
attribute breakdown, chats, contact share, report, report acknowledgement,
the 30-day check-in, and the moderator queue with its evidence/decision/
action-log detail.

One element inside a screen is deliberately absent rather than missing: the
check-in's seven-option "What has been the biggest friction, if any?"
question, already documented in `FeedbackDialog.tsx`'s own comment — the
`FeedbackRequest` schema carries only `outcome` and
`cohabitation_duration_days`, so rendering it would mean a control that
silently discards its answer.

Also noted: the mockup's match detail reads "Her listing"; the app uses
"Their listing". A deviation, kept — the app has male, female and
non-binary users and the heading is generated for every candidate.

## Phase 13 — Modal restyle, demo path, and layout density

### D-13.1 Four DB fields exposed that were stored but never returned

`course` on the match-list card, plus `listing_room_type`,
`listing_available_from` (both on `MatchListItem`) and `current_housemates`
(on `MatchListingSummary`), plus `weight_set_version` on the explanation
response. All were already columns; `Candidate.from_orm` already had the
`Listing` in hand, so this costs no extra query. They unblock the mockup's
"Room type" and "Move-in window" filters and its "under weight set v2" line.
Flagged as cosmetic-only in `candidate.py` — never read by Stage 1 or Stage 2.

### D-13.2 Modal phosphor palette replaces the mockup-decoded tokens

**This overrides D-5.1.** The two root-level mockups remain authoritative on
layout and copy but no longer on colour: the user supplied Modal's
dark phosphor-terminal style reference and asked for it applied.

The `--color-cohab-*` token *names* were kept deliberately. Roughly 40 built
screens reference them through `cohab-*` utility classes, so remapping the
values re-themes the whole app from one file. The sweep then fixed what
tokens could not reach: 78 `bg-white`, 32 arbitrary hexes across 39 files,
14 `text-white`-on-lime contrast failures (white on `#7fee64` is unreadable;
Modal's own spec puts `#181818` there), and 6 shadows tuned for a light page.

**Two deliberate departures from the Modal spec, both accessibility floors:**

- Modal forbids non-green chromatic accents. One survives — a desaturated
  brick `#c96a4d` — for destructive actions (block/report/suspend) and the
  "Fair" score band. A destructive button indistinguishable from a neutral
  one is a hazard, and score bands must differ by hue, not only bar length.
- `cohab-primary` is used mainly as a *stroke and text* colour, not a fill.
  Modal rations Lime Pulse to one fill per viewport; a match list of twenty
  lime-filled cards would break the metaphor outright.

Score-band *thresholds* stay mockup-sourced; `lib/score.ts`'s comment was
corrected, since it claimed mockup provenance for colours that no longer
have it.

### D-13.3 Onboarding screens were a dead end when reached from Profile

All four onboarding screens render without `AppShell`. That is right during
first-run signup — a nav bar inviting you to abandon a half-finished profile
is the wrong affordance — but those same screens are the *edit* surface
linked from the Profile hub, and entered that way desktop had no header, no
wordmark and no back button at all (mobile had a bare back arrow).

`components/OnboardingHeader.tsx` renders only when `GET /profile` succeeds,
which is exactly the edit case; a genuine first-run signup still sees the
original uninterrupted flow. Its back button falls back to `/profile` when
`window.history.length <= 1`, since `navigate(-1)` on a pasted URL would
leave the app entirely.

**Found by the user clicking through the running app.** No build, typecheck
or lint can see it. Same class of gap as D-11.8 and D-12.7 flagged.

### D-13.4 Operator screens widened to the app's own 1800px rhythm

The moderator queue was a `max-w-[900px]` card inside an `1800px` container
and analytics was `max-w-2xl` (672px) — roughly 900px of dead space at
common desktop widths, reported by the user.

Both now use the 1800px grid the match list already uses. The queue becomes
two-pane (`1fr | 420px`) with `TriageRail`: unclaimed count, escalated
count, cases past the SLA target, oldest open case, and a reason breakdown.
**Every figure is derived from the `GET /moderation/reports` payload the
table already renders** — no new endpoint, no second query, nothing shown
that the API does not return. Analytics tiles gained a share-of-total bar,
computed from the same dict, because a bare "42 mutual" means nothing
without a denominator.

`SLA_HOURS = 24` in `TriageRail.tsx` is **proposed, not specified** — PRD
§8.3 requires a moderator review step but fixes no turnaround time. The
number comes from the mockup's own "SLA 24h" label and is marked in the code
as a placeholder to confirm before a real pilot.

The moderation wordmark in both `ModerationQueue` and `ReportReview` was a
`<span>` — dead text. Now a `Link` to `/matches`.

**Moderator gating was verified, not assumed:** nav links behind
`user?.is_moderator`, routes behind `ModeratorGate`, and every backend route
behind `require_moderator`. Confirmed live — a logged-in non-moderator gets
403 on `/moderation/reports` and `/analytics/summary`, and 200 on `/matches`
as a control. The user saw those tabs because the demo account genuinely
holds the flag.

### D-13.5 One decorative graphic, confined to the landing panel

`components/CompatibilityField.tsx` — a canvas field where two populations
drift and a line is struck between a pair only inside a distance threshold,
brighter the closer they sit; two "has a place" nodes never link at all.
That is the two-stage matcher as an image: a hard constraint first, a graded
score second.

Confined to the marketing panel on purpose. Modal renders 3D objects on its
marketing site and keeps operator surfaces plain, and the same split holds
here — a moderator queue decorated with figures reads as padding over a thin
feature. Deterministic (fixed PRNG seed) so screenshots are reproducible for
the report, and it paints one static frame under `prefers-reduced-motion`.

### D-13.6 Demo path: the screens existed, they were unreachable

The bulk seed produces ~1550 users and ~43k scored pairs, but no account that
can walk every screen. Three separate causes, none of them "missing pages":
the user's own account had never completed onboarding (hence `/profile` and
`/listing` 404s); Report and Feedback are modals with no route; and six
screens are state-gated, with `cohabiting` having **zero** rows — making the
30-day check-in unreachable by anyone.

`cohab/demo_seed.py` is additive and re-runnable: it creates one demo user
and **promotes that user's own existing `match_score` rows** into each gated
state rather than fabricating scores, so every number on screen is one the
matcher actually produced. It never edits another member's profile and never
touches the ~43k rows Phase 9's evaluation is computed from.

**Side effect worth recording:** making the new accounts matchable required
running `recompute`, which published **`weight_set` v3** (1387 subjects,
88222 rows touched). Historical rows keep their own `weight_set_id`, so the
CLAUDE.md reproducibility invariant holds — but any evaluation re-run now
scores under v3, and the Phase 9 chapter's numbers were produced under v2.

### D-13.7 Test suite was hitting the live Resend API — 322 passing again

`pytest` was at 35 failed / 85 errors, and **not from any change in this
phase**. `get_otp_sender()` selects a sender from environment variables, so
once `RESEND_API_KEY` was set in a local `.env` (the normal state after
D-11.9), every `/auth/register` in the suite posted to the live Resend API,
got 403, surfaced as 502, and failed as `KeyError: 'user_id'`.

The suite also *structurally* depends on `ConsoleOTPSender`: every fixture
recovers the code by reading the `cohab.otp` log record, and that is the only
implementation which writes one. An autouse fixture in `tests/api/conftest.py`
now pins it, patched at the `cohab.api.auth` reference because the route
handlers call `get_otp_sender()` directly at request time rather than taking
it as a FastAPI dependency — `app.dependency_overrides` cannot reach it.
Full suite: **322 passed, 0 failed.**

### D-13.8 Profile hub: two columns, and a rail built from data already fetched

The profile screen was a 720px column centred in an 1800px viewport, so most
of the screen was empty — reported by the user, not caught by any check. The
fix is a two-column grid whose right rail renders ten `preference_profile`
fields (`city`, `budget_*`, `move_in_date`, `gender_preference`, both allergy
lists, `has_pet`, `pet_tolerance`, `smoking_dealbreaker`) that the page's
existing `profile` query already fetched and then discarded.

Split into "Hard constraints" and "How you live" deliberately: the two behave
differently in the matcher — Stage 1 excludes outright, Stage 2 scores — and
that distinction is the single thing users most often misread. The copy on
each panel says so.

### D-13.9 Profile editing: `PATCH /auth/me`, scoped to three fields

`AccountUpdateRequest` accepts `full_name`, `course` and `phone_number` only.
Email, gender and `seeker_type` are excluded on purpose: email anchors the
institutional verification, and gender and seeker type are Stage 1 inputs, so
letting them be edited freely from a profile form would silently invalidate
every previously computed `match_score` involving that user. Changing those
belongs behind a re-verification flow that does not exist yet.

`None` means "leave alone" and empty string clears `phone_number`, so a
partial patch cannot blank a field the client did not mention.

### D-13.10 Seeded imagery: generated avatars, not downloaded faces

The obvious approach — pulling portraits from a placeholder API — fails two
tests, and the first is a factual finding worth recording: the free services
that filter by nationality localise **names, not faces**.
`randomuser.me?nat=in` and `?nat=us` were verified to draw from the same
portrait pool (`women/92.jpg` appears under both), so "Indian avatars" from
that source would be a label on generic Western photographs. Second, and more
seriously, attaching photographs of real people to ~1550 fabricated student
profiles is not something that should ship anywhere near a pilot.

So the Indian identity comes from the part of the data that genuinely is
Indian — the names `seed.py` already generates — and the imagery is honestly
synthetic: initials rendered locally with Pillow, gender tinting the palette
rather than deciding a face. Written as **PNG, not SVG**, because
`services/uploads.py` deliberately excludes SVG from `ALLOWED_CONTENT_TYPES`
(D-10.2 — a same-origin SVG can carry script) and seeded files land in the
same `/media` mount as genuine member uploads; emitting a format the upload
path itself rejects would quietly punch a hole in that boundary.

Listing photos remain Picsum (Unsplash-licensed) — rooms, not people.

Auditing this also surfaced a genuine data gap: **five `has_place` users had
no listing at all**, so they would have appeared in matches as someone with a
place and nothing to show. Listings were created and photographed for all
five; final state is 721/721 `has_place` users with a photographed listing
and 0 users without an avatar.

### D-13.11 Ambient field on every screen, and the bugs that exposed

The compatibility field (D-13.5) was confined to the login panel. At the
user's request it now sits behind every screen via `AmbientField`, a single
`position: fixed` canvas — fixed rather than absolute so one canvas covers
the viewport on every route, instead of one per page stretching to that
page's scroll height (on the analytics screen that would be an enormous
canvas and a node count to match). Behind live data it runs far sparser
(`density` 46,000 vs the hero's 14,000) and dimmer, because the failure mode
on an operator screen is a queue that looks decorated rather than legible.

Three real bugs surfaced only by driving the running app in a browser; none
were visible to `tsc`, the build, or the linter:

1. **Opaque roots hid the canvas.** `AppShell` and both moderation screens
   painted their own background, which covered a `-z-10` canvas completely.
   The page black now comes from `body`, which sits below both.
2. **`MatchCard` stretched square avatars.** The 186x150 landscape photo tile
   from mockup screen 7 was scaling a 256px square initials PNG to fill it,
   rendering the letters as huge cropped type. Generated avatars (detected by
   the `/media/avatar-` prefix via `isGeneratedAvatar`) now fall back to the
   circular treatment; a genuine uploaded photo still fills the tile.
3. **Back-button gaps.** `RequiredQuestionnaire` had no mobile back control at
   all — the other three onboarding screens each draw their own, and
   `OnboardingHeader` was `hidden cohab-desktop:block` — so editing the
   questionnaire from Profile on a phone was a dead end. Both moderation
   screens also lacked one. `hasOwnMobileBack` keeps the three screens that
   already have an arrow from stacking a second.

`/matches` deliberately keeps no back button: it is home, and "back" there
exits the app.

**Duplicate React keys — a labelling bug, not a keying bug.** The console
warned about duplicate keys in `ProfileSummaryRail`. The first hypothesis
(colliding agreement sentences in `MatchCard`) was **wrong and was reverted**:
testing the renderers showed zero overlap between every pair of label sets.
The real cause is that `titleFor` returned the question *group* title, and
several distinct questions share a theme — "Guests" covers frequency and
overnight guests, "Money" covers when you pay and how rent splits, and "Life
stage" is shared by four questions. The rail therefore listed "Life stage"
four times against four unrelated values. `titleFor` now falls back to the
theme only when it belongs to a single question, and to the question's own
title otherwise; rows are keyed on the questionnaire key.

### D-13.12 Light theme: token overrides, not a second stylesheet

Tailwind v4 compiles `@theme` values into the stylesheet, so a runtime switch
cannot rewrite them — but it can redefine the same custom properties at a
later selector. `:root[data-theme='light']` overrides ~25 tokens and every
`cohab-*` utility picks them up through `var()` at use time, so all ~40
screens re-theme without a component change. This is the same indirection
that made the Modal remap cheap (D-13.2) paying off a second time.

A translation into daylight, not an inversion. Rules kept: lime stays the
only accent but drops to `#2f7d1e` for text (`#7fee64` on white is ~1.4:1,
illegible), while filled CTAs keep a bright fill with dark text on it;
surfaces still step page to card to tint; and the destructive brick stays
chromatic and distinct from the accent, the accessibility floor from D-13.2.

Three states, not two — `light`, `dark`, `system` — because "system" is a real
preference that keeps tracking the OS. A binary toggle would silently freeze
the user on whichever theme their OS happened to use the first time they
touched the control. The choice is applied by a small inline script in
`index.html` **before first paint**, since deferring to React paints the
default theme first and then swaps.

Two things could not read the tokens and needed explicit handling: the canvas
paints raw pixels (it picks a palette per theme and repaints via a
`MutationObserver` on `data-theme`), and ~29 hardcoded hex utilities scattered
through components were dark-only colours that would have been stranded on a
light ground — those are now tokens (`cohab-score`, `cohab-warn`,
`cohab-track`, `cohab-bar-mid`). `text-[#0a0a0a]` was deliberately left as a
literal: it is the dark text sitting on a bright lime or brick *fill*, and
that fill stays bright in both themes.

### D-13.13 Nav active state is computed, not left to prefix matching

Chat and contact-share live under `/matches/:id/...`, so `NavLink`'s default
prefix matching underlined "Matches" while a chat thread was open and left
"Chat" inactive — reported by the user. `AppShell` now computes `isChat` and
`isMatches` from the pathname, mirroring what `bottomNavTab` already did on
mobile. Match detail (`/matches/:id`) correctly stays under Matches.

### D-13.14 Light theme is the mockup's green-on-beige, not a lightened phosphor

D-13.12 shipped a light theme derived from the Modal palette — lime darkened
until it was legible on near-white. The user asked instead for the
green-on-beige of `Cohab Desktop.html`, which is also the palette D-5.1
originally decoded before the Modal remap (D-13.2) replaced it.

Values were extracted from the mockup by frequency rather than eyeballed from
a screenshot: `#eceae5` page ground, `#f5f4f0` cards, `#0f5f52` deep green
primary, `#a8442a` brick, `#eef4f2` selected-row mint, and the
`#14201f`/`#3f4d4a`/`#63706d`/`#7d8a86` text ramp. The app now carries both
identities honestly — the phosphor terminal in dark, the mockup's daylight
palette in light — rather than one lightened palette matching neither
document.

**This invalidated an assumption recorded in D-13.12.** That entry justified
leaving `text-[#0a0a0a]` as a literal because "the fill stays bright in both
themes". True for lime; false for `#0f5f52`, where near-black text on a dark
green fill is unreadable. On-fill text is now itself a token,
`--color-cohab-on-fill` (near-black in dark, white in light), and all 14
occurrences were replaced. No hardcoded colour utilities remain in the
component tree.

**Three UI gaps closed in the same pass, all reported by the user:**

1. **`MatchDetail`'s empty box.** The desktop card rendered a name, a course
   line and ~200px of nothing: the avatar was `cohab-desktop:hidden` and the
   score panel is a fixed-width right column. The avatar now shows at both
   breakpoints, and the explanation cards — fetched by the existing query and
   previously rendered nowhere on this screen — fill the space under the
   name, which is also the most useful thing to read there.

2. **Missing sidebar filters.** The mockup's sidebar has Locality, Room type
   and Move-in window; the app shipped with none of them. Room type and
   move-in window needed no backend change — `MatchListItem` already carried
   `listing_room_type` and `listing_available_from`, but the *frontend type*
   never declared them, so the values arrived and were silently discarded.
   Locality did need adding: it existed on the detail response only, so
   `listing_locality` was added to `Candidate`, the schema and the list
   endpoint (no extra query — the `Listing` is already in hand in
   `from_orm`). Move-in window compares the candidate's `available_from`
   against the viewer's own `move_in_date`, and treats a missing date as
   unfiltered rather than silently excluding the candidate.

3. **Sparser ambient field than intended.** Density 46k → 17k (~2.7x the
   points), node cap 48 → 110, link distance 132 → 172, with opacity dropped
   to 0.45 so the busier field is no louder behind live data.

**Debugging note worth keeping:** the locality field appeared correct in the
schema, the dataclass and a direct `Candidate.from_orm` call, yet was absent
from the HTTP response. Cause was **two uvicorn processes bound to port
8000** — an older one, started before the edit, was serving the requests.
Worth checking `netstat -ano | grep :8000` before concluding that a backend
change did not take effect.

### D-13.15 Two-pane chat, theme-aware avatars, softer filter pills

Four user-reported UI gaps, all in the same pass.

**1. The open conversation hid the other threads.** `/matches/:id/chat`
rendered the conversation alone, so while talking to one person there was no
way to see or reach the others without going back to `/chats` — unlike
WhatsApp Web, which the user named as the reference. `ChatThread`'s own
docstring had already flagged this as ChatList's follow-up.

The thread rail was extracted from `ChatList` into `features/chat/ThreadList.tsx`
(`ThreadRail`, `ThreadRow`, `useThreads`, `CHAT_STATES`) and is now rendered by
both screens: `/chats` is the nothing-selected state, and the thread route
shows the same rail with `activeMatchId` highlighted (green left bar, mint
ground, primary-coloured name). Rather than nested routing or splitting
`ChatThread` into wrapper + presentational halves, the rail simply links to
the existing route — the same navigation mobile already used.

Desktop only. On a phone the list and the conversation stay separate screens,
which is what WhatsApp does too.

*Layout note:* `ThreadRail` carries its own `hidden cohab-desktop:flex` rather
than being wrapped in a visibility div. Wrapped, it became a flex item that
sized to its content, and the rail's right border stopped halfway down the
card instead of running its full height. As a direct grid child it stretches
to the row.

**2. Generated avatars ignored the theme.** `seed_avatars.py` bakes a *dark*
ground into every PNG, so under the light theme the circles stayed dark-green
squares of phosphor type against beige. Since a generated avatar is only
initials on a flat ground — exactly what `Avatar`'s CSS fallback already
draws — `Avatar` now skips the file for generated sources and renders the
fallback, which reads theme tokens. Genuine uploads are photographs and are
still shown as-is. No regeneration of the 1551 PNGs was needed, and none of
the ~40 call sites changed.

The fallback got its own token pair, `--color-cohab-avatar-bg` /
`--color-cohab-avatar-ink`, rather than reusing tint/primary: the two themes
want opposite treatments — dark ground with phosphor initials in dark,
the mockup's solid `#0f5f52` with white initials in light. Verified live:
`rgb(15,95,82)`/white and `rgb(27,38,32)`/`rgb(174,210,164)`, with zero
`img[src*="/avatar-"]` still rendering.

**3. Filter pills read as square boxes.** `Tab` used `rounded` (4px), which
next to the rent `Input`s at `rounded-[10px]` looked like an inconsistency
rather than a choice. Now `rounded-[10px]`, matching them.

**Verification note.** Two intermediate readings during this work were wrong
and are worth recording, because both looked like real bugs:

- A `getBoundingClientRect` measurement said the chat card overflowed the
  viewport (bottom 1064 in a 1000px window). It did not — `document.body.scrollHeight`
  was exactly 1000 and the computed height matched `calc(100vh-170px)`. The
  rect was read against a scrolled page. Changing the offset to `118px` on
  the strength of that reading *introduced* a clipped composer, and was
  reverted. Screenshots caught what the numbers had not.
- A Playwright selector of `a[href*="/chat"]` matches the "Chat" nav link,
  not only thread links, so a "thread rail" assertion was really re-testing
  `/chats`. Anchored to `^/matches/[^/]+/chat$` instead.

### D-13.16 Interaction motion: press feedback, a firmer route transition, and message entrances

The user asked for motion on click and on navigation. An audit first, because
some of it already existed: `PageTransition` was wired into `AppShell` and
`RevealGroup` already re-staggered on `runKey` change. The real gaps were
that the route transition was too subtle to notice and that press feedback
covered only the `Button` component.

**Route transition.** Was `y: 10` over `MOTION.fast` (0.28s) — hardcoded,
bypassing the token system it was supposed to follow. Now `MOTION.pageRise`
(24px) over `MOTION.page` (0.42s), both new tokens in `lib/motion.ts`. Kept
enter-only: an exit animation holds the old screen on-screen after the user
has committed to leaving, which makes every navigation feel slower than it is.

**Press feedback.** `.cohab-press` (scale 0.975 on `:active`) already existed
but was applied only via `Button`. Roughly 20 files use raw `<button>` and had
no active state at all, so the most-clicked controls in the app — filter tabs,
questionnaire option pills and radios, the chat send button, the back button,
save toggle, account menu, photo upload — gave no physical response. The class
is now on the shared components, which covers most call sites at once. No new
CSS: `.cohab-press` already uses longhand transition properties so it composes
with `transition-colors` instead of clobbering it, and reduced-motion is
already honoured.

**Message entrances.** New `components/motion/MessageEnter.tsx`. A sent bubble
fades and scales from 0.96 with `transformOrigin` at the anchored corner, so
it reads as emerging from the composer.

The hard constraint is that ChatThread **polls every 3s**. Animating on render
would make the whole conversation pulse three times a second, so a
module-scoped `seen` set of message ids gates the entrance to genuinely new
messages. Module-scoped rather than component state on purpose: the bubble
unmounts and remounts as the polled list is replaced, so per-component state
would be lost exactly when needed. It is bounded at 500 ids. A `firstPaint`
ref suppresses the animation for history already in the thread when it opens.

**A StrictMode bug this exposed, worth recording.** The first implementation
marked an id seen *before* starting the tween. Under StrictMode's
mount/unmount/remount, the first pass flagged the id and its cleanup reverted
the tween; the second pass then saw `seen=true` and bailed, so the bubble
never moved. This was not merely a dev-mode artifact — any real remount would
hit it. Fixed by marking seen in `onComplete`, with a cleanup-time fallback
guarded on `!el.isConnected` so a genuinely unmounted bubble does not replay
its entrance on the next poll.

**An unrelated theming bug found while adding press to SaveToggle.** The
bookmark had literal `fill`/`stroke` of `#7fee64` — the dark-theme lime —
which stayed lime on the light theme's beige, where it barely reads. Now
`currentColor` driven by `text-cohab-primary` / `text-cohab-subtle`, so it
follows the tokens like everything else. Verified resolving to different
values per theme.

**Verified in-browser, not by inspection:** idle polling produced 0 animated
samples across 40 samples over 10s with 4 bubbles on screen (the churn risk);
a sent message did animate; changing a filter re-staggered the surviving
cards; press class and its transition-property list confirmed present in both
themes; 0 console errors.

### D-13.17 Two favicon files, swapped by the app, not one that self-switches

The first attempt at a theme-aware tab icon was a single `favicon.svg`
carrying its own `@media (prefers-color-scheme: dark)` block. It is the
tidier artefact and it does work — but only against the *operating system*
setting. A favicon is fetched as an independent document: its internal CSS
cannot see `document.documentElement[data-theme]`, so the in-app theme
toggle had no effect on it. With the OS on dark, choosing Light in the
account menu left a dark icon sitting above a light UI. The user reported
this twice before it was diagnosed correctly.

So the icon is now two files, `favicon-light.svg` and `favicon-dark.svg`,
identical in geometry and differing only in palette, with
`lib/theme.ts::applyFavicon` rewriting `link[rel=icon]`'s href.
`applyTheme` is the single choke point every path already funnels through,
so hooking it there covers the toggle, the stored choice on load, and the
OS-flip listener without touching any caller.

Two details that are load-bearing:

- The href comparison is against `new URL(link.href).pathname`, not the raw
  `link.href`. The property reflects an absolute URL carrying the
  cache-busting query, so a naive equality check never matches and the icon
  is rewritten and re-fetched on every theme application.
- `index.html`'s pre-paint script performs the same swap inline. Leaving it
  to React would show the wrong-palette icon until mount, which is the
  favicon equivalent of the flash-of-wrong-theme D-13.12 exists to prevent.
  The static `href` defaults to light so a JS-disabled browser still gets a
  real icon rather than a 404.

**The mark itself:** two overlapping roof forms — two people, one home. The
overlap is the product's actual claim, that this matches on compatibility
rather than listing availability; the shared floor line beneath is the match.
Colours are the app's own tokens. The dark tile is Surface 1 (`#181818`)
rather than the theme's pure-black Surface 0, because a black tile
disappears into a dark browser tab strip and leaves the strokes floating.

Verified in-browser across all four OS/stored-choice combinations at first
paint, and across toggle changes with the OS forced to dark — the case that
was broken. Both files serve 200; the mark stays legible at 16px.

### D-13.18 Post-commit audit ("any bugs, inconsistency or ambiguity") — six findings fixed

**Requested by the user**, same pattern as D-6.6/D-7.8: a full-repo pass
(logic, code, UI) after the f3b3211 commit, rather than a diff-scoped review.
Five of the six were already named, undiagnosed, in that commit's own
message ("known issues... tracked as follow-up"); this pass root-caused each
one to an exact line and fixed all of them, plus one new finding.

1. **`SavedService.save` committed an orphaned bookmark before confirming
   the match was still reachable.** `_entry()` — called *after* `commit()`
   — is what actually loads both candidates and can raise `MatchNotFound`
   (e.g. a party's profile deleted after the match was scored). A caller
   saw a 404 while a `SavedMatch` row had already landed in the DB, silently
   skipped forever by `list_saved`'s own defensive `except MatchNotFound:
   continue`. Fixed by loading both candidates and raising before the
   insert, not after. **Code:** `cohab/services/saved.py`.
2. **Mobile `MatchDetail`'s sticky footer mis-routed `contact_shared`.**
   The desktop side panel renders "Confirm move-in" and "Open chat" as two
   buttons; the mobile footer collapsed them into one, gated on `canChat`
   alone. Since `contact_shared` makes both `canChat` and `canConfirmMoveIn`
   true, the button's *label* correctly read "Confirm move-in" (`primaryLabel`
   already prioritises it) but the button was still wrapped in a `<Link
   to=".../chat">`, so tapping it navigated to chat instead of calling
   `confirmMoveInMutation`. Fixed by gating the `<Link>` wrapper on `canChat
   && !canConfirmMoveIn`; `firePrimaryAction` already handled the
   move-in-mutation branch correctly, so no other logic needed to change.
   Chat is still one tap away via the persistent bottom-nav "Chats" tab.
   **Code:** `frontend/src/features/matches/MatchDetail.tsx`.
3. **`ListingForm`'s "Save as draft" was `type="submit"` on the same form
   as "Save and continue"** — identical validated save, identical
   navigate-to-questionnaire. There is no partial-save shape on the backend
   (`ListingUpsertRequest` requires every field), so "draft" can't mean
   "save incomplete data" without a schema change this pass didn't make.
   It can mean "save what's valid, but don't force the wizard forward" —
   which is what the button now does: a plain `type="button"` handler that
   calls the same `PUT /listing` but skips `navigate()`, showing an inline
   "Saved" confirmation instead. **Code:**
   `frontend/src/features/onboarding/ListingForm.tsx`.
4. **`demo_seed.py` crashed on a sparse seed pool.** `_seed_open_report`
   used `subject`/`reporter` (both `scalar(...).limit(1)`, no guarantee of
   a row) unconditionally — `AttributeError` on `None.id` the first time
   the demo seed ran against a pool with fewer than three active users.
   Fixed with an explicit `None` check on both, printing and returning
   rather than crashing — consistent with the script's own "additive,
   safe to re-run" framing. **Code:** `cohab/demo_seed.py`.
5. **Moderation queue's "Escalated" tab never emptied.** Escalation is
   monotonic by design (D-7.2: a case keeps `escalated=True` after
   resolution), but `matchesFilter`'s `'Escalated'` branch only checked
   `r.escalated`, not status — a `dismissed`/`action_taken` case stayed in
   the Escalated tab forever, indistinguishable from one still needing
   review. Fixed by excluding `CLOSED_STATUSES` from that branch (and from
   the tab's badge count, which had the identical gap). **Code:**
   `frontend/src/features/moderation/ModerationQueue.tsx`.
6. **New finding, not in the commit message: blanking "Full name" in
   Account settings failed silently and desynced the edit form.**
   `update_account` special-cased an empty/whitespace `full_name` by just
   skipping the assignment (`full_name` is `NOT NULL`, unlike
   `course`/`phone_number`, which do normalise an empty string to `NULL`)
   — no error, no signal to the caller, contradicting the function's own
   docstring, which claimed the empty-string-clears rule applied uniformly.
   `AccountPanel.tsx` compounded it: `onSuccess` never resynced the local
   `fullName`/`course`/`phone` state from the server's returned object, so
   a rejected edit left the input showing the rejected (blank) text
   indefinitely, with the "Edit" button not resetting it either. Fixed with
   a new `BlankFullName` exception (400, "full name cannot be blank"),
   a client-side disable on an empty name, and resyncing all three fields
   from the mutation's response on success. **Code:**
   `cohab/services/auth.py` (`BlankFullName`, `update_account`),
   `cohab/api/auth.py` (`update_me`),
   `frontend/src/features/profile/AccountPanel.tsx`.

**One item raised during this pass and then withdrawn, on rereading the
spec:** `Candidate.from_orm` collapsing a `has_place` user's budget band to a
single point (`listing.rent_per_person`) was first flagged here as an
undocumented judgment call. It isn't one — `COHAB_MATCHING_SPEC.md` says
this explicitly, twice: §2's Stage-1 band-intersection rule ("For a
`has_place` member, the listing's rent replaces the band as a point value")
and §7's `budget_proximity` definition ("For a `has_place` member, the
listing rent is the point value"), which is exactly the `budget_midpoint`
computation `candidate.py` implements. No decision was made outside the spec
here, so there is nothing to log — correcting the record rather than
leaving a wrong claim standing. **Code:**
`cohab/services/matching/candidate.py` (`from_orm`, `budget_midpoint`) —
unchanged, and correct as written.

### D-13.19 Deploy-readiness pass: the prod half of "FastAPI serves the static bundle" never existed

**Requested by the user** ("do whatever has to be done for deployment
ready"), after a status check found `cohab/main.py` had no code path for
CLAUDE.md's own documented architecture — `run.cmd` only ever launches dev
mode (`npm run dev` + `uvicorn --reload`, Vite's proxy on top), so the prod
path had apparently never been run, let alone exercised.

**Two problems, not one, and the second is the one that actually bites.**
`npm run build` itself works (563 kB bundle, one non-blocking chunk-size
warning) — the gap is that nothing serves the output, and simply adding a
`StaticFiles` mount would not have been enough:

1. `frontend/src/api/client.ts` calls every endpoint at `/api/...`, but
   every router here is registered at its bare path (`/auth/...`,
   `/matches/...`) — matching what ~330 tests call directly against
   `TestClient(app)`, and what `vite.config.ts`'s dev proxy already forwards
   to after its own `rewrite: p => p.replace(/^\/api/, '')`. With no proxy
   once this app is the only server, `/api/auth/register` needs the
   identical strip to reach the same bare-path handler — done server-side
   now, onto the exact same route table, so zero tests needed to change.
2. **The one that would have silently broken the app.** Several frontend
   *pages* share a literal path with a real API route on this app: `GET
   /matches` is both the match-list page and the match-list data endpoint;
   same for `/profile`, `/saved`. A naive "try the router, serve
   `index.html` on a 404" fallback does not help here, because these paths
   are *not* 404 — the real route matches and returns real API output (a
   401 without a cookie, JSON with one). A browser hard-refresh on
   `/matches` would have rendered raw JSON or a 401 page instead of the
   app. Confirmed live: before the fix, `curl -H "Accept: text/html"
   localhost:8000/matches` returned `{"detail":"not authenticated"}`.

**Decision:** one `@app.middleware("http")` (`serve_frontend`,
`cohab/main.py`) does both, keyed on two signals that don't require
touching a single route or test:

- A leading `/api/` is stripped from `request.scope["path"]` before
  `call_next` — mutating the scope in place is enough for Starlette's
  router to see the rewritten path, a standard technique for this exact
  case.
- A **real browser navigation** is told apart from every other caller
  (`fetch()`, `TestClient`, an asset `<script>`/`<link>` tag) by its
  `Accept` header — only a navigation request asks for `text/html`. When it
  does, this serves `index.html` directly and never calls the router at
  all, sidestepping the path collision entirely rather than trying to
  detect it after the fact. Everything else goes through the router first
  as before; only a genuine 404 (an actual missing route, e.g. a built
  asset like `/assets/index-*.js`, which has no registered route) falls
  back to serving a matching file under the built `dist/` — checked with a
  `.relative_to()` guard against path traversal.
- No-ops entirely — falls straight through to `call_next` — whenever
  `FRONTEND_DIST` (new `FRONTEND_DIST_DIR` config, default
  `../frontend/dist`, same relative-to-cwd convention as `UPLOAD_DIR`)
  doesn't exist, so a backend-only dev session with no `npm run build` run
  is unaffected.

Verified live end-to-end against the merged origin (`http://localhost:8000`
directly, no Vite dev server): login, `/matches` render, and a **hard
navigation reload on `/matches`** all correctly serve/re-render the app
(network tab showed `/api/auth/me`, `/api/matches`, `/api/feedback/pending`,
`/api/saved` each returning 200, zero console errors) — the exact scenario
item 2 above would have broken. `tests/test_frontend_serving.py` (new,
6 cases) locks in both behaviours with a throwaway `FRONTEND_DIST` via
monkeypatch, so the suite doesn't depend on whether a build happens to
exist on disk; the full suite (329 pre-existing + these 6) passes unchanged.

**Also closed, not code:** `backend/.env`'s `SECRET_KEY` was still the
literal `.env.example` placeholder (`dev-only-change-me`) — a value visible
to anyone who reads the checked-in example file, and this key signs every
session cookie. Replaced with a random `secrets.token_urlsafe(48)` value.
`.env` is gitignored and has never been committed (`git log --all` on it is
empty), so this was a local-file fix, not a leak response.

**Left for the user, not touched:** `COOKIE_SECURE` stays `False` in this
`.env` — it's correctly local-dev-only (the code's own default, unset, is
`True`; this file's override is what makes plain http work here) and
flipping it now would break the very same local session just used to
verify this fix. Must be `True` (or simply unset) wherever this is actually
deployed over https. The `SMTP_PASSWORD` in this `.env` is still the exact
value its own comment says was already exposed via screenshot and needs
rotating at Google's app-passwords page — the user said a new one had been
set, but the file's value is unchanged from before that message, flagged
back to them rather than assumed fixed.

**Code:** `cohab/main.py` (`serve_frontend`, `_dist_file`, `FRONTEND_DIST`),
`cohab/core/config.py` (`FRONTEND_DIST_DIR`),
`tests/test_frontend_serving.py` (new), `backend/.env` (`SECRET_KEY`,
local only, not committed).

### D-13.20 First moderator on a fresh production DB — a CLI grant, not an API route

**Raised by the user**, asking how a single account gets moderator/admin
access once the app is deployed with an empty database rather than the dev
seed. It's a real gap: `is_moderator` (`models/user.py`) defaults `False` and
is set `True` in exactly two places in the whole codebase — `demo_seed.py`
and test fixtures. There is no API route that can set it (`api/moderation.py`
gates on `is_moderator` per D-7.1, deliberately with no self-service
promotion path, since an endpoint that could grant it would be a
privilege-escalation hole). On a brand-new prod DB, nobody has the flag and
nothing in the running app can grant it.

**Decision:** a standalone management script, the same shape as
`demo_seed.py` — `python -m cohab.promote_moderator <email>`
(`cohab/promote_moderator.py`, new) — looks up the account by email and sets
`is_moderator = True` directly via `SessionLocal`. No HTTP surface at all:
whoever runs it needs deploy/DB access already, which is the same trust
level required to seat the first moderator by any means. Documented in
CLAUDE.md's Commands section ("First moderator on a fresh DB"): register the
account normally through the app first, then run the script once against it.

**Not done:** no admin UI or invite-based promotion flow — out of scope for
the pilot, and the one-off script is sufficient for seating a small, known
set of moderators by hand.

**Code:** `cohab/promote_moderator.py` (new), `CLAUDE.md` (Commands).

### D-13.21 User-uploaded images move from local disk to Cloudflare R2

**Raised by the user**, while scoping free hosting options. `services/uploads.py`
wrote every avatar/listing photo straight to `UPLOAD_DIR` on local disk,
served back via a `/media` StaticFiles mount (`main.py`) — fine on a host
with a persistent disk, but silently loses every image on the next restart
or redeploy on the free tiers under consideration (Render, Cloud Run, Koyeb),
whose filesystems are ephemeral. `seed_avatars.py` and `seed_photos.py` wrote
through the exact same local-disk path, so the gap wasn't limited to real
user uploads.

**Decision:** Cloudflare R2 (S3-compatible, no egress fees, free tier doesn't
expire — unlike Supabase Storage, which pauses the whole project after a
week idle, or S3, whose free tier is 12 months only). Storage sits behind a
new `ImageStorage` protocol (`services/storage.py`), the same
swap-behind-an-interface pattern `OTPSender` already uses (`services/otp.py`)
— `LocalDiskStorage` and `R2Storage`, picked by `get_image_storage()` based
on whether `R2_ENDPOINT_URL`/`R2_ACCESS_KEY_ID`/`R2_SECRET_ACCESS_KEY`/
`R2_BUCKET_NAME` are all set. Unset (dev, CI, tests) still uses local disk —
no test changes needed, no network dependency in the test suite.

Images are proxied through the app rather than linked at R2's public URL
directly: `main.py`'s `/media/{name}` is now an explicit route (not a
`StaticFiles` mount) that calls `get_image_storage().load(name)` regardless
of backend, and stamps `X-Content-Type-Options: nosniff` on the response
either way. This was a deliberate choice over serving R2 URLs to the browser
directly — direct serving is less server load and marginally faster, but R2
doesn't attach that header to publicly-served objects without an added
Cloudflare Worker/Transform Rule, which would have dropped the D-10.2
content-sniffing guard silently. Proxying keeps that guard intact at the
cost of every image request round-tripping through the single uvicorn
worker — acceptable at pilot scale, revisit if it measurably isn't.

Verified live against a real R2 bucket (not just the local-disk fallback):
upload → stored in R2 → served back through `/media/<name>` with the nosniff
header intact, all 7 `test_uploads.py` cases passing unchanged. Full suite:
333 passed, 2 pre-existing failures unrelated to this change (confirmed via
`git stash` — `test_analytics_summary_counts_reflect_seeded_members` and
`test_put_profile_persists_and_computes_text_vector` fail identically on
unmodified code; not investigated further here, out of scope for this pass).

**Also found, not part of this decision:** the local `backend/.env` had
`COOKIE_SECURE=True`, which broke ~13 unrelated tests (a `Secure` cookie
isn't sent back over `TestClient`'s plain-http scheme) — flipped to `False`
locally to match `.env.example`'s documented local-dev value; `True` is
still correct on the actual deployed server. Separately, the user asked to
commit `backend/.env` (containing the live R2 secret, `SECRET_KEY`, and a
Gmail app password) to git — declined: `.env` is gitignored specifically so
these never enter git history, and a later "remove it" commit would not
undo that exposure. Deployment env vars belong in the hosting platform's own
config, not the repo.

**Not done:** no image resizing/thumbnailing (pre-existing, unrelated to
this change — `services/uploads.py`'s own docstring already flags it as
future work). No custom domain on the R2 bucket — the Public Development
URL is unused anyway under the proxy-serving design above.

**Code:** `cohab/services/storage.py` (new), `cohab/services/uploads.py`,
`cohab/seed_avatars.py`, `cohab/seed_photos.py`, `cohab/main.py` (`/media`
route), `cohab/core/config.py` (`R2_*`), `backend/requirements.txt`
(`boto3`), `backend/.env.example` (`R2_*` placeholders).

### D-13.22 Auth/signup/onboarding motion parity, a live-caught Neon connection bug, and a light-mode default

**Raised by the user**, live-testing the deployed-toward app on a phone
browser: light theme should be the default (not follow the OS), the ambient
dots background should appear everywhere including mobile, the desktop
seeker-type step had no way back to login, the desktop account-creation form
was missing its "Already have an account?" link (mobile had one), and there
was "not much animation... going to next page," especially on mobile.

**Light theme by default:** `lib/theme.ts::getStoredChoice()` and the
pre-mount inline script in `index.html` both defaulted an unset choice to
`'system'` (follow the OS). Changed to `'light'` — `'system'` remains a
fully-supported explicit choice via the existing three-way toggle, this only
changes what a first-time visitor with no stored preference sees. Both
places had to change together or the pre-mount script (which exists
specifically to avoid a flash-of-wrong-theme before React mounts) would
paint dark first and then flip.

**Ambient dots on the auth/signup flow:** turned out the app-wide
`AmbientField` (`CompatibilityField.tsx`, D-13.11) already covers every
other screen — `AppShell`, `OnboardingHeader`, and the moderation screens
all already mount it, confirmed by grep before touching anything. The actual
gap was narrower: the login/signup screens use their own `AuthShell`, whose
dots (`HeroStagger`'s own `CompatibilityField` instance) are desktop-only by
design, and the signup wizard's seeker-type step doesn't use `AuthShell` at
all. Fixed by mounting `AmbientField` in both places. `AuthShell`'s form
panel had an opaque `bg-cohab-card` covering the entire mobile viewport,
which would have silently hidden the canvas behind it exactly the way
`AppShell`'s own comment warns against — made transparent on mobile only
(`bg-transparent cohab-desktop:bg-cohab-card`), confirmed `Input`/`Select`
already carry their own backgrounds so legibility doesn't depend on the page
wrapper.

**Motion between steps that aren't route changes:** `PageTransition`
(D-12.1) only fires on a `useLocation().pathname` change. The login↔signup
switch and the signup wizard's seeker/form/otp/avatar steps are local
`useState`, never a URL change, so it never fired there — this is very
likely the real source of "not much animation... going to next page," since
this is the first thing every new user (or anyone testing fresh) goes
through. Added `StepTransition` (new,
`components/motion/StepTransition.tsx`): the same GSAP tokens and enter-only
behaviour as `PageTransition`, keyed on an arbitrary step string instead of
the pathname. Wired into every auth/signup step, the 12-question
`RequiredQuestionnaire`'s per-question entrance (previously zero motion
across all 12 clicks — probably the single biggest contributor to the
complaint), and `PageTransition` itself into the three other onboarding
routes, which don't use `AppShell` (D-13.3) and so never got it either.

**A `StepTransition` bug found and fixed within this same pass:** wrapping
`RequiredQuestionnaire`'s mobile and desktop question blocks broke the
`cohab-desktop:grid cohab-desktop:grid-cols-[268px_1fr]` layout — the
`hidden`/`cohab-desktop:hidden` classes were on the *inner* wrapped div, not
on `StepTransition`'s own (unstyled, always-`display:block`) wrapper div, so
at desktop width the invisible wrapper still consumed a grid track and
pushed the real content out of view. Gave `StepTransition` a `className`
prop and collapsed the double-nesting at each call site instead of wrapping
from outside — caught by live browser testing, not by `tsc` or the build.

**A real login-breaking bug, found live, unrelated to any of the above:**
logging in against Neon threw a 500 —
`sqlalchemy.exc.OperationalError: ... SSL connection has been closed
unexpectedly`. Neon's free tier suspends its compute after idle time;
`db.py`'s `create_engine()` had no `pool_pre_ping`, so the first request
after any idle period reused a dead pooled connection instead of
transparently reconnecting. This would have hit the deployed app the first
time anyone used it after it sat idle — `pool_pre_ping=True` is the standard
SQLAlchemy fix for exactly this class of problem (serverless/autosuspending
Postgres + a long-lived connection pool). Full test suite re-run after:
333 passed, the same 2 pre-existing failures from D-13.21 (confirmed
unrelated there via `git stash`), zero regressions.

**A vertical-centering nudge**, also reported live (screenshots): the
login/signup form panel's `justify-center` left it looking too far down.
`justify-content: center` splits whatever padding-free space remains
between top and bottom equally, so asymmetric padding
(`cohab-desktop:pt-8 cohab-desktop:pb-28`, replacing the previous equal
`py-14`) shifts the visual centre up without abandoning centering outright.

**Also on disk, not authored in this pass:** `CompatibilityField.tsx` and
`index.css` carry a retuning of the ambient field's light-theme colours
(deep green instead of a lightened lime, since the beige ground is already
bright — going darker than the surface is what makes it legible, not paler)
and a minimum line-width floor so the faintest links don't antialias to
nothing without the dark theme's glow to carry them.

**Not done:** no live verification of `AmbientField`/`PageTransition` on
routes reached only via WebSocket-chat or listing-photo upload flows —
out of scope for this pass, same class of gap D-12.7 already flags for the
rest of the motion system.

**Code:** `frontend/src/lib/theme.ts`, `frontend/index.html`,
`frontend/src/features/auth/AuthPage.tsx`,
`frontend/src/features/auth/SignUpWizard.tsx`,
`frontend/src/components/motion/StepTransition.tsx` (new),
`frontend/src/features/onboarding/RequiredQuestionnaire.tsx`,
`frontend/src/features/onboarding/OptionalQuestionnaire.tsx`,
`frontend/src/features/onboarding/ListingForm.tsx`,
`frontend/src/features/onboarding/ImportanceWeights.tsx`,
`frontend/src/main.tsx` (touch-listener), `backend/cohab/db.py`
(`pool_pre_ping`).
