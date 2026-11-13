import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { profileApi } from '@/api/profile'
import { REQUIRED_QUESTIONNAIRE_KEYS } from '@/data/questionnaire'
import type { GenderPreference, PetTolerance, ProfileOut } from '@/api/types'

/** Accumulates screens 3-6's answers client-side. `PUT /profile` takes the
 * whole profile in one call — there's no per-question save endpoint — so
 * this holds the draft across screens and only hits the API once, on the
 * importance-weighting screen's continue/skip (docs/DECISIONS.md D-5.1).
 * Persisted to sessionStorage so a refresh mid-flow doesn't lose progress. */
export interface OnboardingDraft {
  city: string
  budgetMin: string
  budgetMax: string
  moveInDate: string
  genderPreference: GenderPreference
  hasPet: boolean
  petTolerance: PetTolerance
  severeAllergy: string[]
  kitchenAllergens: string[]
  smokingDealbreaker: boolean
  answers: Record<string, string>
  optAnswers: Record<string, string>
  interests: string[]
  notes: string
  importantAttributes: string[]
}

const EMPTY_DRAFT: OnboardingDraft = {
  city: 'Bangalore',
  budgetMin: '',
  budgetMax: '',
  moveInDate: '',
  genderPreference: 'any',
  hasPet: false,
  petTolerance: 'comfortable',
  severeAllergy: [],
  kitchenAllergens: [],
  smokingDealbreaker: false,
  answers: {},
  optAnswers: {},
  interests: [],
  notes: '',
  importantAttributes: [],
}

const STORAGE_KEY = 'cohab.onboarding.draft'

/** A saved profile as an editable draft. Without this, opening any onboarding
 * screen from Profile ("edit") started from an empty draft: the last screen
 * then submitted a blank budget and move-in date, the API rejected it, and
 * the raw validation JSON was shown to the user. Worse, a filled-in required
 * screen would have overwritten the rest of the profile with blanks. */
function draftFromProfile(p: ProfileOut): OnboardingDraft {
  const answers: Record<string, string> = {}
  const optAnswers: Record<string, string> = {}
  for (const [key, value] of Object.entries(p.questionnaire ?? {})) {
    if (typeof value !== 'string' || key === 'lifestyle_notes') continue
    if (REQUIRED_QUESTIONNAIRE_KEYS.includes(key)) answers[key] = value
    else optAnswers[key] = value
  }
  const interests = p.questionnaire?.interests
  const notes = p.questionnaire?.lifestyle_notes
  return {
    city: p.city,
    budgetMin: String(p.budget_min),
    budgetMax: String(p.budget_max),
    moveInDate: p.move_in_date,
    genderPreference: p.gender_preference as GenderPreference,
    hasPet: p.has_pet,
    petTolerance: p.pet_tolerance as PetTolerance,
    severeAllergy: p.severe_allergy ?? [],
    kitchenAllergens: p.kitchen_allergens ?? [],
    smokingDealbreaker: p.smoking_dealbreaker,
    answers,
    optAnswers,
    interests: Array.isArray(interests) ? (interests as string[]) : [],
    notes: typeof notes === 'string' ? notes : '',
    importantAttributes: p.important_attributes ?? [],
  }
}

function readStoredDraft(): OnboardingDraft | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    return raw ? { ...EMPTY_DRAFT, ...JSON.parse(raw) } : null
  } catch {
    return null
  }
}

const OnboardingContext = createContext<{
  draft: OnboardingDraft
  update: (patch: Partial<OnboardingDraft>) => void
  reset: () => void
} | null>(null)

export function OnboardingProvider({ children }: { children: ReactNode }) {
  // A draft already in sessionStorage is work in progress and wins. With
  // none, an existing profile (an edit visit) seeds the draft; a first-run
  // signup has no profile (GET /profile 404s) and starts empty.
  const [stored] = useState(readStoredDraft)
  const [draft, setDraft] = useState<OnboardingDraft>(stored ?? EMPTY_DRAFT)
  // A stored draft that already has the required details is complete enough
  // to use as is; one without them (left over from an edit visit that began
  // empty) still needs the saved profile underneath it.
  const [hydrated, setHydrated] = useState(stored !== null && Boolean(stored.budgetMin && stored.moveInDate))
  const profile = useQuery({
    // Its own key: ProfilePage caches "no profile" as null under ['profile'],
    // and a null there must not be mistaken for "still loading" here.
    queryKey: ['profile', 'draft-seed'],
    queryFn: () => profileApi.get(),
    retry: false,
    enabled: !hydrated,
    staleTime: 0,
    gcTime: 0,
  })

  useEffect(() => {
    if (hydrated) return
    if (profile.data) {
      const saved = draftFromProfile(profile.data)
      setDraft(
        stored
          ? {
              ...saved,
              answers: { ...saved.answers, ...stored.answers },
              optAnswers: { ...saved.optAnswers, ...stored.optAnswers },
              interests: stored.interests.length ? stored.interests : saved.interests,
              notes: stored.notes || saved.notes,
              importantAttributes: stored.importantAttributes.length
                ? stored.importantAttributes
                : saved.importantAttributes,
            }
          : saved,
      )
      setHydrated(true)
    } else if (profile.isError || profile.isSuccess) {
      setHydrated(true) // no profile yet: genuine first run
    }
  }, [hydrated, profile.data, profile.isError, profile.isSuccess, stored])

  useEffect(() => {
    if (!hydrated) return
    try {
      // After reset() the draft is the empty constant: keep storage clear
      // rather than writing a blank draft back for the next visit to find.
      if (draft === EMPTY_DRAFT) sessionStorage.removeItem(STORAGE_KEY)
      else sessionStorage.setItem(STORAGE_KEY, JSON.stringify(draft))
    } catch {
      // storage unavailable (private mode): the in-memory draft still works
    }
  }, [draft, hydrated])

  function update(patch: Partial<OnboardingDraft>) {
    setDraft((prev) => ({ ...prev, ...patch }))
  }

  function reset() {
    try {
      sessionStorage.removeItem(STORAGE_KEY)
    } catch {
      // ignore
    }
    setDraft(EMPTY_DRAFT)
  }

  // Render nothing until the draft is known, so no screen can show (or
  // submit) an empty form over a saved profile.
  if (!hydrated) return null

  return (
    <OnboardingContext.Provider value={{ draft, update, reset }}>
      {children}
    </OnboardingContext.Provider>
  )
}

export function useOnboarding() {
  const ctx = useContext(OnboardingContext)
  if (!ctx) throw new Error('useOnboarding must be used within OnboardingProvider')
  return ctx
}
