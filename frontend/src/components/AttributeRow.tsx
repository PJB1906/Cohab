import { attributeLabel, attributeType } from '@/data/attributes'
import { Progress } from '@/components/ui/progress'
import { cn } from '@/lib/utils'

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

  return (
    <div className="py-3 border-b border-cohab-border-soft last:border-b-0">
      <div className="flex items-baseline justify-between gap-3">
        <div>
          <span className="text-[13.5px] font-semibold text-cohab-ink">{label}</span>
          {type && (
            <span className="ml-2 font-mono text-[10.5px] text-cohab-placeholder uppercase tracking-wide">
              {type}
            </span>
          )}
        </div>
        <span
          className={cn(
            'font-mono text-[13px] font-semibold tabular-nums',
            low ? 'text-cohab-accent' : 'text-cohab-ink',
          )}
        >
          {primary.toFixed(2)}
        </span>
      </div>
      <Progress
        value={primary * 100}
        className="mt-2 h-[3px]"
        barClassName={low ? 'bg-cohab-accent' : 'bg-cohab-primary'}
      />
      {diverges && (
        <p className="mt-1 text-[11.5px] text-cohab-subtle">
          Scored differently in each direction — their view of this: {simB.toFixed(2)}.
        </p>
      )}
    </div>
  )
}
