import { useNavigate } from 'react-router-dom'
import { useOnboarding } from './OnboardingContext'
import { OPTIONAL_TIER2_QUESTIONS, INTEREST_TAGS, LIFESTYLE_NOTES_PROMPT } from '@/data/questionnaire'
import { ChipPill } from '@/components/OptionPill'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'

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

  return (
    <div className="max-w-2xl mx-auto px-4 py-10">
      <p className="font-mono text-[10px] uppercase tracking-wider text-cohab-subtle mb-3">
        Optional · Step 3 of 4
      </p>
      <h1 className="text-2xl font-semibold tracking-tight mb-2">Depth, if you want it</h1>
      <p className="text-[15px] text-cohab-muted mb-7">
        These six questions carry 15% of the score. Skipping them costs you nothing — unanswered
        attributes are dropped from both sides, never guessed at.
      </p>

      {OPTIONAL_TIER2_QUESTIONS.map((q) => (
        <Card key={q.id} className="p-6 mb-5">
          <span className="font-mono text-[10px] uppercase tracking-wider text-cohab-subtle">{q.theme}</span>
          <h2 className="text-lg font-semibold mt-1 mb-1">{q.title}</h2>
          {q.sub && <p className="text-[13px] text-cohab-muted mb-3">{q.sub}</p>}
          <div className="flex flex-wrap gap-2 mt-2">
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

      <Card className="p-6 mb-5">
        <span className="font-mono text-[10px] uppercase tracking-wider text-cohab-subtle">Interests</span>
        <h2 className="text-lg font-semibold mt-1 mb-4">What are you into?</h2>
        <div className="flex flex-wrap gap-2">
          {INTEREST_TAGS.map((tag) => (
            <ChipPill key={tag.value} selected={draft.interests.includes(tag.value)} onClick={() => toggleInterest(tag.value)}>
              {tag.label}
            </ChipPill>
          ))}
        </div>
      </Card>

      <Card className="p-6 mb-6">
        <span className="font-mono text-[10px] uppercase tracking-wider text-cohab-subtle">About you</span>
        <h2 className="text-lg font-semibold mt-1 mb-1">A note for your matches</h2>
        <p className="text-[13px] text-cohab-muted mb-3">{LIFESTYLE_NOTES_PROMPT}</p>
        <Textarea
          rows={4}
          placeholder="Second-year MSc, mostly on campus till 7. I cook on weekends and I like a quiet flat on weeknights…"
          value={draft.notes}
          onChange={(e) => update({ notes: e.target.value })}
        />
      </Card>

      <div className="flex items-center gap-4">
        <Button onClick={proceed}>Save and continue</Button>
        <Button variant="ghost" onClick={proceed}>
          Skip for now
        </Button>
      </div>
    </div>
  )
}
