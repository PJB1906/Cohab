import { useNavigate } from 'react-router-dom'
import { useOnboarding } from './OnboardingContext'
import { REQUIRED_QUESTIONS, REQUIRED_QUESTIONNAIRE_KEYS } from '@/data/questionnaire'
import { OptionPill, ChipPill } from '@/components/OptionPill'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import type { GenderPreference } from '@/api/types'

const GENDER_PREFS: { value: GenderPreference; label: string }[] = [
  { value: 'female', label: 'Female roommate' },
  { value: 'male', label: 'Male roommate' },
  { value: 'any', label: 'No preference' },
]

export function RequiredQuestionnaire() {
  const navigate = useNavigate()
  const { draft, update } = useOnboarding()

  const answeredCount = REQUIRED_QUESTIONNAIRE_KEYS.filter((k) => draft.answers[k]).length
  const preambleDone = Boolean(draft.budgetMin && draft.budgetMax && draft.moveInDate)
  const totalSteps = REQUIRED_QUESTIONNAIRE_KEYS.length + 1
  const doneSteps = answeredCount + (preambleDone ? 1 : 0)

  const allAnswered = answeredCount === REQUIRED_QUESTIONNAIRE_KEYS.length && preambleDone

  function setAnswer(key: string, value: string) {
    update({ answers: { ...draft.answers, [key]: value } })
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-10">
      <p className="font-mono text-[10px] uppercase tracking-wider text-cohab-subtle mb-3">
        Step 3 of 4 · Required
      </p>
      <h1 className="text-2xl font-semibold tracking-tight mb-2">The twelve that matter</h1>
      <p className="text-[15px] text-cohab-muted mb-4">
        Under four minutes. Answers save as you go — you can change any of them later from your
        profile.
      </p>
      <Progress value={(doneSteps / totalSteps) * 100} className="mb-8" />

      <Card className="p-6 mb-5">
        <h2 className="text-base font-semibold mb-1">Where and when are you looking</h2>
        <p className="text-[13px] text-cohab-muted mb-4">
          These act as your hard constraints — candidates outside them are never shown to you.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
          <div>
            <Label htmlFor="budget-min">Budget, monthly (₹) — minimum</Label>
            <Input
              id="budget-min"
              type="number"
              min={1}
              required
              value={draft.budgetMin}
              onChange={(e) => update({ budgetMin: e.target.value })}
            />
          </div>
          <div>
            <Label htmlFor="budget-max">Budget, monthly (₹) — maximum</Label>
            <Input
              id="budget-max"
              type="number"
              min={1}
              required
              value={draft.budgetMax}
              onChange={(e) => update({ budgetMax: e.target.value })}
            />
          </div>
          <div>
            <Label htmlFor="move-in">Move-in date</Label>
            <Input
              id="move-in"
              type="date"
              required
              value={draft.moveInDate}
              onChange={(e) => update({ moveInDate: e.target.value })}
            />
          </div>
        </div>

        <Label>Roommate gender preference</Label>
        <div className="flex flex-wrap gap-2 mb-4">
          {GENDER_PREFS.map((g) => (
            <ChipPill
              key={g.value}
              selected={draft.genderPreference === g.value}
              onClick={() => update({ genderPreference: g.value })}
            >
              {g.label}
            </ChipPill>
          ))}
        </div>

        <Label>Do you have a pet?</Label>
        <div className="flex flex-wrap gap-2 mb-4">
          <ChipPill selected={!draft.hasPet} onClick={() => update({ hasPet: false })}>
            No
          </ChipPill>
          <ChipPill selected={draft.hasPet} onClick={() => update({ hasPet: true })}>
            Yes
          </ChipPill>
        </div>

        <Label>Comfort with a roommate's pets</Label>
        <div className="flex flex-wrap gap-2 mb-4">
          <ChipPill
            selected={draft.petTolerance === 'comfortable'}
            onClick={() => update({ petTolerance: 'comfortable' })}
          >
            Comfortable with pets
          </ChipPill>
          <ChipPill
            selected={draft.petTolerance === 'cannot_live_with_pets'}
            onClick={() => update({ petTolerance: 'cannot_live_with_pets' })}
          >
            Can't live with pets
          </ChipPill>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
          <div>
            <Label htmlFor="allergies">Severe allergies (comma separated)</Label>
            <Input
              id="allergies"
              placeholder="e.g. peanuts, shellfish"
              value={draft.severeAllergy.join(', ')}
              onChange={(e) =>
                update({ severeAllergy: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })
              }
            />
          </div>
          <div>
            <Label htmlFor="kitchen-allergens">Allergens you cook with (comma separated)</Label>
            <Input
              id="kitchen-allergens"
              placeholder="e.g. peanuts, shellfish"
              value={draft.kitchenAllergens.join(', ')}
              onChange={(e) =>
                update({ kitchenAllergens: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })
              }
            />
          </div>
        </div>

        <Label>Smoking indoors</Label>
        <div className="flex flex-wrap gap-2">
          <ChipPill selected={!draft.smokingDealbreaker} onClick={() => update({ smokingDealbreaker: false })}>
            Not a deal-breaker for me
          </ChipPill>
          <ChipPill selected={draft.smokingDealbreaker} onClick={() => update({ smokingDealbreaker: true })}>
            Must be smoke-free
          </ChipPill>
        </div>
      </Card>

      {REQUIRED_QUESTIONS.map((q) => (
        <Card key={q.id} className="p-6 mb-5">
          <span className="font-mono text-[10px] uppercase tracking-wider text-cohab-subtle">{q.theme}</span>
          <h2 className="text-lg font-semibold mt-1 mb-1">{q.title}</h2>
          {q.sub && <p className="text-[13px] text-cohab-muted mb-4">{q.sub}</p>}
          <div className={q.sub ? 'flex flex-col gap-5' : 'flex flex-col gap-5 mt-4'}>
            {q.parts.map((part) => (
              <div key={part.key}>
                {part.label && (
                  <span className="block text-[13px] font-semibold text-cohab-ink/80 mb-2">{part.label}</span>
                )}
                <div className="flex flex-col gap-2">
                  {part.options.map((opt) => (
                    <OptionPill
                      key={opt.value}
                      selected={draft.answers[part.key] === opt.value}
                      onClick={() => setAnswer(part.key, opt.value)}
                    >
                      {opt.label}
                    </OptionPill>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Card>
      ))}

      <p className="text-[12.5px] text-cohab-subtle mb-4">
        Answer honestly rather than aspirationally — an inflated cleanliness answer produces a
        match you'll regret in week two.
      </p>

      <Button disabled={!allAnswered} onClick={() => navigate('/onboarding/optional')}>
        Continue
      </Button>
    </div>
  )
}
