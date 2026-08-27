import { useState } from 'react'
import { OnboardingHeader } from '@/components/OnboardingHeader'
import { PageTransition } from '@/components/motion/PageTransition'
import { useNavigate } from 'react-router-dom'
import { useOnboarding } from './OnboardingContext'
import { WEIGHT_TILES } from '@/data/questionnaire'
import { WeightTile } from '@/components/WeightTile'
import { Button } from '@/components/ui/button'
import { Eyebrow } from '@/components/Eyebrow'
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

  const count = draft.importantAttributes.length
  const mobileCtaLabel = busy ? 'Saving…' : count === 0 ? 'Pick three to continue' : count < 3 ? `${3 - count} more to pick` : 'See my matches'

  return (
    <>
      <OnboardingHeader hasOwnMobileBack />
    <PageTransition>
    <div className="min-h-dvh flex flex-col cohab-desktop:block">
      {/* Mobile header — back arrow only, no step counter (proto s6 omits it). */}
      <div className="cohab-desktop:hidden px-2 py-1">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="w-11 h-11 flex items-center justify-center text-cohab-ink text-[22px] cursor-pointer"
        >
          ←
        </button>
      </div>

      <div className="flex-1 px-4 pb-4 cohab-desktop:max-w-[1160px] cohab-desktop:mx-auto cohab-desktop:px-6 cohab-desktop:py-14 cohab-desktop:pb-0">
        <Eyebrow className="hidden cohab-desktop:block mb-3.5">Step 4 of 4 · Priorities</Eyebrow>
        <h1 className="hidden cohab-desktop:block text-[26px] font-semibold tracking-[-.015em] leading-[1.18] mb-2">
          Pick the three that matter most to you
        </h1>
        <h1 className="cohab-desktop:hidden text-[26px] font-semibold tracking-[-.02em] leading-[1.2] mb-2">
          What matters most to you?
        </h1>
        <p className="text-[15px] cohab-desktop:text-[15px] text-cohab-muted-mobile cohab-desktop:text-cohab-score leading-[1.5] mb-1.5 cohab-desktop:mb-2 cohab-desktop:max-w-[660px]">
          <span className="cohab-desktop:hidden">
            Tap the three you'd least want to get wrong. They count for more in your ranking —
            everything else still counts.
          </span>
          <span className="hidden cohab-desktop:inline">
            Your three are weighted more heavily when Cohab scores candidates for you. Everyone
            weights these differently, which is why your ranking and theirs are not the same list.
          </span>
        </p>
        <p className="text-[13px] font-medium text-cohab-primary cohab-desktop:font-normal cohab-desktop:text-cohab-subtle mb-3 cohab-desktop:mb-[26px]">
          {count} of 3 selected
        </p>

        <div className="flex flex-col gap-[9px] cohab-desktop:grid cohab-desktop:grid-cols-3 cohab-desktop:gap-3">
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

        <div className="cohab-desktop:hidden mt-[18px] px-[15px] py-3.5 bg-cohab-card rounded-2xl text-[13px] leading-[1.5] text-cohab-muted-mobile">
          Skip this and we use the platform defaults, which are weighted from reported conflict
          data. Nothing breaks either way.
        </div>

        {error && <p className="text-sm text-cohab-accent mt-4">{error}</p>}

        <div className="hidden cohab-desktop:flex items-center gap-3.5 mt-7">
          <Button onClick={save} disabled={busy}>
            {busy ? 'Saving…' : 'See my matches'}
          </Button>
          <Button variant="ghost" onClick={save} disabled={busy}>
            Skip — use the platform defaults
          </Button>
        </div>
      </div>

      {/* Mobile sticky footer */}
      <div className="cohab-desktop:hidden flex-none px-4 pt-3 pb-2 border-t border-cohab-border-soft bg-cohab-card sticky bottom-0">
        <Button className="w-full" onClick={save} disabled={busy}>
          {mobileCtaLabel}
        </Button>
        <button
          type="button"
          onClick={save}
          disabled={busy}
          className="block w-full text-center text-sm font-medium text-cohab-muted-mobile py-3.5 cursor-pointer disabled:opacity-50"
        >
          Skip — use the defaults
        </button>
      </div>
    </div>
    </PageTransition>
    </>
  )
}
