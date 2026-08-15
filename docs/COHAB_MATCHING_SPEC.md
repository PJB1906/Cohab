# Cohab — Questionnaire and Scoring Specification

**Companion to** `COHAB_PRD.md`. This document holds every question, every answer option, and every number the matching engine needs. It is the buildable spec: nothing in the matcher should contain a magic constant that is not written down here.

---

## 1. Attribute types

Four types, each scored differently. Getting the type right matters more than getting the number right — a well-tuned weight on a wrongly-typed attribute still produces wrong answers.

| Type | Rule | Symmetric? | Examples |
|---|---|---|---|
| **Hard** | Pass or fail. No score. | Yes | City, budget, dates, gender, allergies, pets, seeker type |
| **Similarity** | Closer is better | Yes | Sleep, cleanliness, chores, communication, cost splitting, sociability, interests |
| **Tolerance** | Does A tolerate B's behaviour? | **No** | Guests, smoking, alcohol, non-veg cooking, noise, sharing |
| **Absolute** | Higher is better, independent of self | **No** | Money reliability |

Tolerance and absolute attributes score differently in each direction, which is why `S(a→b) ≠ S(b→a)` and why the two are combined by harmonic mean rather than computed once.

---

## 2. Hard constraints

Collected outside the scored questionnaire. All are evaluated symmetrically: the pair passes only if both sides' requirements are satisfied.

| Field | Type | Constraint | Config |
|---|---|---|---|
| `seeker_type` | enum | `has_place` + `has_place` → fail. All other combinations pass. | — |
| `city` | string | Must be equal. v1 is Bangalore-only. | — |
| `locality` | list | v2: must share at least one preferred locality. v1: city-level only. | — |
| `budget_min/max` | int | Bands must intersect: `NOT (a.max < b.min OR b.max < a.min)`. For a `has_place` member, the listing's rent replaces the band as a point value. | — |
| `move_in_date` | date | `abs(a - b) <= MOVE_IN_TOLERANCE_DAYS` | **30 days** |
| `gender`, `gender_preference` | enum | Mutually satisfied. `any` matches all. | — |
| `severe_allergy` | list | If A declares a severe allergy, B must not require that allergen in the shared kitchen. | — |
| `has_pet`, `pet_tolerance` | enum | If B has a pet, A's tolerance must not be `cannot_live_with_pets`. Asymmetric, evaluated both ways. | — |
| `smoking_indoors` | bool | If B smokes indoors and A has flagged it a deal-breaker → fail. | — |
| account state | — | Both `Verified` and `Active`; neither blocks the other. | — |

`MOVE_IN_TOLERANCE_DAYS` must be a config value, not a constant. It is the single biggest lever on filter yield, and 30 days is a starting guess to be tuned against the pilot.

---

## 3. The questionnaire

### Tier 1 — Conflict (required, 12 questions, target under 4 minutes)

Every dimension here traces to a documented conflict source.

---

**Q1. Sleep schedule** · *similarity* · `sleep_schedule`
When do you usually go to sleep?
`early` Before 11pm · `regular` 11pm–1am · `night_owl` After 1am · `varies` It varies a lot

**Q2. Noise expectation at home** · *tolerance* · `noise_preference` / `noise_behaviour`
Two parts — what you need, and what you do.
*Need:* `strict` Quiet after 10pm · `moderate` Quiet after midnight · `flexible` Noise rarely bothers me
*Behaviour:* `quiet` I'm quiet at home · `moderate` Normal, occasional calls or music · `loud` Music, calls, friends over

> Noise generates more residence-hall mediation than any other single issue, which is why it is asked separately from sleep schedule rather than inferred from it. Two night owls can still conflict if one works in silence and the other takes 1am calls.

**Q3. Cleanliness standard** · *similarity* · `cleanliness_level`
How tidy do you keep shared spaces?
`very_tidy` Cleaned daily, everything put away · `moderate` Tidy up every few days · `relaxed` Clean when it needs it

**Q4. Chore approach** · *similarity* · `chore_approach`
How should cleaning get done?
`rota` Fixed rota, everyone knows their job · `shared` Share fairly, no formal schedule · `hired` Hire help and split the cost · `own_mess` Everyone cleans up after themselves only

> Asked separately from Q3 because two people can share a cleanliness standard and still fight bitterly about who does the work. Agreement templates almost always contain a chore clause.

**Q5. Food and belongings** · *tolerance* · `sharing_norm`
How do you treat things in a shared flat?
`communal` Mostly shared — help yourself · `ask_first` Ask before using my things · `separate` I keep my things separate

> Sharing food and belongings accounts for roughly 27% of reported disputes and is **independent of Q3 and Q4**: a person can keep shared spaces spotless, follow the rota, pay early, and still finish your milk. The cleanliness questions do not reach it.
>
> Scored as a tolerance attribute even though it is collected as a single field — a person's sharing norm is simultaneously what they expect and how they behave, so the same value indexes both axes of the matrix. The asymmetry is real: a `separate` person paired with a `communal` one loses possessions, while a `communal` person paired with a `separate` one is merely mildly frustrated. A similarity model would score both directions identically and get the harm backwards.

**Q6. How often do you have guests over?** · *tolerance* · `guest_frequency`
`rarely` Rarely · `occasionally` A few times a month · `often` Weekly or more · `partner_regular` A partner stays over regularly

**Q7. How do you feel about a roommate's guests?** · *tolerance* · `guest_tolerance`
`anytime` Fine anytime · `with_notice` Fine with notice · `weekends` Weekends only · `prefer_none` I'd rather not

> Q6 and Q7 form a tolerance pair. Guests appear in roughly a third of reported conflicts, and agreement templates specify overnight limits in nights per month — the friction is one person's frequency against the other's comfort, not the similarity of their habits.

**Q8. Communication style** · *similarity* · `communication_style`
If something bothered you at home, what would you do?
`direct_now` Say it directly, straight away · `calm_later` Bring it up calmly at a good moment · `message` Message rather than talk face to face · `let_go` Usually let it go

> The roommate-breakup literature finds communication style among the strongest predictors of people actually ending the arrangement — stronger than lifestyle logistics.

**Q9. Rent and bills** · *absolute* · `payment_reliability`
How do you handle your share?
`early` Always before it's due · `on_time` On time · `needs_grace` Sometimes need a few days · `needs_reminding` I'd rather someone reminded me

> The only absolute attribute. Over 20% of renters call non-payment immediately terminable, and 22% report financial arguments. Nobody wants a match on *shared* unreliability, so similarity is the wrong comparison — the score depends only on the other person's answer.

**Q10. Splitting the costs** · *similarity* · `cost_split_preference`
How should rent and bills be divided?
`equal` Everything split equally · `by_room` By room size or what each room has · `by_use` By what each person actually uses · `flexible` Happy either way

> Q9 measures *when* someone pays; this measures *how the total is divided*, and they are different arguments. Two people who both answer `early` can still deadlock over whether the smaller bedroom pays less. Similarity rather than tolerance: neither answer is a behaviour imposed on the other, and the failure mode is a negotiation that never resolves.

**Q11. Diet and kitchen** · *similarity (diet) + tolerance (cooking)* · `diet` / `nonveg_cooking_tolerance`
*Your diet:* `veg` Vegetarian · `nonveg` Non-vegetarian · `eggetarian` Eggetarian · `vegan` Vegan · `jain` Jain
*Non-vegetarian cooking in a shared kitchen:* `fine` No problem · `prefer_not` I'd prefer not · `not_at_all` Not at all

> Diet is scored, never filtered — see PRD §10. The kitchen-tolerance question captures the genuine practical friction without the proxy effect.

**Q12. Smoking and alcohol** · *tolerance* · `smoking_behaviour` / `smoking_tolerance` / `alcohol_*`
*You:* `none` Don't smoke · `outside` Smoke, outside only · `indoors` Smoke indoors
*A roommate who smokes:* `fine` Fine · `outside_ok` Outside only · `smoke_free` I want a smoke-free home
Same structure for alcohol.

---

### Tier 2 — Life stage (optional but prompted, 4 questions)

**Q13. What are you working towards right now?** · *similarity* · `life_stage`
`coursework` Coursework and classes · `exam_prep` Competitive exam preparation · `job` Working or interning · `building` Building something of my own · `research` Research or thesis

> Not about shared ambition. Aspiration is a proxy for daily rhythm, and rhythm is what creates friction. Someone preparing for a competitive exam needs silence and predictable hours for two years; someone building a company takes calls at 2am. "Night owl" does not distinguish a person who games late from one who works late and resents noise at 9am.

**Q14. Typical weekday** · *similarity* · `daytime_presence`
`out` Out most of the day · `partly` Home part of the day · `home` Home most of the day

**Q15. Time at home** · *similarity* · `home_orientation`
`homebody` I'm a homebody · `balanced` Balanced · `rarely` I'm barely home

**Q16. What do you want from a flatmate?** · *similarity* · `sociability`
`friend` Someone I'd spend time with · `friendly` Friendly, but we live our own lives · `independent` Polite and independent

> Q15 asks *how much* someone is home; this asks *what they want to happen while they are*. They are not the same question, and the difference is the one people most often discover too late. Whoever wants company reads distance as rejection; whoever wants independence reads warmth as intrusion. Neither is a habit either party can compromise on the way they can compromise on a chore rota.
>
> Indian flatshare research puts privacy and personal boundaries among its core compatibility themes, alongside the logistics that Tier 1 already covers.

---

### Tier 3 — Affinity (optional, skippable)

**Q17. Interests** · *similarity, set overlap* · `interests`
Multi-select: sports and fitness, music, gaming, cooking, reading, film and series, travel, art and design, technology, volunteering, photography, outdoors.

**Q18. About you** · *semantic* · `lifestyle_notes`
Free text. Prompt: *"What are you working towards, and what do you do outside it? What kind of home do you want to come back to?"*

> This is the field where embeddings earn their place. A lookup table cannot enumerate the ways people describe themselves. The prompt is written to elicit rhythm and atmosphere, not a CV.

---

### Importance weighting (screen 6)

"Pick the three that matter most to you." The three selected are boosted; the rest are scaled down proportionally so the vector still sums to 1. If skipped, the platform defaults apply unchanged.

---

## 4. Similarity matrices

Symmetric. Diagonal is 1.0.

**`sleep_schedule`**

| | early | regular | night_owl | varies |
|---|---|---|---|---|
| **early** | 1.00 | 0.70 | 0.20 | 0.60 |
| **regular** | 0.70 | 1.00 | 0.60 | 0.75 |
| **night_owl** | 0.20 | 0.60 | 1.00 | 0.60 |
| **varies** | 0.60 | 0.75 | 0.60 | 0.80 |

`varies` never scores 1.0 even against itself: two unpredictable schedules are not a reliable match, merely an unobjectionable one.

**`cleanliness_level`**

| | very_tidy | moderate | relaxed |
|---|---|---|---|
| **very_tidy** | 1.00 | 0.60 | 0.15 |
| **moderate** | 0.60 | 1.00 | 0.60 |
| **relaxed** | 0.15 | 0.60 | 1.00 |

The very_tidy/relaxed cell is 0.15 — the harshest non-zero value in the spec. Cleanliness is the most frequently reported conflict source (~42%), and this pairing is its archetype.

**`chore_approach`**

| | rota | shared | hired | own_mess |
|---|---|---|---|---|
| **rota** | 1.00 | 0.65 | 0.60 | 0.25 |
| **shared** | 0.65 | 1.00 | 0.70 | 0.45 |
| **hired** | 0.60 | 0.70 | 1.00 | 0.55 |
| **own_mess** | 0.25 | 0.45 | 0.55 | 1.00 |

**`communication_style`**

| | direct_now | calm_later | message | let_go |
|---|---|---|---|---|
| **direct_now** | 1.00 | 0.75 | 0.45 | 0.30 |
| **calm_later** | 0.75 | 1.00 | 0.70 | 0.50 |
| **message** | 0.45 | 0.70 | 1.00 | 0.60 |
| **let_go** | 0.30 | 0.50 | 0.60 | 0.55 |

Two `let_go` people score 0.55, not 1.0 — the one case where similarity is actively bad. Neither raises anything, resentment accumulates unspoken, and the arrangement fails without a single conversation.

**`cost_split_preference`**

| | equal | by_room | by_use | flexible |
|---|---|---|---|---|
| **equal** | 1.00 | 0.45 | 0.50 | 0.85 |
| **by_room** | 0.45 | 1.00 | 0.70 | 0.85 |
| **by_use** | 0.50 | 0.70 | 1.00 | 0.85 |
| **flexible** | 0.85 | 0.85 | 0.85 | 0.75 |

`equal` against `by_room` is 0.45 — the sharpest cell, because it is a distributive disagreement with a fixed pot, so one side's preferred rule costs the other money every month. `by_room` and `by_use` sit at 0.70: both are proportional principles, differing only in what they measure.

Two `flexible` answers score 0.75 rather than 1.0, following the same logic as `varies` in `sleep_schedule` and `let_go` in `communication_style` — the split still has to be decided, and two people with no stated view have agreed on nothing.

**`sociability`**

| | friend | friendly | independent |
|---|---|---|---|
| **friend** | 1.00 | 0.70 | 0.25 |
| **friendly** | 0.70 | 1.00 | 0.70 |
| **independent** | 0.25 | 0.70 | 1.00 |

Symmetric, unlike most of what this question resembles: `friend` against `independent` harms both parties rather than one, which is why it is not modelled as a tolerance. The 0.25 floor is the second-harshest in the spec after cleanliness, and deliberately so — it is a mismatch of expectation rather than of habit, and there is no rota or schedule that resolves it.

**`diet`**

| | veg | nonveg | eggetarian | vegan | jain |
|---|---|---|---|---|---|
| **veg** | 1.00 | 0.50 | 0.80 | 0.80 | 0.75 |
| **nonveg** | 0.50 | 1.00 | 0.80 | 0.40 | 0.35 |
| **eggetarian** | 0.80 | 0.80 | 1.00 | 0.60 | 0.55 |
| **vegan** | 0.80 | 0.40 | 0.60 | 1.00 | 0.70 |
| **jain** | 0.75 | 0.35 | 0.55 | 0.70 | 1.00 |

Deliberately shallow: the veg/nonveg floor is 0.50, well above the 0.15 in cleanliness. Diet must not be able to dominate a match on its own.

**`life_stage`**

| | coursework | exam_prep | job | building | research |
|---|---|---|---|---|---|
| **coursework** | 1.00 | 0.70 | 0.65 | 0.55 | 0.75 |
| **exam_prep** | 0.70 | 1.00 | 0.55 | 0.35 | 0.70 |
| **job** | 0.65 | 0.55 | 1.00 | 0.75 | 0.65 |
| **building** | 0.55 | 0.35 | 0.75 | 1.00 | 0.60 |
| **research** | 0.75 | 0.70 | 0.65 | 0.60 | 1.00 |

`daytime_presence` and `home_orientation` use ordinal distance: `1 - |i - j| / (n - 1)`.

**`interests`** — Jaccard index over selected tags: `|A ∩ B| / |A ∪ B|`. Floor of 0.3 when either list is empty, so skipping the optional tier is not penalised as a mismatch.

---

## 5. Tolerance matrices

Asymmetric. Read as: **rows = A's preference, columns = B's behaviour.** The value is A's score for B.

**Guests** — `guest_tolerance` (A) × `guest_frequency` (B)

| A ↓ / B → | rarely | occasionally | often | partner_regular |
|---|---|---|---|---|
| **anytime** | 1.00 | 1.00 | 0.95 | 0.90 |
| **with_notice** | 1.00 | 0.90 | 0.70 | 0.60 |
| **weekends** | 1.00 | 0.80 | 0.40 | 0.30 |
| **prefer_none** | 1.00 | 0.50 | 0.20 | 0.10 |

The first column is all 1.00: a roommate who rarely has guests satisfies everyone. This asymmetry is invisible to a similarity model, which would score `prefer_none` against `rarely` as a mismatch when it is in fact ideal.

**Sharing** — `sharing_norm` (A) × `sharing_norm` (B)

| A ↓ / B → | communal | ask_first | separate |
|---|---|---|---|
| **communal** | 1.00 | 0.85 | 0.55 |
| **ask_first** | 0.90 | 1.00 | 0.85 |
| **separate** | 0.35 | 0.90 | 1.00 |

The only tolerance attribute drawn from a single field on both axes — see Q5. The matrix is asymmetric where it matters: `(separate, communal)` scores 0.35 and `(communal, separate)` scores 0.55. Both are mismatches, but only one of them involves someone's things going missing.

`ask_first` is the safe answer in both directions and never scores below 0.85 against anything, which is the correct behaviour — a person who asks first imposes on nobody.

**Smoking** — `smoking_tolerance` (A) × `smoking_behaviour` (B)

| A ↓ / B → | none | outside | indoors |
|---|---|---|---|
| **fine** | 1.00 | 1.00 | 0.90 |
| **outside_ok** | 1.00 | 0.95 | 0.25 |
| **smoke_free** | 1.00 | 0.60 | 0.00 |

The 0.00 cell is scored, not filtered — unless A has flagged indoor smoking a deal-breaker, in which case Stage 1 excludes the pair before scoring.

**Alcohol** — same structure, softer floors (0.15 rather than 0.00).

**Non-veg cooking** — `nonveg_cooking_tolerance` (A) × `diet` (B)

| A ↓ / B → | veg / vegan / jain | eggetarian | nonveg |
|---|---|---|---|
| **fine** | 1.00 | 1.00 | 1.00 |
| **prefer_not** | 1.00 | 0.80 | 0.45 |
| **not_at_all** | 1.00 | 0.55 | 0.15 |

**Noise** — `noise_preference` (A) × `noise_behaviour` (B)

| A ↓ / B → | quiet | moderate | loud |
|---|---|---|---|
| **flexible** | 1.00 | 1.00 | 0.85 |
| **moderate** | 1.00 | 0.85 | 0.40 |
| **strict** | 1.00 | 0.60 | 0.10 |

---

## 6. Absolute scores

**`payment_reliability`** — depends only on B's value, whatever A answered.

| B's answer | Score to A |
|---|---|
| `early` | 1.00 |
| `on_time` | 0.95 |
| `needs_grace` | 0.50 |
| `needs_reminding` | 0.25 |

Self-reported and therefore gameable. Weighted moderately in v1 for that reason, and a candidate for replacement by observed behaviour once outcome data exists.

---

## 7. Continuous attributes

**Budget proximity** — over the midpoints of the two bands. For a `has_place` member, the listing rent is the point value.

```
mid_a = (a.budget_min + a.budget_max) / 2
mid_b = (b.budget_min + b.budget_max) / 2
sim   = max(0, 1 - |mid_a - mid_b| / BUDGET_SPREAD)
```

`BUDGET_SPREAD = 15000` (₹). A ₹15,000 gap scores zero; ₹2,000 scores 0.87. Budget appears in Stage 1 as a hard band-intersection test *and* here as a soft score — passing the filter means affordable, scoring well means comfortably aligned.

**Text similarity** — cosine over vectors of `lifestyle_notes`, computed at profile save and cached. `TfidfSimilarity` in v1, `EmbeddingSimilarity` (`all-MiniLM-L6-v2`, 384-d) once the pipeline is proven. Score 0.5 (neutral) if either field is empty.

---

## 8. Default weights

Version 1 of `weight_set`, `source = Expert`. Traceable to reported conflict frequencies, cited individually rather than pooled:

| Conflict source | Reported frequency |
|---|---|
| Cleanliness | ~42% |
| Noise and sleep schedules | ~38% |
| Guests and partners | ~31% |
| Sharing food and belongings | ~27% |
| Money and shared expenses | ~22% |

| Attribute | Type | Weight |
|---|---|---|
| `cleanliness_level` | similarity | 0.11 |
| `chore_approach` | similarity | 0.06 |
| `sharing_norm` | tolerance | 0.04 |
| `sleep_schedule` | similarity | 0.09 |
| `noise` | tolerance | 0.09 |
| `guests` | tolerance | 0.10 |
| `payment_reliability` | absolute | 0.08 |
| `cost_split_preference` | similarity | 0.03 |
| `communication_style` | similarity | 0.08 |
| `budget_proximity` | continuous | 0.06 |
| `diet` | similarity | 0.03 |
| `nonveg_cooking` | tolerance | 0.03 |
| `smoking` | tolerance | 0.03 |
| `alcohol` | tolerance | 0.02 |
| **Tier 1 subtotal** | | **0.85** |
| `life_stage` | similarity | 0.04 |
| `daytime_presence` | similarity | 0.02 |
| `home_orientation` | similarity | 0.02 |
| `sociability` | similarity | 0.02 |
| **Tier 2 subtotal** | | **0.10** |
| `interests` | similarity | 0.02 |
| `lifestyle_notes` | semantic | 0.03 |
| **Tier 3 subtotal** | | **0.05** |
| **Total** | | **1.00** |

Cleanliness, chores and sharing together reach 0.21; sleep and noise together 0.18 — matching the two dominant conflict sources. Money is 0.11 across reliability and splitting. Affinity is held to 5% deliberately: it makes matches feel personal and supplies explanation copy, but it does not predict whether two people can share a kitchen.

**Where the new weights came from.** The vector must sum to 1, so three attributes were added by funding them from four existing ones rather than by inflating the total. Each reduction has a reason of its own:

- `payment_reliability` 0.11 → 0.08, with the freed 0.03 going to `cost_split_preference`. The money cluster is unchanged at 0.11; it is now measured with two questions instead of one. The reduction also corrects a standing weakness noted in §6 — reliability is self-reported and gameable, and at 0.11 it was the third-heaviest weight in the model resting on the least trustworthy signal.
- `guests` 0.12 → 0.10. Guest tolerance is correlated with noise tolerance, and at 0.12 the combined "other people in my space" cluster reached 0.21, exceeding the cleaning cluster despite a lower reported frequency.
- `budget_proximity` 0.07 → 0.06. Budget is already enforced as a hard band-intersection test in Stage 1, so the soft score is partly redundant with a constraint that has already passed.
- `diet` 0.04 → 0.03. `nonveg_cooking` at 0.03 captures the practical kitchen friction; `diet` similarity is the softer signal of the two and the matrix is deliberately shallow anyway.
- Tier 2 internally rebalanced to fund `sociability` at 0.02 without changing the 0.10 subtotal.

**On the discount applied to sharing.** At the ~0.004-per-percentage-point ratio implied by the other Tier 1 weights, a 27% conflict source would attract roughly 0.10. `sharing_norm` is set at 0.04 instead, for two reasons that should be stated rather than buried: reported *frequency* is not *severity*, and disputes over food and borrowed items are both more frequent and more recoverable than disputes over cleanliness or money; and the attribute is partly correlated with `cleanliness_level` and `chore_approach`, so weighting it at face value would double-count the underlying tidiness disposition. The Phase 3 ablation (§11) is the check on whether 0.04 is too low.

**Prior version.** Weight set v1 as published on this document's first revision had 17 attributes and no `sharing_norm`, `cost_split_preference` or `sociability`. Per the immutability rule, this table is **weight set v2** — v1 is not edited in place, and any `match_score` row computed under v1 keeps its explanation.

**Missing answers.** If an optional attribute is unanswered by either party, drop it from both weight vectors and renormalise the remainder to 1. Never impute a neutral 0.5 — that silently rewards incomplete profiles by moving every score toward the middle.

---

## 9. Scoring procedure

```
score(a, b):
    # Stage 1
    ok, reason = passes_hard_constraints(a, b)
    if not ok: return EXCLUDED, reason

    # Stage 2 — per-attribute, per-direction
    for each attribute i:
        if type(i) == similarity:  sim_a[i] = sim_b[i] = M_i[a.i][b.i]
        if type(i) == tolerance:   sim_a[i] = T_i[a.pref_i][b.behav_i]
                                   sim_b[i] = T_i[b.pref_i][a.behav_i]
        if type(i) == absolute:    sim_a[i] = A_i[b.i]
                                   sim_b[i] = A_i[a.i]
        if type(i) == continuous:  sim_a[i] = sim_b[i] = f_i(a.i, b.i)

    w_a = blend(weight_set.defaults, a.importance_weights)
    w_b = blend(weight_set.defaults, b.importance_weights)
    renormalise both over attributes present in both profiles

    S_ab = Σ w_a[i] · sim_a[i]
    S_ba = Σ w_b[i] · sim_b[i]
    combined = 2 · S_ab · S_ba / (S_ab + S_ba)      # harmonic mean

    return combined, S_ab, S_ba, {i: (sim_a[i], sim_b[i])}, weight_set.id
```

`blend(defaults, importance)`: attributes the user selected as most important are multiplied by 1.5, the remainder scaled down so the vector sums to 1. Multiplicative rather than replacement, so a user's choices shift the emphasis without discarding the platform prior.

---

## 10. Explanation templates

Rendered from the breakdown already computed. Each card shows **the three highest-scoring attributes and the single lowest** — never only the positives.

**Agreement** (attribute score ≥ 0.8):

| Attribute | Template |
|---|---|
| sleep | "You're both {night owls / early risers}." |
| cleanliness | "You both keep things {very tidy / moderately tidy / relaxed}." |
| guests | "{Name} rarely has guests over, which suits you." |
| payment | "{Name} pays rent on time." |
| cost_split | "You'd both split rent and bills {equally / by room}." |
| sharing | "You both like to {share things / ask before borrowing}." |
| noise | "You both want a {quiet / relaxed} home." |
| sociability | "You're both looking for {a flatmate you'd spend time with / a friendly but independent household}." |
| life_stage | "You're both {preparing for exams / working}." |
| interests | "You both mentioned {shared tag} and {shared tag}." |
| notes | "Your descriptions of what you're looking for line up closely." |

**Divergence** (lowest, and below 0.5):

| Attribute | Template |
|---|---|
| cleanliness | "You keep things very tidy; {Name} is more relaxed. Worth discussing." |
| sleep | "You're an early riser and {Name} is a night owl." |
| guests | "{Name} has guests over weekly — you prefer a quieter home." |
| payment | "{Name} sometimes needs a few days on rent." |
| cost_split | "You'd split everything equally; {Name} would split by room size. Worth discussing." |
| sharing | "You keep your things separate; {Name} treats the flat as communal. Worth discussing." |
| sociability | "You're looking for a flatmate you'd spend time with; {Name} would rather keep to themselves." |
| diet | "You're vegetarian and {Name} cooks non-veg." |

Wording rules: name the difference plainly, never editorialise, never advise beyond "worth discussing". A card with no divergence above threshold shows nothing rather than inventing one.

---

## 11. Tuning checklist for Phase 3

Run against the realistic seed generator before touching the API.

1. **Filter yield** — median eligible pool. Below 10, widen `MOVE_IN_TOLERANCE_DAYS` before blaming the scoring.
2. **Exclusion reasons** — which constraint eliminates most candidates. If one dominates, it is probably too strict.
3. **Score distribution** — should spread across roughly 0.35–0.90. Everything bunched at 0.70–0.80 means the weights are not discriminating and the matrices need sharpening.
4. **Directional spread** — `|S_ab − S_ba|`. If always near zero, the importance weighting is not doing anything and directional scoring is dead weight.
5. **Eyeball the top ten** for twenty synthetic profiles. This is the only test that catches a design error rather than a coding error.
6. **Ablation** — re-rank with each attribute removed. An attribute that never changes the ranking is a question you can drop from the form. Four to look at specifically: `sharing_norm`, where 0.04 is a deliberate discount on its reported frequency (§8) and may be too severe; `home_orientation` and `sociability`, which sit at 0.02 each and may be partly redundant with `daytime_presence`; and `cost_split_preference`, which will only discriminate if the seed generator gives its four options a realistic spread rather than defaulting most profiles to `flexible`.
