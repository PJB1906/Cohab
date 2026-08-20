import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { feedbackApi } from '@/api/feedback'
import { ApiError } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { OptionPill } from '@/components/OptionPill'
import type { FeedbackOutcome } from '@/api/types'

const REJECTED_OPTIONS: { value: FeedbackOutcome; label: string }[] = [
  { value: 'not_pursued', label: "Didn't end up talking further" },
  { value: 'incompatible', label: "Talked, but weren't compatible" },
  { value: 'other', label: 'Something else' },
]

const COHABITING_OPTIONS: { value: FeedbackOutcome; label: string }[] = [
  { value: 'still_together', label: 'Still living together' },
  { value: 'moved_out', label: 'No longer living together' },
]

/** PRD §9 screen 12 ("Outcome feedback"), §8.2 ("outcome logged" on
 * Cohabiting/Rejected). A modal, same pattern as ReportDialog — this fires
 * from wherever GET /feedback/pending surfaces it, not its own route. */
export function FeedbackDialog({
  matchId,
  otherUserName,
  state,
  onClose,
}: {
  matchId: string
  otherUserName: string
  state: 'cohabiting' | 'rejected'
  onClose: () => void
}) {
  const [outcome, setOutcome] = useState<FeedbackOutcome | null>(null)
  const [durationDays, setDurationDays] = useState('')
  const queryClient = useQueryClient()
  const options = state === 'cohabiting' ? COHABITING_OPTIONS : REJECTED_OPTIONS

  const mutation = useMutation({
    mutationFn: () =>
      feedbackApi.submit(matchId, {
        outcome: outcome as FeedbackOutcome,
        cohabitation_duration_days:
          outcome === 'moved_out' && durationDays ? Number(durationDays) : null,
      }),
    onSuccess: () => {
      queryClient.setQueryData<{ match_id: string }[]>(['feedback', 'pending'], (prev) =>
        prev?.filter((p) => p.match_id !== matchId),
      )
      queryClient.invalidateQueries({ queryKey: ['feedback', 'pending'] })
    },
  })

  if (mutation.isSuccess) {
    return (
      <div className="fixed inset-0 bg-black/40 flex items-end sm:items-center justify-center p-4 z-50">
        <div className="bg-white rounded-2xl p-6 max-w-sm w-full">
          <h2 className="text-base font-semibold mb-2">Thanks for letting us know</h2>
          <p className="text-[13.5px] text-cohab-muted mb-5">
            This helps us improve future matches.
          </p>
          <Button onClick={onClose} className="w-full">
            Done
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-end sm:items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl p-6 max-w-sm w-full max-h-[85vh] overflow-y-auto">
        <h2 className="text-base font-semibold mb-1">How did it go with {otherUserName}?</h2>
        <p className="text-[13px] text-cohab-muted mb-4">
          A quick check-in — this is what lets us improve the scoring over time.
        </p>

        <div className="flex flex-col gap-2 mb-4">
          {options.map((o) => (
            <OptionPill key={o.value} selected={outcome === o.value} onClick={() => setOutcome(o.value)}>
              {o.label}
            </OptionPill>
          ))}
        </div>

        {outcome === 'moved_out' && (
          <Input
            type="number"
            min={0}
            placeholder="How many days did you live together?"
            value={durationDays}
            onChange={(e) => setDurationDays(e.target.value)}
            className="mb-4"
          />
        )}

        {mutation.isError && (
          <p className="text-[13px] text-cohab-accent mb-3">
            {mutation.error instanceof ApiError ? mutation.error.message : 'Could not submit this — try again.'}
          </p>
        )}

        <div className="flex flex-col gap-2">
          <Button onClick={() => mutation.mutate()} disabled={!outcome || mutation.isPending} className="w-full">
            Submit
          </Button>
          <Button variant="secondary" onClick={onClose} className="w-full">
            Not now
          </Button>
        </div>
      </div>
    </div>
  )
}
