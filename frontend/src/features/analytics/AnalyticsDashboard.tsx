import { useQuery } from '@tanstack/react-query'
import { analyticsApi } from '@/api/analytics'
import { AppShell } from '@/components/AppShell'
import { Reveal } from '@/components/motion/Reveal'
import { CountUp } from '@/components/motion/CountUp'

const VERIFICATION_LABELS: Record<string, string> = {
  unverified: 'Unverified',
  pending: 'Pending',
  verified: 'Verified',
}

const ACCOUNT_LABELS: Record<string, string> = {
  active: 'Active',
  suspended: 'Suspended',
  banned: 'Banned',
  erased: 'Erased',
}

const MATCH_STATE_LABELS: Record<string, string> = {
  suggested: 'Suggested',
  viewed: 'Viewed',
  interested: 'Interested',
  mutual: 'Mutual',
  chatting: 'Chatting',
  contact_shared: 'Contact shared',
  cohabiting: 'Cohabiting',
  rejected: 'Rejected',
  expired: 'Expired',
}

const REPORT_STATUS_LABELS: Record<string, string> = {
  open: 'Open',
  under_review: 'Under review',
  substantiated: 'Substantiated',
  dismissed: 'Dismissed',
  action_taken: 'Action taken',
}

/** A count plus its share of the section total.
 *
 * The bare number alone told a moderator almost nothing — "42 mutual" only
 * means something against how many matches exist. The share bar is computed
 * client-side from the same dict the tile already renders, so it adds a
 * dimension of meaning without a new field or endpoint. */
function StatTile({
  label,
  count,
  total,
  span = '',
  barWidth = '',
}: {
  label: string
  count: number
  total: number
  span?: string
  barWidth?: string
}) {
  const pct = total === 0 ? 0 : Math.round((count / total) * 100)
  return (
    <div className={`bg-cohab-card p-4 flex flex-col ${span}`}>
      <CountUp value={count} locale="en-IN" className="block text-[26px] leading-none font-semibold tabular-nums" />
      <span className="block text-[11.5px] leading-[1.35] text-cohab-muted mt-1.5 mb-2.5">{label}</span>
      {/* A tile stretched over a part-empty row is capped back to one
          column's width, so its meter reads at the same length as its
          row-mates' rather than several times theirs. */}
      <div className={`mt-auto flex items-center gap-2 ${barWidth}`}>
        <div className="flex-1 h-1 rounded-full bg-cohab-border-soft overflow-hidden">
          <div className="h-full rounded-full bg-cohab-primary" style={{ width: `${pct}%` }} />
        </div>
        <span className="text-[11px] tabular-nums text-cohab-subtle w-8 text-right">{pct}%</span>
      </div>
    </div>
  )
}

/** Tailwind only sees class names it can read literally, so the span classes
 * are looked up rather than interpolated. Indices are the number of cells the
 * entries leave empty in the final row; the tile spans one more than that.
 *
 * The bar caps undo the stretch for the meter: inside a tile of `k` columns
 * the row is `p-4`-inset, so one column of it measures `100%/k` less the
 * padding the extra column boundaries swallow. */
const COL_SPAN = ['col-span-1', 'col-span-2'] as const
const SM_COL_SPAN = ['sm:col-span-1', 'sm:col-span-2', 'sm:col-span-3'] as const
const BAR_WIDTH = ['max-w-none', 'max-w-[calc(50%-16px)]'] as const
const SM_BAR_WIDTH = [
  'sm:max-w-none',
  'sm:max-w-[calc(50%-16px)]',
  'sm:max-w-[calc(33.333%-22px)]',
] as const

/** How far the last tile must stretch to close its row.
 *
 * The tiles are a `gap-px` mosaic over a border-coloured background, so every
 * cell the entries don't fill shows that background as a grey slab — four
 * account statuses in a three-column grid left two dead cells, reported by the
 * user. Stretching the final tile over the remainder keeps the grid flush at
 * both breakpoints without varying the column count between sections that sit
 * side by side. */
function lastTileShape(count: number): { span: string; barWidth: string } {
  const fill = (cols: number) => (cols - (count % cols)) % cols
  return {
    span: `${COL_SPAN[fill(2)]} ${SM_COL_SPAN[fill(3)]}`,
    barWidth: `${BAR_WIDTH[fill(2)]} ${SM_BAR_WIDTH[fill(3)]}`,
  }
}

function StatSection({
  title,
  caption,
  counts,
  labels,
}: {
  title: string
  caption: string
  counts: Record<string, number>
  labels: Record<string, string>
}) {
  const entries = Object.entries(counts)
  const total = entries.reduce((sum, [, n]) => sum + n, 0)

  return (
    <Reveal className="surface rounded-[22px] p-6">
      <div className="flex items-baseline justify-between gap-4 mb-1">
        <h2 className="text-base font-semibold">{title}</h2>
        <span className="text-[12px] tabular-nums text-cohab-subtle flex-none">
          {total.toLocaleString('en-IN')} total
        </span>
      </div>
      <p className="text-[12.5px] leading-[1.45] text-cohab-subtle mb-4">{caption}</p>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-px bg-cohab-border rounded-xl overflow-hidden border border-cohab-border">
        {entries.map(([key, count], i) => (
          <StatTile
            key={key}
            label={labels[key] ?? key}
            count={count}
            total={total}
            {...(i === entries.length - 1 ? lastTileShape(entries.length) : {})}
          />
        ))}
      </div>
    </Reveal>
  )
}

/** PRD §3.2's Dr Sathya persona ("aggregated visibility into whether
 * students are housed and where problems cluster. Read-only, anonymised") —
 * built as v1-adjacent minimal scope per docs/DECISIONS.md's Phase 8
 * section, not the full v2 "institutional analytics dashboard" PRD §4
 * formally scopes to post-pilot. Gated by is_moderator (App.tsx), same as
 * /moderation — no separate institution-admin role exists yet. */
export function AnalyticsDashboard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['analytics', 'summary'],
    queryFn: () => analyticsApi.summary(),
  })

  return (
    <AppShell>
      {/* Widened from `max-w-2xl` (672px) to the app's own 1800px rhythm and
          laid out two-up (docs/DECISIONS.md D-13.4) — at desktop widths the
          narrow column left most of the screen empty, reported by the user. */}
      <div className="max-w-[1800px] mx-auto px-4 cohab-desktop:px-6 py-7 pb-12">
        <h1 className="poster text-[64px] mb-2">Analytics</h1>
        <p className="text-[13.5px] leading-[1.5] text-cohab-muted mb-6 max-w-[720px]">
          Aggregated, read-only counts — no individual member data. Housing outcomes are covered
          in the evaluation report, not here.
        </p>

        {isLoading && <p className="text-cohab-muted">Loading…</p>}
        {error && <p className="text-cohab-accent">Couldn't load analytics.</p>}

        {data && (
          <div className="grid gap-4 grid-cols-1 cohab-desktop:grid-cols-2 items-start">
            <StatSection
              title="Members by verification"
              caption="Only verified members enter anyone's candidate pool."
              counts={data.members_by_verification_status}
              labels={VERIFICATION_LABELS}
            />
            <StatSection
              title="Members by account status"
              caption="Suspended and banned accounts are excluded from matching."
              counts={data.members_by_account_status}
              labels={ACCOUNT_LABELS}
            />
            <StatSection
              title="Matches by state"
              caption="Every suggested pair that progressed, and how far it got."
              counts={data.matches_by_state}
              labels={MATCH_STATE_LABELS}
            />
            <StatSection
              title="Reports by status"
              caption="Safety cases filed by members, by where they sit now."
              counts={data.reports_by_status}
              labels={REPORT_STATUS_LABELS}
            />
          </div>
        )}
      </div>
    </AppShell>
  )
}
