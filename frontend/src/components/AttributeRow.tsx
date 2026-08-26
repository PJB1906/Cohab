import { attributeLabel, attributeType } from '@/data/attributes'
import { Progress } from '@/components/ui/progress'
import { useBarFill } from '@/hooks/useBarFill'
import { cn } from '@/lib/utils'

/** One row of the attribute breakdown. The API only returns sim_a/sim_b per
 * attribute (no free-text "you said X" answer), so unlike the mockups' table
 * — which shows a human-readable answer per side — both breakpoints here
 * show the two directional scores as numbers, not invented sentences. Desktop
 * renders the 4-column table row from screen 8 (Attribute / You / [name] /
 * Score, `AttributeBreakdownCell.sim_a` in "You", `sim_b` in the candidate's
 * column); mobile renders the stacked comparison row from `s8`, dropping the
 * per-attribute description text the mockup shows (not backed by any field
 * the API returns) in favour of a divergence note, same as before. */
export function AttributeRow({
  attribute,
  simA,
  simB,
}: {
  attribute: string
  simA: number
  simB: number
}) {
  const label = attributeLabel(attribute)
  const type = attributeType(attribute)
  const primary = simA // "how well they suit you" on this attribute
  const diverges = Math.abs(simA - simB) > 0.15
  const low = primary < 0.5
  // Mobile bar tint follows the same three-tier banding as the overall score
  // bar (s8's per-row bars: #7fee64 strong, #8cab87 mid, #c96a4d low).
  const mobileBarClass = low ? 'bg-cohab-accent' : primary >= 0.8 ? 'bg-cohab-primary' : 'bg-cohab-bar-mid'
  const desktopBarRef = useBarFill<HTMLDivElement>(primary * 100)

  return (
    <>
      {/* Mobile: stacked row */}
      <div className="cohab-desktop:hidden py-[13px] border-b border-cohab-border-soft last:border-b-0">
        <div className="flex items-baseline justify-between gap-3">
          <span className={cn('text-[14px] font-semibold', low ? 'text-cohab-accent' : 'text-cohab-ink')}>
            {label}
          </span>
          <span
            className={cn(
              'text-[12.5px] font-medium tabular-nums',
              low ? 'text-cohab-accent' : 'text-cohab-muted-mobile',
            )}
          >
            {primary.toFixed(2)}
          </span>
        </div>
        {diverges && (
          <p className={cn('text-[13px] leading-[1.4] mt-[3px] mb-[5px]', low ? 'text-cohab-warn' : 'text-cohab-muted-mobile')}>
            They see this differently — their score: {simB.toFixed(2)}.
          </p>
        )}
        <Progress
          value={primary * 100}
          className={cn('h-[3px]', diverges ? '' : 'mt-2')}
          barClassName={mobileBarClass}
          animate
        />
      </div>

      {/* Desktop: table row, grid-template-columns:150px 1fr 1fr 128px */}
      <div className="hidden cohab-desktop:grid grid-cols-[150px_1fr_1fr_128px] gap-2.5 items-center py-3 border-b border-cohab-border-soft last:border-b-0">
        <div>
          <span className="block text-[13.5px] font-semibold leading-[1.25]">{label}</span>
          {type && (
            <span className="font-mono text-[10.5px] leading-[1.2] text-cohab-placeholder">{type}</span>
          )}
        </div>
        <span className="text-[13.5px] leading-[1.35] text-cohab-score tabular-nums">{simA.toFixed(2)}</span>
        <span className="text-[13.5px] leading-[1.35] text-cohab-score tabular-nums">{simB.toFixed(2)}</span>
        <div className="flex items-center gap-[9px] justify-end">
          <div className="w-[66px] h-1 rounded-full bg-cohab-border-soft overflow-hidden">
            <div
              ref={desktopBarRef}
              className={cn('h-full rounded-full', low ? 'bg-cohab-accent' : 'bg-cohab-primary')}
              style={{ width: `${Math.max(0, Math.min(100, primary * 100))}%` }}
            />
          </div>
          <span className={cn('font-mono text-[13px] font-semibold tabular-nums', low ? 'text-cohab-accent' : 'text-cohab-ink')}>
            {primary.toFixed(2)}
          </span>
        </div>
      </div>
    </>
  )
}
