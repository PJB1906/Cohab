import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { safetyApi } from '@/api/safety'
import { ApiError } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { OptionRadio } from '@/components/OptionRadio'
import { Dialog } from '@/components/ui/dialog'
import { REASON_OPTIONS, STATUS_LABELS } from './copy'
import type { MatchListItem, ReportReason } from '@/api/types'

/** PRD §9 screen 11 ("Reason, details, submit"). A modal rather than its
 * own route — reachable from match detail and chat, and reporting
 * shouldn't cost the user their place in either flow.
 *
 * The mockups render the reason list with a two-line label+description
 * (`{{ r.label }}` / `{{ r.sub }}`), but the description text itself is
 * template pseudocode with no literal copy in either source — there is
 * nothing real to transcribe, so this renders single-line `OptionRadio`
 * entries (label only) rather than inventing descriptions. */
export function ReportDialog({
  reportedUserId,
  reportedUserName,
  onClose,
  onBlockRequested,
}: {
  reportedUserId: string
  reportedUserName: string
  onClose: () => void
  /** Mockup fidelity: both mockups offer blocking right after filing a
   * report (Desktop: inline checkbox; Prototype: a post-submit offer) —
   * the built app had Report/Block as two disconnected menu actions.
   * Optional so this dialog stays usable standalone. docs/DECISIONS.md
   * D-10.5 — block stays a post-submit offer here (`fileReport` has no
   * block parameter to bind an inline checkbox to). */
  onBlockRequested?: () => void
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

  const resetForAnother = () => {
    mutation.reset()
    setReason(null)
    setDetails('')
  }

  if (mutation.isSuccess) {
    const report = mutation.data
    const ref = report.id.slice(0, 8).toUpperCase()
    return (
      <Dialog
        open
        onClose={onClose}
        className="rounded-none h-screen max-h-screen cohab-desktop:h-auto cohab-desktop:max-h-[85vh] cohab-desktop:rounded-2xl cohab-desktop:max-w-[520px]"
      >
        <div className="flex flex-col items-center text-center cohab-desktop:hidden pt-6">
          <div className="w-[52px] h-[52px] rounded-full bg-cohab-tint text-cohab-primary text-[22px] font-semibold flex items-center justify-center mb-5">
            ✓
          </div>
          <h2 className="text-[21px] font-semibold text-cohab-ink mb-2.5">Report submitted</h2>
          <p className="text-[14.5px] leading-[1.55] text-cohab-muted-mobile mb-6 text-pretty">
            Reference {ref}. A moderator will review it within 24 hours and you'll be told the
            outcome by email.
          </p>
          {onBlockRequested && (
            <div className="w-full border border-cohab-border-soft rounded-2xl p-[15px] mb-5 text-left">
              <p className="text-[13.5px] font-semibold text-cohab-ink mb-1.5">While we review</p>
              <p className="text-[13.5px] leading-[1.5] text-cohab-muted-mobile">
                You can block {reportedUserName} now if you'd rather not hear from them. Blocking
                hides the thread and removes you from each other's matches.
              </p>
            </div>
          )}
          {onBlockRequested ? (
            <Button onClick={onBlockRequested} className="w-full mb-4">
              Block {reportedUserName} and go back
            </Button>
          ) : (
            <Button onClick={onClose} className="w-full mb-4">
              Back to matches
            </Button>
          )}
          <button
            type="button"
            onClick={onClose}
            className="text-[14px] font-medium text-cohab-muted-mobile cursor-pointer"
          >
            {onBlockRequested ? 'Just go back' : 'File another report'}
          </button>
        </div>

        <div className="hidden cohab-desktop:block">
          <span className="block font-mono text-[10px] uppercase tracking-[.08em] text-cohab-primary mb-3.5">
            Report {ref} · {STATUS_LABELS[report.status] ?? report.status}
          </span>
          <h1 className="text-[24px] font-semibold leading-[1.2] tracking-[-.015em] text-cohab-ink mb-2.5">
            Thanks — a moderator has it
          </h1>
          <p className="text-[14.5px] leading-[1.55] text-cohab-muted mb-6">
            You will hear the outcome by email within 24 hours, whether or not action is taken.{' '}
            {reportedUserName} is not told who filed the report.
          </p>
          <div className="flex gap-3">
            <Button onClick={onClose}>Back to matches</Button>
            <Button variant="secondary" onClick={resetForAnother}>
              File another report
            </Button>
          </div>
        </div>
      </Dialog>
    )
  }

  return (
    <Dialog
      open
      onClose={onClose}
      className="rounded-none h-screen max-h-screen cohab-desktop:h-auto cohab-desktop:max-h-[85vh] cohab-desktop:rounded-2xl cohab-desktop:max-w-[680px]"
    >
      <button
        type="button"
        onClick={onClose}
        className="block text-[13px] font-medium text-cohab-primary mb-5 cursor-pointer"
      >
        ← Cancel
      </button>
      <h1 className="text-[22px] cohab-desktop:text-[26px] font-semibold leading-[1.18] tracking-[-.015em] text-cohab-ink mb-2">
        Report {reportedUserName}
      </h1>
      <p className="text-[14px] cohab-desktop:text-[14.5px] leading-[1.55] text-cohab-muted mb-6 text-pretty">
        A moderator reviews every report before any action is taken. {reportedUserName}'s account
        is not suspended while a report is open, except for threats or harassment, which escalate
        immediately.
      </p>

      <div className="cohab-desktop:bg-cohab-card cohab-desktop:border cohab-desktop:border-cohab-border cohab-desktop:rounded-2xl cohab-desktop:p-6 mb-4">
        <h2 className="hidden cohab-desktop:block text-[17px] font-semibold text-cohab-ink mb-3.5">
          What happened?
        </h2>
        <div className="flex flex-col gap-2">
          {REASON_OPTIONS.map((r) => (
            <OptionRadio key={r.value} selected={reason === r.value} onClick={() => setReason(r.value)}>
              {r.label}
            </OptionRadio>
          ))}
        </div>
      </div>

      <div className="cohab-desktop:bg-cohab-card cohab-desktop:border cohab-desktop:border-cohab-border cohab-desktop:rounded-2xl cohab-desktop:p-6 mb-5">
        <h2 className="text-[15px] cohab-desktop:text-[17px] font-semibold text-cohab-ink mb-1.5">
          Details{' '}
          <span className="cohab-desktop:hidden font-normal text-[13px] text-cohab-subtle-mobile">
            — optional but useful
          </span>
        </h2>
        <p className="hidden cohab-desktop:block text-[13px] leading-[1.45] text-cohab-muted mb-3.5">
          Dates and what was said help.
        </p>
        <Textarea
          placeholder="What happened, and when? Anything a moderator should look at."
          rows={4}
          value={details}
          onChange={(e) => setDetails(e.target.value)}
        />
      </div>

      {mutation.isError && (
        <p className="text-[13px] text-cohab-accent mb-3">
          {mutation.error instanceof ApiError ? mutation.error.message : 'Could not submit this report.'}
        </p>
      )}

      <div className="flex flex-col cohab-desktop:flex-row cohab-desktop:items-center gap-3">
        <Button
          variant="destructive"
          onClick={() => mutation.mutate()}
          disabled={!reason || mutation.isPending}
          className="w-full cohab-desktop:w-auto"
        >
          Submit report
        </Button>
        <span className="text-[12.5px] text-cohab-subtle text-center cohab-desktop:text-left">
          Reviewed within 24 hours.
        </span>
      </div>

      {onBlockRequested && (
        <button
          type="button"
          onClick={onBlockRequested}
          className="block w-full text-center text-[14px] font-medium text-cohab-muted-mobile mt-4 cohab-desktop:hidden cursor-pointer"
        >
          Block instead, without reporting
        </button>
      )}
    </Dialog>
  )
}
