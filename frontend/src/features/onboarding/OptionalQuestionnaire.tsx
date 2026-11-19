import { useNavigate } from 'react-router-dom'
import { OnboardingHeader } from '@/components/OnboardingHeader'
import { PageTransition } from '@/components/motion/PageTransition'
import { useOnboarding } from './OnboardingContext'
import { OPTIONAL_TIER2_QUESTIONS, INTEREST_TAGS, LIFESTYLE_NOTES_PROMPT } from '@/data/questionnaire'
import { ChipPill } from '@/components/OptionPill'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { Eyebrow } from '@/components/Eyebrow'

const TOTAL_OPTIONAL = OPTIONAL_TIER2_QUESTIONS.length + 2 // + interests + notes

export function OptionalQuestionnaire() {
  const navigate = useNavigate()
  const { draft, update } = useOnboarding()

  function setOptAnswer(key: string, value: string) {
    update({ optAnswers: { ...draft.optAnswers, [key]: value } })
  }

  function toggleInterest(tag: string) {
    update({
      interests: draft.interests.includes(tag)
        ? draft.interests.filter((t) => t !== tag)
        : [...draft.interests, tag],
    })
  }

  function proceed() {
    navigate('/onboarding/weights')
  }

  const doneMain = OPTIONAL_TIER2_QUESTIONS.filter((q) => draft.optAnswers[q.parts[0].key]).length
  const doneOptional = doneMain + (draft.interests.length > 0 ? 1 : 0) + (draft.notes.trim() ? 1 : 0)

  return (
    <>
      <OnboardingHeader hasOwnMobileBack />
    <PageTransition>
    <div className="cohab-desktop:max-w-[1500px] cohab-desktop:mx-auto cohab-desktop:px-6 cohab-desktop:py-12 cohab-desktop:grid cohab-desktop:grid-cols-[268px_1fr] cohab-desktop:gap-11 cohab-desktop:items-start">
      {/* Mobile header — back arrow + skip link, no step counter (that lives
          in the progress-summary card further down, per proto s5). */}
      <div className="cohab-desktop:hidden px-2 py-1 flex items-center justify-between">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="w-11 h-11 flex items-center justify-center text-cohab-ink text-[22px] cursor-pointer"
        >
          ←
        </button>
        <button type="button" onClick={proceed} className="h-11 px-1 text-cohab-primary text-sm font-semibold cursor-pointer">
          Skip for now
        </button>
      </div>

      <aside className="hidden cohab-desktop:block cohab-desktop:sticky cohab-desktop:top-8">
        <Eyebrow className="mb-2.5">Optional · Step 3 of 4</Eyebrow>
        <h2 className="text-lg font-semibold mb-1.5">Depth, if you want it</h2>
        <p className="text-[13px] text-cohab-muted leading-[1.45] mb-[18px]">
          These six questions carry 15% of the score. Skipping them costs you nothing — unanswered
          attributes are dropped from both sides, never guessed at.
        </p>
        <div className="inline-flex items-center gap-[7px] border border-cohab-border rounded-full bg-cohab-card px-3 py-1.5 mb-5">
          <span className="w-1.5 h-1.5 rounded-full bg-cohab-accent" />
          <span className="text-xs font-medium text-cohab-ink/85">
            {doneOptional} of {TOTAL_OPTIONAL} answered
          </span>
        </div>
        <div className="border-t border-cohab-border pt-4">
          <p className="text-xs font-semibold mb-1.5">Where this is used</p>
          <p className="text-xs text-cohab-muted leading-[1.5]">
            Life stage and daily rhythm explain why two night owls can still clash. Interests and
            your note supply the wording on your match cards.
          </p>
        </div>
      </aside>

      <div className="px-4 pt-4 pb-8 cohab-desktop:px-0 cohab-desktop:pt-0 cohab-desktop:pb-0 flex flex-col gap-4">
        <h1 className="cohab-desktop:hidden poster text-[46px] mb-2">
          A bit more, if you have a minute
        </h1>
        <p className="cohab-desktop:hidden text-[14.5px] text-cohab-muted-mobile leading-[1.5] -mt-2 mb-1">
          Optional. These sharpen your matches rather than deciding them — daily rhythm counts for
          about a tenth of your score, shared interests half that.
        </p>

        <Card className="cohab-desktop:hidden p-3.5 rounded-2xl bg-cohab-tint border-cohab-border">
          <div className="flex items-baseline justify-between mb-2">
            <span className="text-[13.5px] font-semibold text-cohab-primary">
              {doneOptional} of {TOTAL_OPTIONAL} answered
            </span>
            <span className="text-xs text-cohab-score">Saved automatically</span>
          </div>
          <div className="h-1 rounded-full bg-cohab-bubble-mint overflow-hidden">
            <div
              className="h-full bg-cohab-primary rounded-full"
              style={{ width: `${(doneOptional / TOTAL_OPTIONAL) * 100}%` }}
            />
          </div>
          <p className="text-xs text-cohab-score leading-[1.45] mt-2">
            Come back any time — nothing here is required.
          </p>
        </Card>

        {OPTIONAL_TIER2_QUESTIONS.map((q, i) => (
          <Card key={q.id} className="p-5 cohab-desktop:p-[26px] rounded-2xl cohab-desktop:rounded-2xl">
            <div className="flex items-baseline gap-2.5 mb-1 cohab-desktop:mb-1">
              <span className="font-mono text-[10px] uppercase tracking-wider text-cohab-subtle cohab-desktop:tracking-[.06em]">
                Q{13 + i}
              </span>
              <span className="text-[11px] cohab-desktop:text-[11px] text-cohab-subtle-mobile cohab-desktop:text-cohab-placeholder">
                {q.theme}
              </span>
            </div>
            <h3 className="text-lg cohab-desktop:text-[17px] font-semibold leading-[1.2] cohab-desktop:leading-[1.15] mb-3 cohab-desktop:mb-4">
              {q.title}
            </h3>
            <div className="flex flex-wrap gap-2 cohab-desktop:gap-[9px]">
              {q.parts[0].options.map((opt) => (
                <ChipPill
                  key={opt.value}
                  selected={draft.optAnswers[q.parts[0].key] === opt.value}
                  onClick={() => setOptAnswer(q.parts[0].key, opt.value)}
                >
                  {opt.label}
                </ChipPill>
              ))}
            </div>
          </Card>
        ))}

        <Card className="p-5 cohab-desktop:p-[26px] rounded-2xl">
          <div className="flex items-baseline gap-2.5 mb-1">
            <span className="font-mono text-[10px] uppercase tracking-wider text-cohab-subtle">Q17</span>
            <span className="text-[11px] text-cohab-subtle-mobile cohab-desktop:text-cohab-placeholder">
              Interests
            </span>
          </div>
          <h3 className="text-lg cohab-desktop:text-[17px] font-semibold mb-3 cohab-desktop:mb-4">
            What are you into?
          </h3>
          <div className="flex flex-wrap gap-2">
            {INTEREST_TAGS.map((tag) => (
              <ChipPill key={tag.value} selected={draft.interests.includes(tag.value)} onClick={() => toggleInterest(tag.value)}>
                {tag.label}
              </ChipPill>
            ))}
          </div>
        </Card>

        <Card className="p-5 cohab-desktop:p-[26px] rounded-2xl">
          <div className="flex items-baseline gap-2.5 mb-1">
            <span className="font-mono text-[10px] uppercase tracking-wider text-cohab-subtle">lifestyle_notes</span>
            <span className="text-[11px] text-cohab-subtle-mobile cohab-desktop:text-cohab-placeholder">
              Tier 3 · Affinity
            </span>
          </div>
          <h3 className="text-lg cohab-desktop:text-[17px] font-semibold mb-1">A note for your matches</h3>
          <p className="text-[13px] cohab-desktop:text-[13px] text-cohab-muted leading-[1.45] mb-3">
            {LIFESTYLE_NOTES_PROMPT}
          </p>
          <Textarea
            rows={4}
            className="min-h-[96px] cohab-desktop:min-h-[110px]"
            placeholder="Second-year MSc, mostly on campus till 7. I cook on weekends and I like a quiet flat on weeknights…"
            value={draft.notes}
            onChange={(e) => update({ notes: e.target.value })}
          />
        </Card>

        {/* Desktop footer */}
        <div className="hidden cohab-desktop:flex items-center gap-3 pt-1">
          <Button onClick={proceed}>Save and continue</Button>
          <Button variant="secondary" onClick={proceed}>
            Skip for now
          </Button>
          <span className="text-xs text-cohab-subtle">You can come back to this from your profile at any time.</span>
        </div>

        {/* Mobile inline buttons — stacked, end of scroll content */}
        <div className="cohab-desktop:hidden flex flex-col gap-2.5">
          <Button className="w-full" onClick={proceed}>
            Save and continue
          </Button>
          <Button className="w-full" variant="secondary" onClick={proceed}>
            Finish this later
          </Button>
        </div>
      </div>
    </div>
    </PageTransition>
    </>
  )
}
