import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { matchesApi } from '@/api/matches'
import { ApiError } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import type { MatchListItem } from '@/api/types'

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

  const mutation = useMutation({
    mutationFn: () => matchesApi.reject(matchId),
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
      <p className="text-[14px] cohab-desktop:text-[13.5px] leading-[1.55] text-cohab-muted mb-6">
        This ends the match for both of you. Any conversation stays visible, but neither of you
        can pick this back up from here.
      </p>
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
