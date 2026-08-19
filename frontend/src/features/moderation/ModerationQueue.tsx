import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { moderationApi } from '@/api/moderation'
import { AppShell } from '@/components/AppShell'
import { Badge } from '@/components/ui/badge'
import { REASON_LABELS, STATUS_LABELS } from '@/features/safety/copy'
import type { ReportSummaryOut } from '@/api/types'

const _ACTIVE_STATUSES = new Set(['open', 'under_review'])

/** PRD §9 screen 13: "Open reports, evidence, decision, action." Split into
 * Needs attention / Resolved rather than a single flat list or a status
 * dropdown — a moderator's actual question on opening this screen is "what
 * do I still need to act on", not "show me everything". */
export function ModerationQueue() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['moderation', 'reports'],
    queryFn: () => moderationApi.listReports(),
  })

  const active = data?.filter((r) => _ACTIVE_STATUSES.has(r.status)) ?? []
  const resolved = data?.filter((r) => !_ACTIVE_STATUSES.has(r.status)) ?? []

  return (
    <AppShell>
      <div className="max-w-2xl mx-auto px-4 py-7">
        <h1 className="text-2xl font-semibold tracking-tight mb-1">Moderation queue</h1>
        <p className="text-[13.5px] text-cohab-muted mb-6">
          Reports filed by members, newest first.
        </p>

        {isLoading && <p className="text-cohab-muted">Loading…</p>}
        {error && <p className="text-cohab-accent">Couldn't load the queue.</p>}

        {data && (
          <>
            <h2 className="text-sm font-semibold text-cohab-muted mb-2">
              Needs attention ({active.length})
            </h2>
            {active.length === 0 ? (
              <p className="text-[13.5px] text-cohab-subtle mb-8">Nothing open right now.</p>
            ) : (
              <div className="flex flex-col gap-2 mb-8">
                {active.map((r) => (
                  <ReportRow key={r.id} report={r} />
                ))}
              </div>
            )}

            {resolved.length > 0 && (
              <>
                <h2 className="text-sm font-semibold text-cohab-muted mb-2">Resolved</h2>
                <div className="flex flex-col gap-2">
                  {resolved.map((r) => (
                    <ReportRow key={r.id} report={r} />
                  ))}
                </div>
              </>
            )}
          </>
        )}
      </div>
    </AppShell>
  )
}

function ReportRow({ report }: { report: ReportSummaryOut }) {
  return (
    <Link
      to={`/moderation/reports/${report.id}`}
      className="block bg-white border border-cohab-border rounded-2xl p-4 hover:border-cohab-primary transition-colors"
    >
      <div className="flex items-center justify-between gap-2">
        <p className="text-[14.5px] font-medium text-cohab-ink truncate">
          {report.reporter_name} → {report.reported_user_name}
        </p>
        <Badge variant={_ACTIVE_STATUSES.has(report.status) ? 'divergence' : 'neutral'} className="flex-none">
          {STATUS_LABELS[report.status] ?? report.status}
        </Badge>
      </div>
      <p className="text-[13px] text-cohab-muted mt-1">
        {REASON_LABELS[report.reason] ?? report.reason}
        {report.escalated && <span className="text-cohab-accent font-medium"> · Escalated</span>}
      </p>
      <p className="text-[11.5px] text-cohab-subtle mt-1">{new Date(report.created_at).toLocaleString()}</p>
    </Link>
  )
}
