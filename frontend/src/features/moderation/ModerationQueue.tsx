import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { moderationApi } from '@/api/moderation'
import { Avatar } from '@/components/ui/avatar'
import { Input } from '@/components/ui/input'
import { Tab } from '@/components/Tab'
import { BackButton } from '@/components/BackButton'
import { useSession } from '@/hooks/useSession'
import { REASON_LABELS, STATUS_LABELS } from '@/features/safety/copy'
import { TriageRail } from './TriageRail'
import { cn } from '@/lib/utils'
import type { ReportSummaryOut } from '@/api/types'

const QUEUE_COLS = 'grid-cols-[88px_minmax(180px,1.3fr)_minmax(140px,1fr)_106px_74px]'

const FILTERS = ['Open', 'Under review', 'Escalated', 'Closed'] as const
type FilterLabel = (typeof FILTERS)[number]

const CLOSED_STATUSES = new Set(['substantiated', 'dismissed', 'action_taken'])

function matchesFilter(r: ReportSummaryOut, filter: FilterLabel): boolean {
  if (filter === 'Open') return r.status === 'open'
  if (filter === 'Under review') return r.status === 'under_review'
  // Escalation is monotonic (docs/DECISIONS.md D-7.2) — a case keeps
  // `escalated=true` even once resolved, so this tab has to exclude closed
  // statuses itself or a dismissed/actioned case never leaves it.
  if (filter === 'Escalated') return r.escalated && !CLOSED_STATUSES.has(r.status)
  return CLOSED_STATUSES.has(r.status)
}

/** No relative-time helper exists elsewhere in the codebase — kept local
 * and matched to the mockup's compact "4h" / "1d" / "5d" age format. */
function formatAge(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime()
  const hours = Math.floor(ms / 3_600_000)
  if (hours < 1) return '<1h'
  if (hours < 24) return `${hours}h`
  return `${Math.floor(hours / 24)}d`
}

function stateClasses(status: string, escalated: boolean): string {
  if (escalated) return 'border-cohab-accent text-cohab-accent bg-cohab-card'
  if (CLOSED_STATUSES.has(status)) return 'border-cohab-border text-cohab-subtle bg-cohab-card'
  return 'border-cohab-primary text-cohab-primary bg-cohab-tint'
}

/** PRD §9 screen 13: "Open reports, evidence, decision, action." The
 * mockup renders queue (this screen) and case detail (ReportReview) as one
 * two-pane view, but this app routes them separately — see DECISIONS.md for
 * why this pass kept the two-route split rather than merging them. This
 * screen restyles just the left pane: dark moderation app bar + report
 * queue table, matching the mockup's own dark shell rather than the light
 * AppShell every other screen uses. */
export function ModerationQueue() {
  const { data: me } = useSession()
  const { data, isLoading, error } = useQuery({
    queryKey: ['moderation', 'reports'],
    queryFn: () => moderationApi.listReports(),
  })

  const [filter, setFilter] = useState<FilterLabel>('Open')
  const [search, setSearch] = useState('')

  const openCount = data?.filter((r) => r.status === 'open').length ?? 0
  const underReviewCount = data?.filter((r) => r.status === 'under_review').length ?? 0
  const escalatedCount = data?.filter((r) => r.escalated && !CLOSED_STATUSES.has(r.status)).length ?? 0

  const rows = useMemo(() => {
    if (!data) return []
    const q = search.trim().toLowerCase()
    return data
      .filter((r) => matchesFilter(r, filter))
      .filter(
        (r) =>
          !q ||
          r.reporter_name.toLowerCase().includes(q) ||
          r.reported_user_name.toLowerCase().includes(q) ||
          r.id.toLowerCase().includes(q) ||
          (REASON_LABELS[r.reason] ?? r.reason).toLowerCase().includes(q),
      )
  }, [data, filter, search])

  return (
    // No opaque background here (D-13.11): `bg-[#000000]` painted over the
    // fixed ambient canvas, which is why this screen alone had none. The
    // black now comes from `body`, which sits below both.
    <div className="min-h-screen">
      <header className="bg-cohab-dark-bg/95 backdrop-blur border-b border-cohab-dark-bg">
        <div className="max-w-[1800px] mx-auto px-6 h-[54px] flex items-center gap-[22px]">
          <BackButton pathname="/moderation" />
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
          <span className="text-xs text-cohab-dark-text-muted">
            Open {openCount} · Under review {underReviewCount} · Escalated {escalatedCount}
          </span>
          <Avatar
            name={me?.full_name ?? '?'}
            src={me?.avatar_url}
            size={26}
            className="bg-cohab-primary text-cohab-on-fill border-none text-[11px]"
          />
        </div>
      </header>

      {/* Two-pane operator view (docs/DECISIONS.md D-13.4). The queue table
          was `max-w-[900px]` inside an `1800px` container, leaving ~900px of
          dead space at common desktop widths — reported by the user. The rail
          fills it with the summary a moderator actually opens this screen
          for, derived from the same payload the table renders. Collapses to a
          single column below the desktop breakpoint. */}
      <div className="max-w-[1800px] mx-auto px-6 py-[22px] pb-[60px] grid gap-6 items-start grid-cols-1 cohab-desktop:grid-cols-[minmax(0,1fr)_420px]">
        <div className="bg-cohab-card border border-cohab-border rounded-2xl overflow-hidden">
          <div className="px-5 py-4 border-b border-cohab-border flex items-center gap-2.5 flex-wrap">
            <h1 className="poster text-[44px] mr-2">Report queue</h1>
            {FILTERS.map((f) => (
              <Tab key={f} selected={filter === f} onClick={() => setFilter(f)}>
                {f}
              </Tab>
            ))}
            <div className="flex-1" />
            <Input
              placeholder="Search reports, users, IDs"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-[210px] py-2 px-[11px] text-[12.5px]"
            />
          </div>

          <div className="overflow-x-auto">
            <div className="min-w-[630px]">
              <div
                className={cn(
                  'grid gap-2.5 px-5 py-[9px] border-b border-cohab-border bg-cohab-row-tint',
                  QUEUE_COLS,
                )}
              >
                {['Case', 'Subject', 'Reason', 'State', 'Age'].map((c) => (
                  <span
                    key={c}
                    className="font-mono font-medium text-[10px] tracking-[.06em] uppercase text-cohab-subtle"
                  >
                    {c}
                  </span>
                ))}
              </div>

              {isLoading && <p className="px-5 py-6 text-cohab-muted">Loading…</p>}
              {error && <p className="px-5 py-6 text-cohab-accent">Couldn't load the queue.</p>}
              {data && rows.length === 0 && (
                <p className="px-5 py-6 text-[13.5px] text-cohab-subtle">No reports match this filter.</p>
              )}

              {rows.map((r) => (
                <Link
                  key={r.id}
                  to={`/moderation/reports/${r.id}`}
                  className={cn(
                    'grid gap-2.5 items-center px-5 py-[13px] border-b border-cohab-border-soft hover:bg-cohab-row-tint transition-colors',
                    QUEUE_COLS,
                  )}
                >
                  <span className="font-mono font-medium text-[11.5px] text-cohab-ink truncate">
                    {r.id.slice(0, 8)}
                  </span>
                  <div className="min-w-0">
                    <span className="font-semibold text-[13.5px] block truncate">{r.reported_user_name}</span>
                    <span className="text-xs text-cohab-subtle truncate block">
                      Reported by {r.reporter_name}
                    </span>
                  </div>
                  <span className="text-[13px] text-cohab-ink truncate">
                    {REASON_LABELS[r.reason] ?? r.reason}
                  </span>
                  <span
                    className={cn(
                      'justify-self-start rounded-full border px-2.5 py-1 text-[11px] font-medium',
                      stateClasses(r.status, r.escalated),
                    )}
                  >
                    {r.escalated ? 'Escalated' : (STATUS_LABELS[r.status] ?? r.status)}
                  </span>
                  <span className="text-xs text-cohab-subtle text-right">{formatAge(r.created_at)}</span>
                </Link>
              ))}
            </div>
          </div>

          <div className="px-5 py-[13px] border-t border-cohab-border">
            <p className="text-xs leading-relaxed text-cohab-subtle m-0">
              {rows.length} {rows.length === 1 ? 'case' : 'cases'} shown
              {search.trim() ? ' for this search' : ` under "${filter}"`}.
            </p>
          </div>
        </div>

        {/* The auto-suspension and collapse rules moved into the rail's
            "House rules" panel rather than being duplicated in both places. */}
        <TriageRail reports={data ?? []} />
      </div>
    </div>
  )
}
