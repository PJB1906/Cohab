import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { feedbackApi } from '@/api/feedback'
import { ApiError } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog } from '@/components/ui/dialog'
import { ChipPill } from '@/components/OptionPill'
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
 * from wherever GET /feedback/pending surfaces it, not its own route.
 *
 * Both mockups' screen 12 only depict the cohabiting check-in ("Are you
 * still living together?"). Desktop additionally shows a 7-option "biggest
 * friction" question and the mobile prototype a 1–5 "how well is it going"
 * rating scale — neither has a backing field on `FeedbackRequest` (only
 * `outcome` and `cohabitation_duration_days` exist), so neither is
 * implemented here: rendering them would mean either a control that
 * silently discards its answer or inventing new API fields, both out of
 * scope. The rejected-state question set has no mockup screen at all and
 * keeps its existing generic framing. */
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
      <Dialog open onClose={onClose} className="cohab-desktop:max-w-[440px]">
        <h2 className="text-[19px] cohab-desktop:text-base font-semibold text-cohab-ink mb-2">
          Thanks for letting us know
        </h2>
        <p className="text-[14px] cohab-desktop:text-[13.5px] leading-[1.5] text-cohab-muted mb-6">
          This helps us improve future matches.
        </p>
        <Button onClick={onClose} className="w-full cohab-desktop:w-auto">
          Done
        </Button>
      </Dialog>
    )
  }

  return (
    <Dialog
      open
      onClose={onClose}
      className="rounded-none h-screen max-h-screen cohab-desktop:h-auto cohab-desktop:max-h-[85vh] cohab-desktop:rounded-2xl cohab-desktop:max-w-[640px]"
    >
      <div className="flex items-center justify-between -mx-6 -mt-6 mb-5 px-5 h-11 border-b border-cohab-border-soft cohab-desktop:hidden">
        <span className="text-[15px] font-semibold text-cohab-ink">30-day check-in</span>
        <button
          type="button"
          onClick={onClose}
          className="w-11 h-11 -mr-5 flex items-center justify-center text-cohab-subtle-mobile text-xl cursor-pointer"
        >
          ✕
        </button>
      </div>

      <span className="hidden cohab-desktop:block font-mono text-[10px] uppercase tracking-[.08em] text-cohab-subtle mb-3.5">
        30-day check-in
      </span>
      <h1 className="text-[20px] cohab-desktop:text-[26px] font-semibold leading-[1.2] cohab-desktop:leading-[1.18] tracking-[-.015em] text-cohab-ink mb-2">
        How did it go with {otherUserName}?
      </h1>
      <p className="text-[14px] cohab-desktop:text-[15px] leading-[1.55] text-cohab-muted mb-6">
        A quick check-in — this is what lets us improve the scoring over time. Your answers
        aren't shown to {otherUserName}.
      </p>

      <div className="cohab-desktop:bg-cohab-card cohab-desktop:border cohab-desktop:border-cohab-border cohab-desktop:rounded-2xl cohab-desktop:p-6 mb-4">
        {state === 'cohabiting' && (
          <h2 className="text-[15px] cohab-desktop:text-[17px] font-semibold text-cohab-ink mb-3.5">
            Are you still living together?
          </h2>
        )}
        <div className="flex flex-wrap gap-2.5">
          {options.map((o) => (
            <ChipPill key={o.value} selected={outcome === o.value} onClick={() => setOutcome(o.value)}>
              {o.label}
            </ChipPill>
          ))}
        </div>
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

      <div className="flex flex-col cohab-desktop:flex-row cohab-desktop:items-center gap-3">
        <Button
          onClick={() => mutation.mutate()}
          disabled={!outcome || mutation.isPending}
          className="w-full cohab-desktop:w-auto"
        >
          Submit
        </Button>
        <button
          type="button"
          onClick={onClose}
          className="hidden cohab-desktop:inline text-[13px] font-medium text-cohab-muted cursor-pointer hover:underline"
        >
          Ask me at 90 days instead
        </button>
        <button
          type="button"
          onClick={onClose}
          className="cohab-desktop:hidden text-[14px] font-medium text-cohab-muted-mobile cursor-pointer text-center"
        >
          Remind me later
        </button>
      </div>
      <p className="cohab-desktop:hidden text-[12px] leading-[1.5] text-cohab-subtle-mobile text-center mt-2.5">
        We'll ask once more at 90 days, then stop.
      </p>
    </Dialog>
  )
}
