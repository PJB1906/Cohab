import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import type { GenderPreference, PetTolerance } from '@/api/types'

/** Accumulates screens 3-6's answers client-side. `PUT /profile` takes the
 * whole profile in one call — there's no per-question save endpoint — so
 * this holds the draft across screens and only hits the API once, on the
 * importance-weighting screen's continue/skip (docs/DECISIONS.md D-5.1).
 * Persisted to sessionStorage so a refresh mid-flow doesn't lose progress. */
export interface OnboardingDraft {
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

const OnboardingContext = createContext<{
  draft: OnboardingDraft
  update: (patch: Partial<OnboardingDraft>) => void
  reset: () => void
} | null>(null)

export function OnboardingProvider({ children }: { children: ReactNode }) {
  const [draft, setDraft] = useState<OnboardingDraft>(() => {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return EMPTY_DRAFT
    try {
      return { ...EMPTY_DRAFT, ...JSON.parse(raw) }
    } catch {
      return EMPTY_DRAFT
    }
  })

  useEffect(() => {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(draft))
  }, [draft])

  function update(patch: Partial<OnboardingDraft>) {
    setDraft((prev) => ({ ...prev, ...patch }))
  }

  function reset() {
    sessionStorage.removeItem(STORAGE_KEY)
    setDraft(EMPTY_DRAFT)
  }

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
