import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { safetyApi } from '@/api/safety'
import { ApiError } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import type { MatchListItem } from '@/api/types'

/** PRD §10: blocking "removes the pair from each other's eligible pool at
 * Stage 1, hides existing threads, and cannot be undone by the blocked
 * party." Confirmed before firing — a one-sided action the other person
 * won't see coming and can't reverse. */
export function BlockConfirmDialog({
  blockedUserId,
  blockedUserName,
  onClose,
}: {
  blockedUserId: string
  blockedUserName: string
  onClose: () => void
}) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: () => safetyApi.block(blockedUserId),
    onSuccess: () => {
      // `invalidateQueries` alone isn't enough: `/matches` isn't mounted
      // yet at this point, so it only guarantees a *background* refetch
      // once it mounts — the first paint still synchronously renders the
      // pre-block cached list, so the person you just blocked flashes back
      // on screen for a frame (found live: real, reproducible, and a bad
      // moment to get wrong given what blocking is for). Stripping them
      // from the cache directly — same pattern MatchDetail.tsx already
      // uses for its interest mutation — makes the very first render
      // correct instead of eventually correct.
      queryClient.setQueryData<MatchListItem[]>(['matches'], (prev) =>
        prev?.filter((m) => m.candidate_id !== blockedUserId),
      )
      queryClient.invalidateQueries({ queryKey: ['matches'] })
      navigate('/matches')
    },
  })

  return (
    <Dialog open onClose={onClose} title={`Block ${blockedUserName}?`} className="cohab-desktop:max-w-[440px]">
      <p className="text-[14px] cohab-desktop:text-[13.5px] leading-[1.55] text-cohab-muted mb-6">
        You won't be matched with each other again, and any existing conversation disappears
        for both of you. {blockedUserName} isn't notified, and can't undo this.
      </p>
      {mutation.isError && (
        <p className="text-[13px] text-cohab-accent mb-3">
          {mutation.error instanceof ApiError ? mutation.error.message : 'Could not block this person.'}
        </p>
      )}
      <div className="flex flex-col gap-2.5">
        <Button variant="secondary" onClick={onClose} className="w-full">
          Cancel
        </Button>
        <Button
          variant="danger"
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          className="w-full"
        >
          Block {blockedUserName}
        </Button>
      </div>
    </Dialog>
  )
}
