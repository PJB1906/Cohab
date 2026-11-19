import { useBarFill } from '@/hooks/useBarFill'
import { cn } from '@/lib/utils'

export function Progress({
  value,
  className,
  barClassName,
  /** Opt in to the scroll-triggered fill (docs/DECISIONS.md D-12.2). Off by
   * default so existing call sites — and any bar used as a step indicator
   * rather than as a score — keep rendering statically. */
  animate = false,
}: {
  value: number
  className?: string
  barClassName?: string
  animate?: boolean
}) {
  const pct = Math.max(0, Math.min(100, value))
  const barRef = useBarFill<HTMLDivElement>(pct)

  return (
    <div className={cn('h-1 rounded-full bg-cohab-border-soft overflow-hidden', className)}>
      <div
        ref={animate ? barRef : undefined}
        className={cn('h-full bg-cohab-fill rounded-full', barClassName)}
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}
