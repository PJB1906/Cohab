import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { moderationApi } from '@/api/moderation'
import { ApiError } from '@/api/client'
import { AppShell } from '@/components/AppShell'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { OptionPill } from '@/components/OptionPill'
import { REASON_LABELS, STATUS_LABELS } from '@/features/safety/copy'
import type { ReportDetailOut, ReportSanction, ReportSummaryOut } from '@/api/types'

const SANCTIONS: { value: ReportSanction; label: string }[] = [
  { value: 'warn', label: 'Warn' },
  { value: 'suspend', label: 'Suspend' },
  { value: 'ban', label: 'Ban' },
]

/** PRD §8.3 state machine, §9 screen 13. Claim -> Resolve (finding +
 * sanction + note) — the same two moderator actions build plan §4 Phase 7
 * scopes for this queue. */
export function ReportReview() {
  const { reportId } = useParams<{ reportId: string }>()
  const queryClient = useQueryClient()

  const { data, isLoading, error } = useQuery({
    queryKey: ['moderation', 'report', reportId],
    queryFn: () => moderationApi.getReport(reportId!),
    enabled: Boolean(reportId),
  })

  const [finding, setFinding] = useState<'substantiated' | 'dismissed' | null>(null)
  const [sanction, setSanction] = useState<ReportSanction | null>(null)
  const [note, setNote] = useState('')

  function setReportCache(r: ReportDetailOut) {
    queryClient.setQueryData(['moderation', 'report', reportId], r)
    // `invalidateQueries` alone isn't enough — see BlockConfirmDialog.tsx's
    // comment for why: `/moderation` may already be mounted (came here via
    // back button) with `staleTime` still fresh, so its first paint would
    // synchronously show the pre-claim/pre-resolve status until the
    // background refetch lands. Patching the list cache directly, the same
    // pattern used throughout safety/matches, makes the first render correct.
    queryClient.setQueryData<ReportSummaryOut[]>(['moderation', 'reports'], (prev) =>
      prev?.map((row) => (row.id === r.id ? { ...row, status: r.status, escalated: r.escalated } : row)),
    )
    queryClient.invalidateQueries({ queryKey: ['moderation', 'reports'] })
  }

  const claimMutation = useMutation({
    mutationFn: () => moderationApi.claim(reportId!),
    onSuccess: setReportCache,
  })

  const resolveMutation = useMutation({
    mutationFn: () =>
      moderationApi.resolve(reportId!, {
        finding: finding as 'substantiated' | 'dismissed',
        sanction: finding === 'substantiated' ? sanction : null,
        note: note.trim() || null,
      }),
    onSuccess: setReportCache,
  })

  if (isLoading || !data) {
    return (
      <AppShell>
        <div className="max-w-2xl mx-auto px-4 py-10 text-cohab-muted">Loading…</div>
      </AppShell>
    )
  }
  if (error) {
    return (
      <AppShell>
        <div className="max-w-2xl mx-auto px-4 py-10 text-cohab-accent">Couldn't load this report.</div>
      </AppShell>
    )
  }

  const canClaim = data.status === 'open'
  const canResolve = data.status === 'under_review'
  const isResolved = !canClaim && !canResolve

  return (
    <AppShell>
      <div className="max-w-2xl mx-auto px-4 py-7 pb-10">
        <Link to="/moderation" className="text-[13px] font-medium text-cohab-primary">
          ← Queue
        </Link>

        <div className="bg-white border border-cohab-border rounded-2xl p-6 mt-4">
          <div className="flex items-start justify-between gap-2 mb-1">
            <h1 className="text-lg font-semibold">
              {data.reporter_name} reported {data.reported_user_name}
            </h1>
            <Badge variant={isResolved ? 'neutral' : 'divergence'} className="flex-none">
              {STATUS_LABELS[data.status] ?? data.status}
            </Badge>
          </div>
          <p className="text-[13.5px] text-cohab-muted">
            {REASON_LABELS[data.reason] ?? data.reason}
            {data.escalated && <span className="text-cohab-accent font-medium"> · Escalated</span>}
          </p>
          {data.details && (
            <p className="text-[13.5px] text-cohab-ink bg-cohab-bg rounded-xl px-3.5 py-3 mt-3">{data.details}</p>
          )}
          <p className="text-[11.5px] text-cohab-subtle mt-3">
            Filed {new Date(data.created_at).toLocaleString()}
          </p>
        </div>

        <div className="bg-white border border-cohab-border rounded-2xl p-6 mt-4">
          <h2 className="text-base font-semibold mb-1">Flagged messages ({data.evidence.length})</h2>
          <p className="text-[13px] text-cohab-muted mb-4">
            Only {data.reported_user_name}'s messages that were auto-flagged — not the full thread.
          </p>
          {data.evidence.length === 0 && (
            <p className="text-[13.5px] text-cohab-subtle">No flagged messages from this account.</p>
          )}
          <div className="flex flex-col gap-2">
            {data.evidence.map((m) => (
              <div key={m.id} className="bg-cohab-bg rounded-xl px-3.5 py-3">
                <p className="text-[13.5px] text-cohab-ink">{m.body}</p>
                <p className="text-[11px] text-cohab-subtle mt-1">{new Date(m.created_at).toLocaleString()}</p>
              </div>
            ))}
          </div>
        </div>

        {canClaim && (
          <div className="bg-white border border-cohab-border rounded-2xl p-6 mt-4">
            <p className="text-[13.5px] text-cohab-muted mb-4">
              Claim this report to start reviewing it — PRD §8.3's SLA is 24 hours from filing.
            </p>
            {claimMutation.isError && (
              <p className="text-[13px] text-cohab-accent mb-3">
                {claimMutation.error instanceof ApiError ? claimMutation.error.message : 'Could not claim this report.'}
              </p>
            )}
            <Button onClick={() => claimMutation.mutate()} disabled={claimMutation.isPending} className="w-full">
              Claim report
            </Button>
          </div>
        )}

        {canResolve && (
          <div className="bg-white border border-cohab-border rounded-2xl p-6 mt-4">
            <h2 className="text-base font-semibold mb-3">Resolve</h2>
            <div className="flex flex-col gap-2 mb-4">
              <OptionPill selected={finding === 'substantiated'} onClick={() => setFinding('substantiated')}>
                Substantiated — there's a basis for this report
              </OptionPill>
              <OptionPill selected={finding === 'dismissed'} onClick={() => setFinding('dismissed')}>
                Dismissed — no basis
              </OptionPill>
            </div>

            {finding === 'substantiated' && (
              <div className="mb-4">
                <p className="text-xs font-semibold text-cohab-ink/80 mb-1.5">Sanction</p>
                <div className="flex gap-2">
                  {SANCTIONS.map((s) => (
                    <OptionPill
                      key={s.value}
                      selected={sanction === s.value}
                      onClick={() => setSanction(s.value)}
                      className="w-auto flex-1 text-center"
                    >
                      {s.label}
                    </OptionPill>
                  ))}
                </div>
              </div>
            )}

            <Textarea
              placeholder="Notes for the record (optional)"
              rows={3}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              className="mb-4"
            />

            {resolveMutation.isError && (
              <p className="text-[13px] text-cohab-accent mb-3">
                {resolveMutation.error instanceof ApiError
                  ? resolveMutation.error.message
                  : 'Could not resolve this report.'}
              </p>
            )}

            <Button
              onClick={() => resolveMutation.mutate()}
              disabled={!finding || (finding === 'substantiated' && !sanction) || resolveMutation.isPending}
              className="w-full"
            >
              Submit decision
            </Button>
          </div>
        )}

        {isResolved && (
          <div className="bg-white border border-cohab-border rounded-2xl p-6 mt-4">
            <h2 className="text-base font-semibold mb-2">Decision</h2>
            {data.sanction && (
              <p className="text-[13.5px] text-cohab-ink mb-2">
                Sanction: <span className="font-semibold capitalize">{data.sanction}</span>
              </p>
            )}
            {data.resolution_note && (
              <p className="text-[13.5px] text-cohab-muted bg-cohab-bg rounded-xl px-3.5 py-3">
                {data.resolution_note}
              </p>
            )}
            {data.resolved_at && (
              <p className="text-[11.5px] text-cohab-subtle mt-3">
                Resolved {new Date(data.resolved_at).toLocaleString()}
              </p>
            )}
          </div>
        )}
      </div>
    </AppShell>
  )
}
