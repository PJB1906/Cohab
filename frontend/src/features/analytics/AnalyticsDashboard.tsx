import { useQuery } from '@tanstack/react-query'
import { analyticsApi } from '@/api/analytics'
import { AppShell } from '@/components/AppShell'

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

function StatSection({ title, counts, labels }: { title: string; counts: Record<string, number>; labels: Record<string, string> }) {
  return (
    <div className="bg-white border border-cohab-border rounded-2xl p-6 mt-4">
      <h2 className="text-base font-semibold mb-4">{title}</h2>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-px bg-cohab-border rounded-xl overflow-hidden border border-cohab-border">
        {Object.entries(counts).map(([key, count]) => (
          <div key={key} className="bg-white p-3.5">
            <span className="block text-2xl font-bold tabular-nums">{count}</span>
            <span className="block text-[11.5px] text-cohab-muted mt-0.5">{labels[key] ?? key}</span>
          </div>
        ))}
      </div>
    </div>
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
      <div className="max-w-2xl mx-auto px-4 py-7 pb-12">
        <h1 className="text-2xl font-semibold tracking-tight mb-1">Analytics</h1>
        <p className="text-[13.5px] text-cohab-muted mb-2">
          Aggregated, read-only counts — no individual member data. Housing outcomes are covered
          in the evaluation report, not here.
        </p>

        {isLoading && <p className="text-cohab-muted">Loading…</p>}
        {error && <p className="text-cohab-accent">Couldn't load analytics.</p>}

        {data && (
          <>
            <StatSection title="Members by verification" counts={data.members_by_verification_status} labels={VERIFICATION_LABELS} />
            <StatSection title="Members by account status" counts={data.members_by_account_status} labels={ACCOUNT_LABELS} />
            <StatSection title="Matches by state" counts={data.matches_by_state} labels={MATCH_STATE_LABELS} />
            <StatSection title="Reports by status" counts={data.reports_by_status} labels={REPORT_STATUS_LABELS} />
          </>
        )}
      </div>
    </AppShell>
  )
}
