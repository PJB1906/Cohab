import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { matchesApi, type RejectionReason } from '@/api/matches'
import { OptionPill } from '@/components/OptionPill'
import { ApiError } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import type { MatchListItem } from '@/api/types'

const REASONS: [RejectionReason, string][] = [
  ['lifestyle', 'Lifestyle'],
  ['schedule', 'Schedule'],
  ['budget', 'Budget'],
  ['location', 'Location'],
  ['found_elsewhere', 'Found a place'],
  ['not_interested', 'Not for me'],
  ['safety', 'Felt unsafe'],
  ['other', 'Other'],
]

/** PRD §8.2's "Viewed -> Rejected: dismisses" / "Chatting -> Rejected: either
 * withdraws" — confirmed before firing, same reasoning as BlockConfirmDialog:
 * a one-sided action the other person won't see coming (unlike blocking,
 * this doesn't prevent a future match, but it does end the current one). */
export function RejectConfirmDialog({
  matchId,
  candidateId,
  candidateName,
  onClose,
}: {
  matchId: string
  candidateId: string
  candidateName: string
  onClose: () => void
}) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [reason, setReason] = useState<RejectionReason | null>(null)

  const mutation = useMutation({
    mutationFn: () => matchesApi.reject(matchId, reason ?? undefined),
    onSuccess: () => {
      queryClient.setQueryData<MatchListItem[]>(['matches'], (prev) =>
        prev?.filter((m) => m.candidate_id !== candidateId),
      )
      queryClient.invalidateQueries({ queryKey: ['matches'] })
      navigate('/matches')
    },
  })

  return (
    <Dialog
      open
      onClose={onClose}
      title={`Not going ahead with ${candidateName}?`}
      className="cohab-desktop:max-w-[440px]"
    >
      <p className="text-[14px] cohab-desktop:text-[13.5px] leading-[1.55] text-cohab-muted mb-4">
        This ends the match for both of you. Any conversation stays visible, but neither of you
        can pick this back up from here.
      </p>
      <p className="text-[12.5px] font-medium text-cohab-ink mb-2">Why? (optional, never shown to them)</p>
      <div className="flex flex-wrap gap-2 mb-6">
        {REASONS.map(([value, label]) => (
          <OptionPill
            key={value}
            selected={reason === value}
            onClick={() => setReason(reason === value ? null : value)}
            className="w-auto min-h-9 px-3 py-2 text-[13px]"
          >
            {label}
          </OptionPill>
        ))}
      </div>
      {mutation.isError && (
        <p className="text-[13px] text-cohab-accent mb-3">
          {mutation.error instanceof ApiError ? mutation.error.message : 'Could not update this match.'}
        </p>
      )}
      <div className="flex flex-col gap-2.5">
        <Button variant="secondary" onClick={onClose} className="w-full">
          Keep the match
        </Button>
        <Button
          variant="danger"
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          className="w-full"
        >
          Not going ahead
        </Button>
      </div>
    </Dialog>
  )
}
