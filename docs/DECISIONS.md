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

**Code:** `cohab/services/matching/eligibility.py` (`Reason.BLOCKED`),
`tests/matching/test_eligibility.py`; not yet: `cohab/services/matches.py`,
`cohab/models/safety.py` (`UserBlock`, unwritten).

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
