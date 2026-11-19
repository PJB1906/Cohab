import { useState } from 'react'
import { OnboardingHeader } from '@/components/OnboardingHeader'
import { StepTransition } from '@/components/motion/StepTransition'
import { useNavigate } from 'react-router-dom'
import { useOnboarding } from './OnboardingContext'
import { REQUIRED_QUESTIONS, type Question } from '@/data/questionnaire'
import { OptionRadio } from '@/components/OptionRadio'
import { ChipPill } from '@/components/OptionPill'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card } from '@/components/ui/card'
import { Eyebrow } from '@/components/Eyebrow'
import { cn } from '@/lib/utils'
import type { GenderPreference } from '@/api/types'

const GENDER_PREFS: { value: GenderPreference; label: string }[] = [
  { value: 'female', label: 'Female roommate' },
  { value: 'male', label: 'Male roommate' },
  { value: 'any', label: 'No preference' },
]

/** Mobile mockup (proto s4) labels this "3 per page" in its screen caption
 * and groups the twelve questions into four scrollable pages; the desktop
 * mockup instead gives a 268px rail listing all twelve individually and a
 * single-question card. Rather than run two disconnected state machines,
 * both breakpoints share one `currentIndex` (0-11): desktop uses it as the
 * one-question-at-a-time position directly, mobile derives the page that
 * contains it (`Math.floor(currentIndex / QUESTIONS_PER_PAGE)`) and shows
 * that whole page. Next/Back move by one question on desktop and by a full
 * page on mobile. Judgment call — not fixed by either doc (docs/DECISIONS.md
 * candidate). */
const QUESTIONS_PER_PAGE = 3

export function RequiredQuestionnaire() {
  const navigate = useNavigate()
  const { draft, update } = useOnboarding()
  const [currentIndex, setCurrentIndex] = useState(0)

  const total = REQUIRED_QUESTIONS.length
  const budgetValid =
    Number(draft.budgetMin) > 0 && Number(draft.budgetMax) > 0 && Number(draft.budgetMin) <= Number(draft.budgetMax)
  const preambleDone = Boolean(budgetValid && draft.moveInDate)

  function isAnswered(q: Question) {
    return q.parts.every((p) => draft.answers[p.key])
  }

  const doneCount = REQUIRED_QUESTIONS.filter(isAnswered).length
  const allAnswered = doneCount === total && preambleDone

  function setAnswer(key: string, value: string) {
    update({ answers: { ...draft.answers, [key]: value } })
  }

  function goTo(i: number) {
    setCurrentIndex(Math.max(0, Math.min(total - 1, i)))
  }

  function finish() {
    navigate('/onboarding/optional')
  }

  // Why Finish is disabled, in words: a greyed-out button with no reason
  // reads as a broken one (v2 audit).
  const blocker = allAnswered
    ? null
    : !budgetValid
      ? draft.budgetMin && draft.budgetMax
        ? 'Your minimum budget is above your maximum.'
        : 'Add your monthly budget at the top.'
      : !draft.moveInDate
        ? 'Add your move-in date at the top.'
        : `${total - doneCount} question${total - doneCount === 1 ? '' : 's'} still unanswered. Use Back to find ${total - doneCount === 1 ? 'it' : 'them'}.`

  const currentQuestion = REQUIRED_QUESTIONS[currentIndex]
  const pageStart = Math.floor(currentIndex / QUESTIONS_PER_PAGE) * QUESTIONS_PER_PAGE
  const pageQuestions = REQUIRED_QUESTIONS.slice(pageStart, pageStart + QUESTIONS_PER_PAGE)
  const isLastPage = pageStart + QUESTIONS_PER_PAGE >= total
  const isLastQuestion = currentIndex === total - 1

  function renderQuestionBody(q: Question) {
    return (
      <div className="flex flex-col gap-5 cohab-desktop:gap-6">
        {q.parts.map((part) => (
          <div key={part.key}>
            {part.label && (
              <span className="block mb-2 text-[13px] font-medium text-cohab-muted-mobile cohab-desktop:font-semibold cohab-desktop:text-cohab-ink/80">
                {part.label}
              </span>
            )}
            <div className="flex flex-col gap-2 cohab-desktop:gap-[9px] cohab-desktop:max-w-[640px]">
              {part.options.map((opt) => (
                <OptionRadio
                  key={opt.value}
                  selected={draft.answers[part.key] === opt.value}
                  onClick={() => setAnswer(part.key, opt.value)}
                >
                  {opt.label}
                </OptionRadio>
              ))}
            </div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <>
      <OnboardingHeader />
    <div className="min-h-dvh flex flex-col cohab-desktop:block">
      {/* Preamble: budget / dates / gender / pets / allergies / smoking — hard
          constraints for Stage 1 eligibility. Not depicted in either mockup's
          screen 4 (which only covers the twelve scored questions), so this is
          rendered as its own card ahead of the rail/question flow, in the
          same visual language, rather than folded into the 12-item rail. */}
      <div className="px-4 pt-5 cohab-desktop:max-w-[1500px] cohab-desktop:mx-auto cohab-desktop:px-6 cohab-desktop:pt-12">
        <Card className="p-5 mb-5 rounded-2xl cohab-desktop:rounded-[18px] cohab-desktop:p-7">
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
      </div>

      {/* Mobile page header — s4's mockup header has no back arrow (back
          lives in the footer only) and uses "Page X of Y" wording, not
          MobileStepHeader's "Step X of Y" + arrow — so it's built inline
          here rather than reusing that component. */}
      <div className="cohab-desktop:hidden px-4 pt-1 pb-3 border-b border-cohab-border-soft flex-none">
        <div className="flex items-baseline justify-between mb-2">
          <span className="text-[14px] font-semibold text-cohab-ink">
            Page {Math.floor(pageStart / QUESTIONS_PER_PAGE) + 1} of {Math.ceil(total / QUESTIONS_PER_PAGE)}
          </span>
          <span className="text-[12.5px] font-medium text-cohab-subtle-mobile">
            {doneCount} of {total} answered
          </span>
        </div>
        <div className="h-1 rounded-full bg-cohab-track overflow-hidden">
          <div className="h-full bg-cohab-fill rounded-full" style={{ width: `${(doneCount / total) * 100}%` }} />
        </div>
        <p className="text-[12px] text-cohab-subtle-mobile mt-1.5">
          Required. About 3 minutes — answers save as you go.
        </p>
      </div>

      <div className="cohab-desktop:max-w-[1500px] cohab-desktop:mx-auto cohab-desktop:px-6 cohab-desktop:grid cohab-desktop:grid-cols-[268px_1fr] cohab-desktop:gap-11 cohab-desktop:items-start cohab-desktop:pb-12 flex-1">
        <aside className="hidden cohab-desktop:block cohab-desktop:sticky cohab-desktop:top-8">
          <Eyebrow className="mb-2.5">Step 3 of 4 · Required</Eyebrow>
          <h2 className="text-lg font-semibold mb-1.5">The twelve that matter</h2>
          <p className="text-[13px] text-cohab-muted leading-[1.45] mb-4">
            {doneCount} of {total} answered
          </p>
          <div className="h-1 rounded-full bg-cohab-border overflow-hidden mb-[22px]">
            <div className="h-full bg-cohab-fill rounded-full" style={{ width: `${(doneCount / total) * 100}%` }} />
          </div>
          <div className="flex flex-col gap-0.5">
            {REQUIRED_QUESTIONS.map((q, i) => {
              const state = i === currentIndex ? 'current' : isAnswered(q) ? 'done' : 'upcoming'
              return (
                <button
                  key={q.id}
                  type="button"
                  onClick={() => goTo(i)}
                  className={cn(
                    'flex items-center gap-2.5 text-left rounded-xl px-3 py-2.5 text-[13.5px] leading-tight cursor-pointer transition-colors',
                    state === 'current' && 'bg-cohab-tint text-cohab-primary font-semibold',
                    state === 'done' && 'text-cohab-ink hover:bg-cohab-bg',
                    state === 'upcoming' && 'text-cohab-subtle hover:bg-cohab-bg',
                  )}
                >
                  <span
                    className={cn(
                      'flex-none w-5 h-5 rounded-full flex items-center justify-center text-[10.5px] font-semibold',
                      state === 'current' && 'bg-cohab-fill text-cohab-on-fill',
                      state === 'done' && 'border border-cohab-primary text-cohab-primary',
                      state === 'upcoming' && 'border border-cohab-border text-cohab-subtle',
                    )}
                  >
                    {state === 'done' ? '✓' : i + 1}
                  </span>
                  {q.theme}
                </button>
              )
            })}
          </div>
          <p className="text-[12px] text-cohab-subtle leading-[1.5] mt-[22px]">
            Answers save as you go. You can change any of them later from your profile.
          </p>
        </aside>

        {/* Mobile: scrollable page of QUESTIONS_PER_PAGE questions. Keyed on
            pageStart so advancing to the next group of questions re-fires
            the entrance rather than only the first page ever animating. */}
        <StepTransition step={`mobile-${pageStart}`} className="cohab-desktop:hidden flex-1 overflow-auto px-4 pt-5 pb-4">
          {pageQuestions.map((q, i) => (
            <div key={q.id} className="mb-7 pb-6 border-b border-cohab-border-soft last:border-b-0 last:mb-0 last:pb-0">
              <p className="text-[11px] font-semibold uppercase tracking-[.07em] text-cohab-subtle-mobile mb-2">
                Q{pageStart + i + 1} · {q.theme}
              </p>
              <h3 className="text-[18px] font-semibold tracking-[-.01em] text-cohab-ink leading-[1.3]">
                {q.title}
              </h3>
              {q.sub && <p className="text-[13.5px] leading-[1.45] text-cohab-muted-mobile mt-1">{q.sub}</p>}
              <div className="mt-3.5">{renderQuestionBody(q)}</div>
            </div>
          ))}
          <p className="text-[12.5px] leading-[1.5] text-cohab-subtle-mobile">
            Answer honestly rather than aspirationally — an inflated cleanliness answer produces a
            match you'll regret in week two.
          </p>
        </StepTransition>

        {/* Desktop: single question card, one at a time */}
        <StepTransition
          step={`desktop-${currentIndex}`}
          className="hidden cohab-desktop:flex cohab-desktop:flex-col bg-cohab-card border border-cohab-border rounded-[18px] px-11 py-10 min-h-[520px]"
        >
          <Eyebrow>{currentQuestion.theme}</Eyebrow>
          <h1 className="poster text-[52px] cohab-desktop:text-[64px] mt-3 max-w-[16ch]">
            {currentQuestion.title}
          </h1>
          {currentQuestion.sub && (
            <p className="text-sm text-cohab-muted leading-[1.5] mt-2.5 max-w-[600px]">{currentQuestion.sub}</p>
          )}
          <div className="mt-7">{renderQuestionBody(currentQuestion)}</div>
          <div className="flex-1" />
          <div className="flex items-center gap-3 mt-[34px] pt-[22px] border-t border-cohab-border">
            <Button variant="secondary" disabled={currentIndex === 0} onClick={() => goTo(currentIndex - 1)}>
              Back
            </Button>
            <Button
              disabled={isLastQuestion && !allAnswered}
              onClick={() => (isLastQuestion ? finish() : goTo(currentIndex + 1))}
            >
              {isLastQuestion ? `Finish — ${total} of ${total}` : 'Next'}
            </Button>
            <div className="flex-1" />
            <span className="text-xs text-cohab-subtle">
              {isLastQuestion && blocker ? <span className="text-cohab-accent">{blocker}</span> : `${doneCount} of ${total} answered`}
            </span>
          </div>
        </StepTransition>
      </div>

      {/* Mobile fixed footer */}
      {isLastPage && blocker && (
        <p className="cohab-desktop:hidden flex-none px-4 pt-2.5 text-[13px] text-cohab-accent bg-cohab-card border-t border-cohab-border-soft" role="status">
          {blocker}
        </p>
      )}
      <div className="cohab-desktop:hidden flex-none px-4 py-3 border-t border-cohab-border-soft bg-cohab-card flex gap-2.5 sticky bottom-0">
        <Button
          variant="secondary"
          className={cn(pageStart === 0 && 'invisible')}
          onClick={() => goTo(pageStart - QUESTIONS_PER_PAGE)}
        >
          Back
        </Button>
        <Button
          className="flex-1"
          disabled={isLastPage && !allAnswered}
          onClick={() => (isLastPage ? finish() : goTo(pageStart + QUESTIONS_PER_PAGE))}
        >
          {isLastPage ? 'Finish' : 'Continue'}
        </Button>
      </div>
    </div>
    </>
  )
}
