import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { safetyApi } from '@/api/safety'
import { ApiError } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { OptionPill } from '@/components/OptionPill'
import { REASON_OPTIONS } from './copy'
import type { MatchListItem, ReportReason } from '@/api/types'

/** PRD §9 screen 11 ("Reason, details, submit"). A modal rather than its
 * own route — reachable from match detail and chat, and reporting
 * shouldn't cost the user their place in either flow. */
export function ReportDialog({
  reportedUserId,
  reportedUserName,
  onClose,
}: {
  reportedUserId: string
  reportedUserName: string
  onClose: () => void
}) {
  const [reason, setReason] = useState<ReportReason | null>(null)
  const [details, setDetails] = useState('')
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: () =>
      safetyApi.fileReport({
        reported_user_id: reportedUserId,
        reason: reason as ReportReason,
        details: details.trim() || null,
      }),
    onSuccess: (report) => {
      // An escalating reason (PRD §8.3) suspends the reported user
      // immediately, server-side — same class of stale-cache gap as
      // blocking (BlockConfirmDialog.tsx): without this, a suspended
      // account that's no longer eligible would still render from the
      // cached match list until the next natural refetch. `escalated` is
      // certain, not a guess — the backend only ever sets it when it's
      // actually suspended them.
      if (report.escalated) {
        queryClient.setQueryData<MatchListItem[]>(['matches'], (prev) =>
          prev?.filter((m) => m.candidate_id !== reportedUserId),
        )
        queryClient.invalidateQueries({ queryKey: ['matches'] })
      }
    },
  })

  if (mutation.isSuccess) {
    return (
      <div className="fixed inset-0 bg-black/40 flex items-end sm:items-center justify-center p-4 z-50">
        <div className="bg-white rounded-2xl p-6 max-w-sm w-full">
          <h2 className="text-base font-semibold mb-2">Report submitted</h2>
          <p className="text-[13.5px] text-cohab-muted mb-5">
            A moderator will review this. Thank you for flagging it.
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
        <h2 className="text-base font-semibold mb-1">Report {reportedUserName}</h2>
        <p className="text-[13px] text-cohab-muted mb-4">
          A moderator will review this. {reportedUserName} won't be told who reported them.
        </p>

        <div className="flex flex-col gap-2 mb-4">
          {REASON_OPTIONS.map((r) => (
            <OptionPill key={r.value} selected={reason === r.value} onClick={() => setReason(r.value)}>
              {r.label}
            </OptionPill>
          ))}
        </div>

        <Textarea
          placeholder="Anything else that would help a moderator understand? (optional)"
          rows={3}
          value={details}
          onChange={(e) => setDetails(e.target.value)}
          className="mb-4"
        />

        {mutation.isError && (
          <p className="text-[13px] text-cohab-accent mb-3">
            {mutation.error instanceof ApiError ? mutation.error.message : 'Could not submit this report.'}
          </p>
        )}

        <div className="flex flex-col gap-2">
          <Button onClick={() => mutation.mutate()} disabled={!reason || mutation.isPending} className="w-full">
            Submit report
          </Button>
          <Button variant="secondary" onClick={onClose} className="w-full">
            Cancel
          </Button>
        </div>
      </div>
    </div>
  )
}
