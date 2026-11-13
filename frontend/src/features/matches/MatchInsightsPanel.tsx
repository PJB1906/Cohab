import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { insightsApi } from '@/api/v2'
import { cn } from '@/lib/utils'

/** v2 match-screen insights: the top-3 tie hint and "why so few people?".
 * Both come from GET /matches/insights, which writes nothing and never
 * names or describes an excluded person — counts only. */
export function MatchInsightsPanel({ className, listSize }: { className?: string; listSize: number }) {
  const { data } = useQuery({ queryKey: ['matches', 'insights'], queryFn: insightsApi.get, staleTime: 60_000 })
  const [open, setOpen] = useState(false)
  if (!data?.pool) return null
  const pool = data.pool
  const tied = data.tie_hint?.tied && listSize >= 3
  const few = pool.eligible < 15
  const maxCount = Math.max(1, ...pool.excluded_by_reason.map((r) => r.count))

  return (
    <div className={cn('flex flex-col gap-3', className)}>
      {tied && (
        <div className="bg-cohab-tint border border-cohab-border rounded-2xl px-4 py-3" role="note">
          <p className="text-[13.5px] font-medium text-cohab-ink">Your top three are effectively tied.</p>
          <p className="text-[12.5px] leading-[1.5] text-cohab-muted mt-0.5">
            Under small, plausible changes to how much each habit matters, these three swap places
            {data.tie_hint?.order_change != null && ` ${Math.round(data.tie_hint.order_change * 100)}% of the time`}. Read all
            three rather than trusting the order.
          </p>
        </div>
      )}

      <div className="bg-cohab-card border border-cohab-border rounded-2xl">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          className="w-full flex items-center justify-between gap-3 px-4 py-3 text-left cursor-pointer"
        >
          <span className="text-[13.5px] font-medium">
            {few ? 'Why am I seeing so few people?' : 'Who isn’t in my list, and why?'}
          </span>
          <span className="text-[12.5px] text-cohab-muted tabular-nums flex-none">
            {pool.eligible} of {pool.considered} fit {open ? '−' : '+'}
          </span>
        </button>
        {open && (
          <div className="px-4 pb-4">
            <p className="text-[12.5px] text-cohab-subtle mb-3">
              Hard requirements are checked before any scoring. These are the requirements that ruled people out, each
              counted once, at the first one they failed.
            </p>
            <ul className="flex flex-col gap-2 mb-4">
              {pool.excluded_by_reason.map((r) => (
                <li key={r.reason} className="grid grid-cols-[1fr_auto] gap-x-3 items-center text-[13px]">
                  <span className="text-cohab-ink">{r.label}</span>
                  <span className="tabular-nums text-cohab-muted">{r.count}</span>
                  <span className="col-span-2 h-1 rounded-full bg-cohab-track overflow-hidden mt-1">
                    <span className="block h-full bg-cohab-bar-mid rounded-full" style={{ width: `${(r.count / maxCount) * 100}%` }} />
                  </span>
                </li>
              ))}
            </ul>
            {pool.suggestions.length > 0 ? (
              <div className="border-t border-cohab-border-soft pt-3">
                <p className="text-[12.5px] font-medium text-cohab-muted mb-2">If you changed one thing in your profile</p>
                <ul className="flex flex-col gap-1.5">
                  {pool.suggestions.map((s) => (
                    <li key={s.kind} className="text-[13px]">
                      {s.label}: <span className="font-semibold text-cohab-ink">+{s.adds}</span>{' '}
                      {s.adds === 1 ? 'person' : 'people'}
                    </li>
                  ))}
                </ul>
                <p className="text-[11.5px] text-cohab-subtle mt-2">Exact counts, re-checked against today's pool. Nothing changes unless you edit your profile.</p>
              </div>
            ) : (
              <p className="text-[12.5px] text-cohab-subtle border-t border-cohab-border-soft pt-3">
                No single profile change would add anyone right now.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

const TIER_TEXT: Record<string, string> = { strong: 'Strong fit', good: 'Good fit', possible: 'Possible fit' }

/** Calibrated confidence tier. Shown only when the API sends one, with the
 * calibration's data source spelled out when it isn't real study data. */
export function TierBadge({ tier, source, probability }: { tier?: string | null; source?: string | null; probability?: number | null }) {
  if (!tier) return null
  const synthetic = source && source !== 'real'
  const title =
    probability != null
      ? `People shown pairs like this said they'd message about ${Math.round(probability * 100)}% of the time` +
        (synthetic ? ' (calibration from a synthetic dry run, demo only)' : '')
      : undefined
  return (
    <span
      title={title}
      className={cn(
        'inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium border',
        tier === 'strong' && 'border-cohab-primary text-cohab-primary',
        tier === 'good' && 'border-cohab-border text-cohab-ink',
        tier === 'possible' && 'border-cohab-border text-cohab-muted',
      )}
    >
      {TIER_TEXT[tier] ?? tier}
      {synthetic && <span className="text-cohab-accent">· demo</span>}
    </span>
  )
}
