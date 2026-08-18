import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useOnboarding } from './OnboardingContext'
import { WEIGHT_TILES } from '@/data/questionnaire'
import { WeightTile } from '@/components/WeightTile'
import { Button } from '@/components/ui/button'
import { profileApi } from '@/api/profile'
import { ApiError } from '@/api/client'
import type { ProfileUpsertRequest } from '@/api/types'

export function ImportanceWeights() {
  const navigate = useNavigate()
  const { draft, update, reset } = useOnboarding()
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  function toggle(id: string) {
    const selected = draft.importantAttributes
    if (selected.includes(id)) {
      update({ importantAttributes: selected.filter((x) => x !== id) })
    } else if (selected.length < 3) {
      update({ importantAttributes: [...selected, id] })
    }
  }

  async function save() {
    setBusy(true)
    setError(null)
    try {
      const body: ProfileUpsertRequest = {
        budget_min: Number(draft.budgetMin),
        budget_max: Number(draft.budgetMax),
        move_in_date: draft.moveInDate,
        gender_preference: draft.genderPreference,
        severe_allergy: draft.severeAllergy,
        kitchen_allergens: draft.kitchenAllergens,
        has_pet: draft.hasPet,
        pet_tolerance: draft.petTolerance,
        smoking_dealbreaker: draft.smokingDealbreaker,
        questionnaire: {
          ...draft.answers,
          ...draft.optAnswers,
          interests: draft.interests,
          lifestyle_notes: draft.notes,
        },
        important_attributes: draft.importantAttributes,
      }
      await profileApi.put(body)
      reset()
      navigate('/matches')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-10">
      <p className="font-mono text-[10px] uppercase tracking-wider text-cohab-subtle mb-3">
        Step 4 of 4 · Priorities
      </p>
      <h1 className="text-2xl font-semibold tracking-tight mb-2">Pick the three that matter most to you</h1>
      <p className="text-[15px] text-cohab-muted mb-1">
        Your three are weighted more heavily when Cohab scores candidates for you. Everyone
        weights these differently, which is why your ranking and theirs aren't the same list.
      </p>
      <p className="text-[13px] text-cohab-subtle mb-6">{draft.importantAttributes.length} of 3 selected</p>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-8">
        {WEIGHT_TILES.map((tile) => {
          const idx = draft.importantAttributes.indexOf(tile.id)
          return (
            <WeightTile
              key={tile.id}
              title={tile.title}
              sub={tile.sub}
              rank={idx >= 0 ? idx + 1 : null}
              onClick={() => toggle(tile.id)}
            />
          )
        })}
      </div>

      {error && <p className="text-sm text-cohab-accent mb-4">{error}</p>}

      <div className="flex items-center gap-4">
        <Button onClick={save} disabled={busy}>
          {busy ? 'Saving…' : 'See my matches'}
        </Button>
        <Button variant="ghost" onClick={save} disabled={busy}>
          Skip — use the platform defaults
        </Button>
      </div>
    </div>
  )
}
