import { useMemo } from 'react'
import { Eyebrow } from '@/components/Eyebrow'
import {
  OPTIONAL_TIER2_QUESTIONS,
  REQUIRED_QUESTIONS,
  type Question,
} from '@/data/questionnaire'
import type { ProfileOut } from '@/api/types'

/** Resolve a stored answer code back to the label the user actually picked.
 *
 * Answers persist as codes (`night_owl`), and every screen that renders them
 * has to map back through the question definitions. Without this the rail
 * would print raw enum values at the user, which is the kind of detail that
 * makes an app feel unfinished. */
function buildLabelIndex(questions: Question[]): Map<string, Map<string, string>> {
  const index = new Map<string, Map<string, string>>()
  for (const q of questions) {
    for (const part of q.parts) {
      index.set(part.key, new Map(part.options.map((o) => [o.value, o.label])))
    }
  }
  return index
}

/** A display label for one questionnaire key.
 *
 * `part.label` wins where a question has several parts. Otherwise the theme
 * is preferred for brevity — but only when it belongs to a single question:
 * "Guests" covers both frequency and overnight guests, "Money" covers both
 * when you pay and how rent is split, and "Life stage" is shared by four
 * questions. Falling back to the theme in those cases produced a rail with
 * "Life stage" listed four times against four unrelated values (and the
 * duplicate React keys that surfaced it). Where the theme is ambiguous the
 * question's own title is used instead, since that is the text that actually
 * distinguishes them.
 */
function titleFor(questions: Question[], key: string): string | null {
  const themeCounts = new Map<string, number>()
  for (const q of questions) {
    if (q.theme) themeCounts.set(q.theme, (themeCounts.get(q.theme) ?? 0) + 1)
  }
  for (const q of questions) {
    for (const part of q.parts) {
      if (part.key !== key) continue
      if (part.label) return part.label
      if (q.theme && themeCounts.get(q.theme) === 1) return q.theme
      return q.title ?? q.theme ?? null
    }
  }
  return null
}

const GENDER_PREFERENCE_LABELS: Record<string, string> = {
  any: 'No preference',
  female: 'Female roommate',
  male: 'Male roommate',
}

const PET_TOLERANCE_LABELS: Record<string, string> = {
  comfortable: 'Comfortable with pets',
  no_pets: "Can't live with pets",
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2.5 border-b border-cohab-border-soft last:border-b-0">
      <span className="text-[13px] text-cohab-muted flex-none">{label}</span>
      <span className="text-[13px] font-medium text-cohab-ink text-right">{value}</span>
    </div>
  )
}

/** The right-hand column of the profile hub.
 *
 * Everything here comes from the `profile` query the page already runs — ten
 * fields (`city`, `budget_*`, `move_in_date`, `gender_preference`, the two
 * allergy lists, `has_pet`, `pet_tolerance`, `smoking_dealbreaker`) that were
 * fetched on every visit and rendered nowhere. Surfacing them is what turns
 * this screen from a menu of links into an actual profile, and it costs no
 * new request.
 *
 * Split into two panels on purpose: the hard constraints genuinely behave
 * differently from the scored answers — they exclude candidates outright
 * rather than lowering a score — and the copy says so, since that distinction
 * is the single thing users most often misread about the matcher.
 */
export function ProfileSummaryRail({ profile }: { profile: ProfileOut | null | undefined }) {
  // Depend on `profile.questionnaire` itself rather than a `?? {}` fallback:
  // the fallback allocates a new object on every render, so the memo below
  // would never actually cache (oxlint exhaustive-deps).
  const questionnaire = profile?.questionnaire

  const lifestyle = useMemo(() => {
    const answers = questionnaire ?? {}
    const all = [...REQUIRED_QUESTIONS, ...OPTIONAL_TIER2_QUESTIONS]
    const index = buildLabelIndex(all)
    // `key` (the questionnaire key) is carried through as the row's identity
    // because `titleFor` returns the *question group* title: a multi-part
    // question such as "Guests" produces one row per part, all sharing that
    // one label. Keying the rendered list on the label therefore collided —
    // React logged duplicate keys for "Guests", "Money" and "Life stage".
    const rows: { key: string; label: string; value: string }[] = []
    for (const [key, options] of index) {
      const raw = answers[key]
      if (typeof raw !== 'string' || !raw) continue
      const label = titleFor(all, key)
      const value = options.get(raw)
      if (label && value) rows.push({ key, label, value })
    }
    return rows
  }, [questionnaire])

  if (!profile) {
    return (
      <aside className="hidden cohab-desktop:block bg-cohab-card border border-cohab-border rounded-[18px] p-7">
        <Eyebrow className="mb-3">Your preferences</Eyebrow>
        <p className="text-[13px] leading-[1.5] text-cohab-muted">
          Finish the questionnaire and your answers will be summarised here.
        </p>
      </aside>
    )
  }

  const answers = profile.questionnaire ?? {}
  const notes = typeof answers.lifestyle_notes === 'string' ? answers.lifestyle_notes : null
  const interests = Array.isArray(answers.interests) ? (answers.interests as string[]) : []

  return (
    <aside className="hidden cohab-desktop:flex cohab-desktop:flex-col gap-6">
      <section className="bg-cohab-card border border-cohab-border rounded-[18px] p-7">
        <Eyebrow className="mb-1.5">Hard constraints</Eyebrow>
        <p className="text-[12.5px] leading-[1.45] text-cohab-subtle mb-3">
          These exclude people outright. Scoring well elsewhere cannot make up for them.
        </p>
        <Fact label="City" value={profile.city} />
        <Fact
          label="Budget"
          value={`₹${profile.budget_min.toLocaleString('en-IN')}–${profile.budget_max.toLocaleString('en-IN')}`}
        />
        <Fact label="Move-in" value={formatDate(profile.move_in_date)} />
        <Fact
          label="Roommate gender"
          value={GENDER_PREFERENCE_LABELS[profile.gender_preference] ?? profile.gender_preference}
        />
        <Fact label="You have a pet" value={profile.has_pet ? 'Yes' : 'No'} />
        <Fact
          label="Their pets"
          value={PET_TOLERANCE_LABELS[profile.pet_tolerance] ?? profile.pet_tolerance}
        />
        <Fact
          label="Smoking indoors"
          value={profile.smoking_dealbreaker ? 'Must be smoke-free' : 'Not a deal-breaker'}
        />
        {profile.severe_allergy.length > 0 && (
          <Fact label="Severe allergies" value={profile.severe_allergy.join(', ')} />
        )}
        {profile.kitchen_allergens.length > 0 && (
          <Fact label="You cook with" value={profile.kitchen_allergens.join(', ')} />
        )}
      </section>

      {lifestyle.length > 0 && (
        <section className="bg-cohab-card border border-cohab-border rounded-[18px] p-7">
          <Eyebrow className="mb-1.5">How you live</Eyebrow>
          <p className="text-[12.5px] leading-[1.45] text-cohab-subtle mb-3">
            Scored against each candidate in both directions, weighted by what you said matters.
          </p>
          {lifestyle.map((row) => (
            <Fact key={row.key} label={row.label} value={row.value} />
          ))}
        </section>
      )}

      {(interests.length > 0 || notes) && (
        <section className="bg-cohab-card border border-cohab-border rounded-[18px] p-7">
          <Eyebrow className="mb-3">In your words</Eyebrow>
          {interests.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-3">
              {interests.map((tag) => (
                <span
                  key={tag}
                  className="text-[12px] text-cohab-muted border border-cohab-border rounded-lg px-2.5 py-1"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
          {notes && <p className="text-[13px] leading-[1.55] text-cohab-muted">{notes}</p>}
        </section>
      )}
    </aside>
  )
}
