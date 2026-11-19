import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { moderationApi } from '@/api/moderation'
import { ApiError } from '@/api/client'
import { Avatar } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { FactsGrid } from '@/components/FactsGrid'
import { Tab } from '@/components/Tab'
import { BackButton } from '@/components/BackButton'
import { useSession } from '@/hooks/useSession'
import { REASON_LABELS, STATUS_LABELS } from '@/features/safety/copy'
import { cn } from '@/lib/utils'
import type { ReportDetailOut, ReportSanction, ReportSummaryOut } from '@/api/types'

/** Each chip is one mockup "decision", collapsed onto the API's two-axis
 * finding+sanction shape (docs/COHAB_MATCHING_SPEC.md doesn't cover
 * moderation — this mirrors the state machine in cohab/models/safety.py). */
const DECISIONS: { label: string; finding: 'substantiated' | 'dismissed'; sanction: ReportSanction | null }[] = [
  { label: 'Dismiss — no basis', finding: 'dismissed', sanction: null },
  { label: 'Warn', finding: 'substantiated', sanction: 'warn' },
  { label: 'Suspend', finding: 'substantiated', sanction: 'suspend' },
  { label: 'Ban', finding: 'substantiated', sanction: 'ban' },
  { label: 'Substantiated, no sanction', finding: 'substantiated', sanction: null },
]

function formatAge(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime()
  const hours = Math.floor(ms / 3_600_000)
  if (hours < 1) return '<1h'
  if (hours < 24) return `${hours}h`
  return `${Math.floor(hours / 24)}d`
}

function stateClasses(status: string, escalated: boolean): string {
  if (escalated) return 'border-cohab-accent text-cohab-accent bg-cohab-card'
  if (status === 'substantiated' || status === 'dismissed' || status === 'action_taken')
    return 'border-cohab-border text-cohab-subtle bg-cohab-card'
  return 'border-cohab-primary text-cohab-primary bg-cohab-tint'
}

/** PRD §8.3 state machine, §9 screen 13. Claim -> Resolve (finding +
 * sanction + note) — the same two moderator actions build plan §4 Phase 7
 * scopes for this queue. Right-pane case-detail portion of the mockup's
 * combined queue+detail screen; see ModerationQueue.tsx's header comment
 * for why this stays a separate route. */
export function ReportReview() {
  const { reportId } = useParams<{ reportId: string }>()
  const queryClient = useQueryClient()
  const { data: me } = useSession()

  const { data, isLoading, error } = useQuery({
    queryKey: ['moderation', 'report', reportId],
    queryFn: () => moderationApi.getReport(reportId!),
    enabled: Boolean(reportId),
  })

  const [decisionLabel, setDecisionLabel] = useState<string | null>(null)
  const [note, setNote] = useState('')

  function setReportCache(r: ReportDetailOut) {
    queryClient.setQueryData(['moderation', 'report', reportId], r)
    queryClient.setQueryData<ReportSummaryOut[]>(['moderation', 'reports'], (prev) =>
      prev?.map((row) => (row.id === r.id ? { ...row, status: r.status, escalated: r.escalated } : row)),
    )
    queryClient.invalidateQueries({ queryKey: ['moderation', 'reports'] })
  }

  const claimMutation = useMutation({
    mutationFn: () => moderationApi.claim(reportId!),
    onSuccess: setReportCache,
  })

  const chosen = DECISIONS.find((d) => d.label === decisionLabel) ?? null

  const resolveMutation = useMutation({
    mutationFn: () =>
      moderationApi.resolve(reportId!, {
        finding: chosen!.finding,
        sanction: chosen!.sanction,
        note: note.trim() || null,
      }),
    onSuccess: setReportCache,
  })

  const dark = (
    <header className="bg-cohab-dark-bg/95 backdrop-blur border-b border-cohab-dark-bg">
      <div className="max-w-[1800px] mx-auto px-6 h-[54px] flex items-center gap-[22px]">
        <BackButton pathname="/moderation/reports" />
        <Link
          to="/matches"
          aria-label="Cohab — back to your matches"
          className="font-bold text-base tracking-[-.02em] text-cohab-primary hover:opacity-70 transition-opacity cohab-press"
        >
          Cohab
        </Link>
        <span className="font-mono font-medium text-[9px] tracking-[.08em] uppercase text-cohab-dark-text border border-cohab-dark-border rounded px-[5px] py-[3px]">
          Moderation
        </span>
        <div className="flex-1" />
        <Avatar
          name={me?.full_name ?? '?'}
          src={me?.avatar_url}
          size={26}
          className="bg-cohab-primary text-cohab-on-fill border-none text-[11px]"
        />
      </div>
    </header>
  )

  if (!error && (isLoading || !data)) {
    return (
      <div className="min-h-screen">
        {dark}
        <div className="max-w-[680px] mx-auto px-7 py-10 text-cohab-muted">Loading…</div>
      </div>
    )
  }
  if (error || !data) {
    return (
      <div className="min-h-screen">
        {dark}
        <div className="max-w-[680px] mx-auto px-7 py-10 text-cohab-accent">Couldn't load this report.</div>
      </div>
    )
  }

  const canClaim = data.status === 'open'
  const canResolve = data.status === 'under_review'
  const isResolved = !canClaim && !canResolve

  const actionLog = [
    ...(data.resolved_at
      ? [
          {
            at: new Date(data.resolved_at).toLocaleString(),
            what: `Decision recorded${data.sanction ? ` — ${data.sanction}` : ''}`,
            who: 'Logged with moderator ID, per audit requirements',
          },
        ]
      : []),
    ...(data.escalated
      ? [{ at: '—', what: 'Marked escalated', who: 'Reason qualifies for immediate escalation' }]
      : []),
    {
      at: new Date(data.created_at).toLocaleString(),
      what: 'Report filed',
      who: `By ${data.reporter_name}`,
    },
  ]

  return (
    <div className="min-h-screen">
      {dark}
      <div className="max-w-[680px] mx-auto px-7 py-[22px] pb-[60px]">
        <Link to="/moderation" className="text-[13px] font-medium text-cohab-primary">
          ← Queue
        </Link>

        <div className="bg-cohab-card border border-cohab-border rounded-2xl p-[22px_24px] mt-4">
          <div className="flex items-start gap-3.5 mb-4">
            <div className="flex-1">
              <div className="flex items-center gap-2.5 mb-1">
                <h2 className="text-[19px] font-semibold m-0">{data.reported_user_name}</h2>
                <span
                  className={cn(
                    'rounded-full border px-2.5 py-1 text-[11px] font-medium',
                    stateClasses(data.status, data.escalated),
                  )}
                >
                  {data.escalated ? 'Escalated' : (STATUS_LABELS[data.status] ?? data.status)}
                </span>
              </div>
              <p className="text-[13px] text-cohab-muted m-0">
                {data.id.slice(0, 8)} · {REASON_LABELS[data.reason] ?? data.reason} · filed{' '}
                {formatAge(data.created_at)} ago · SLA 24h
              </p>
            </div>
            {canClaim && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => claimMutation.mutate()}
                disabled={claimMutation.isPending}
                className="flex-none"
              >
                Claim case
              </Button>
            )}
          </div>
          {claimMutation.isError && (
            <p className="text-[13px] text-cohab-accent mb-3">
              {claimMutation.error instanceof ApiError ? claimMutation.error.message : 'Could not claim this report.'}
            </p>
          )}

          <FactsGrid
            columns={3}
            items={[
              { label: 'Case', value: data.id.slice(0, 8) },
              { label: 'Reason', value: REASON_LABELS[data.reason] ?? data.reason },
              { label: 'Filed', value: new Date(data.created_at).toLocaleDateString() },
              { label: 'Reporter', value: data.reporter_name },
              { label: 'Evidence', value: `${data.evidence.length} flagged` },
              { label: 'Escalated', value: data.escalated ? 'Yes' : 'No' },
            ]}
          />
        </div>

        <div className="bg-cohab-card border border-cohab-border rounded-2xl p-[22px_24px] mt-4">
          <h3 className="text-[17px] font-semibold m-0 mb-1">Evidence</h3>
          <p className="text-[13px] text-cohab-muted m-0 mb-4">
            Only {data.reported_user_name}'s messages that were auto-flagged — not the full thread.
          </p>
          {data.evidence.length === 0 && (
            <p className="text-[13.5px] text-cohab-subtle">No flagged messages from this account.</p>
          )}
          <div className="flex flex-col gap-2.5">
            {data.evidence.map((m) => (
              <div key={m.id} className="border border-cohab-accent rounded-xl px-[15px] py-[13px] bg-cohab-card">
                <div className="flex items-baseline justify-between gap-2.5 mb-1">
                  <span className="font-semibold text-[12.5px]">{data.reported_user_name}</span>
                  <span className="font-mono text-[11.5px] text-cohab-subtle">
                    {new Date(m.created_at).toLocaleString()}
                  </span>
                </div>
                <p className="text-[13.5px] text-cohab-ink m-0">{m.body}</p>
                <span className="inline-block mt-[9px] font-mono font-medium text-[10.5px] tracking-[.05em] uppercase text-cohab-accent">
                  Auto-flagged
                </span>
              </div>
            ))}
          </div>
        </div>

        {canResolve && (
          <div className="bg-cohab-card border border-cohab-border rounded-2xl p-[22px_24px] mt-4">
            <h3 className="text-[17px] font-semibold m-0 mb-1">Decision</h3>
            <p className="text-[13px] text-cohab-muted m-0 mb-4">
              Finding and sanction are recorded separately. Both are written to the audit log with your
              moderator ID.
            </p>
            <div className="flex flex-wrap gap-2.5 mb-4">
              {DECISIONS.map((d) => (
                <Tab key={d.label} selected={decisionLabel === d.label} onClick={() => setDecisionLabel(d.label)}>
                  {d.label}
                </Tab>
              ))}
            </div>
            <Textarea
              placeholder="Reasoning shown to neither party, retained for audit…"
              rows={3}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              className="min-h-[74px] mb-3.5"
            />
            {resolveMutation.isError && (
              <p className="text-[13px] text-cohab-accent mb-3">
                {resolveMutation.error instanceof ApiError
                  ? resolveMutation.error.message
                  : 'Could not resolve this report.'}
              </p>
            )}
            <div className="flex items-center gap-3 flex-wrap">
              <Button
                onClick={() => resolveMutation.mutate()}
                disabled={!chosen || resolveMutation.isPending}
                size="sm"
              >
                Record decision
              </Button>
              <button
                type="button"
                disabled
                title="Escalation is applied automatically from the report reason at filing time — there is no separate moderator action for it in this build."
                className="bg-cohab-card text-cohab-accent border border-cohab-accent rounded-xl px-5 py-2.5 text-[13.5px] font-semibold opacity-50 cursor-not-allowed"
              >
                Escalate
              </button>
              <span className="text-xs text-cohab-subtle">
                {decisionLabel ? 'Reporter is notified either way.' : 'Choose a finding first.'}
              </span>
            </div>
          </div>
        )}

        {isResolved && (
          <div className="bg-cohab-card border border-cohab-border rounded-2xl p-[22px_24px] mt-4">
            <h3 className="text-[17px] font-semibold m-0 mb-3">Decision</h3>
            {data.sanction && (
              <p className="text-[13.5px] text-cohab-ink mb-2">
                Sanction: <span className="font-semibold capitalize">{data.sanction}</span>
              </p>
            )}
            {data.resolution_note && (
              <p className="text-[13.5px] text-cohab-muted bg-cohab-row-tint rounded-xl px-3.5 py-3">
                {data.resolution_note}
              </p>
            )}
            {data.resolved_at && (
              <p className="text-xs text-cohab-subtle mt-3">
                Resolved {new Date(data.resolved_at).toLocaleString()}
              </p>
            )}
          </div>
        )}

        <div className="bg-cohab-card border border-cohab-border rounded-2xl p-[22px_24px] mt-4">
          <h3 className="text-[17px] font-semibold m-0 mb-3.5">Action log</h3>
          <div className="flex flex-col">
            {actionLog.map((l, i) => (
              <div key={i} className="grid grid-cols-[128px_1fr] gap-3.5 py-2.5 border-t border-cohab-border-soft">
                <span className="font-mono text-[11.5px] text-cohab-subtle">{l.at}</span>
                <div>
                  <span className="font-semibold text-[13px] block">{l.what}</span>
                  <span className="text-[12.5px] text-cohab-muted">{l.who}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
