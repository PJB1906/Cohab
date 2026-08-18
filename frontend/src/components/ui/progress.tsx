import { cn } from '@/lib/utils'

export function Progress({
  value,
  className,
  barClassName,
}: {
  value: number
  className?: string
  barClassName?: string
}) {
  const pct = Math.max(0, Math.min(100, value))
  return (
    <div className={cn('h-1 rounded-full bg-cohab-border-soft overflow-hidden', className)}>
      <div
        className={cn('h-full bg-cohab-primary rounded-full', barClassName)}
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}
