import { useMemo } from 'react'
import { REASON_LABELS } from '@/features/safety/copy'
import { cn } from '@/lib/utils'
import type { ReportSummaryOut } from '@/api/types'

/** Pilot SLA target, in hours (docs/DECISIONS.md D-13.4).
 *
 * PROPOSED — no document fixes this. PRD §8.3 requires a moderator review
 * step but states no turnaround time, so this is a working default chosen to
 * make the queue's ageing legible, not a specified figure. The mockup's own
 * header prints "SLA 24h" beside a case, which is where the number comes
 * from; treat it as a placeholder to confirm before a real pilot. */
const SLA_HOURS = 24

const CLOSED_STATUSES = new Set(['substantiated', 'dismissed', 'action_taken'])

function hoursSince(iso: string): number {
  return (Date.now() - new Date(iso).getTime()) / 3_600_000
}

function StatTile({
  label,
  value,
  tone = 'neutral',
}: {
  label: string
  value: string | number
  tone?: 'neutral' | 'accent' | 'critical'
}) {
  return (
    <div className="bg-cohab-tint rounded-lg px-3.5 py-3">
      <div
        className={cn(
          'text-[26px] leading-none font-semibold tabular-nums',
          tone === 'critical' && 'text-cohab-accent',
          tone === 'accent' && 'text-cohab-primary',
          tone === 'neutral' && 'text-cohab-ink',
        )}
      >
        {value}
      </div>
      <div className="text-[11px] leading-[1.35] text-cohab-subtle mt-1.5">{label}</div>
    </div>
  )
}

/** Horizontal proportion bar. Deliberately not a chart library — one bar per
 * reason, width proportional to share, so the shape of the queue reads at a
 * glance without another dependency in the bundle. */
function ReasonBar({ label, count, total }: { label: string; count: number; total: number }) {
  const pct = total === 0 ? 0 : Math.round((count / total) * 100)
  return (
    <div className="flex items-center gap-3">
      <span className="w-[128px] flex-none text-[12.5px] text-cohab-muted truncate">{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-cohab-border-soft overflow-hidden">
        <div className="h-full rounded-full bg-cohab-primary" style={{ width: `${pct}%` }} />
      </div>
      <span className="w-7 flex-none text-right text-[12px] tabular-nums text-cohab-subtle">
        {count}
      </span>
    </div>
  )
}

/** The operator summary beside the queue table.
 *
 * Every figure here is derived from the same `GET /moderation/reports`
 * payload the table already renders — no extra endpoint, no second query,
 * and nothing displayed that the API does not actually return. It exists
 * because the queue screen answers "what is in the list", and a moderator's
 * real question is "what needs me first".
 */
export function TriageRail({ reports }: { reports: ReportSummaryOut[] }) {
  const stats = useMemo(() => {
    const live = reports.filter((r) => !CLOSED_STATUSES.has(r.status))
    const escalated = live.filter((r) => r.escalated)
    const breaching = live.filter((r) => hoursSince(r.created_at) > SLA_HOURS)
    const unclaimed = live.filter((r) => r.status === 'open')

    const oldest = live.reduce<number>((max, r) => Math.max(max, hoursSince(r.created_at)), 0)

    const byReason = new Map<string, number>()
    for (const r of live) byReason.set(r.reason, (byReason.get(r.reason) ?? 0) + 1)
    const reasons = [...byReason.entries()].sort((a, b) => b[1] - a[1])

    return { live, escalated, breaching, unclaimed, oldest, reasons }
  }, [reports])

  const { live, escalated, breaching, unclaimed, oldest, reasons } = stats

  return (
    <aside className="flex flex-col gap-4">
      <section className="surface rounded-[22px] p-5">
        <h2 className="text-[15px] font-semibold mb-1">Triage</h2>
        <p className="text-[12.5px] leading-[1.45] text-cohab-subtle mb-4">
          Counts cover open, under-review and escalated cases. Closed cases are excluded.
        </p>

        <div className="grid grid-cols-2 gap-2.5">
          <StatTile label="Awaiting a moderator" value={unclaimed.length} tone="accent" />
          <StatTile
            label="Escalated"
            value={escalated.length}
            tone={escalated.length > 0 ? 'critical' : 'neutral'}
          />
          <StatTile
            label={`Past ${SLA_HOURS}h target`}
            value={breaching.length}
            tone={breaching.length > 0 ? 'critical' : 'neutral'}
          />
          <StatTile
            label="Oldest open case"
            value={oldest >= 24 ? `${Math.floor(oldest / 24)}d` : `${Math.floor(oldest)}h`}
          />
        </div>
      </section>

      <section className="surface rounded-[22px] p-5">
        <h2 className="text-[15px] font-semibold mb-1">Why people are reporting</h2>
        <p className="text-[12.5px] leading-[1.45] text-cohab-subtle mb-4">
          {live.length === 0
            ? 'Nothing in the queue right now.'
            : `Across ${live.length} live ${live.length === 1 ? 'case' : 'cases'}.`}
        </p>
        <div className="flex flex-col gap-2.5">
          {reasons.map(([reason, count]) => (
            <ReasonBar
              key={reason}
              label={REASON_LABELS[reason] ?? reason}
              count={count}
              total={live.length}
            />
          ))}
        </div>
      </section>

      <section className="surface rounded-[22px] p-5">
        <h2 className="text-[15px] font-semibold mb-2.5">House rules</h2>
        <ul className="flex flex-col gap-2 text-[12.5px] leading-[1.5] text-cohab-muted">
          <li>Threats and harassment escalate immediately — they do not wait in the queue.</li>
          <li>Three independent reports against one account trigger a temporary suspension.</li>
          <li>Repeat reports by the same person collapse into a single case.</li>
          <li>Finding and sanction are recorded separately, both against your moderator ID.</li>
        </ul>
      </section>
    </aside>
  )
}
