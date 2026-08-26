import { cn } from '@/lib/utils'

export function FactsGrid({
  columns,
  items,
  className,
}: {
  columns: number
  items: { label: string; value: React.ReactNode }[]
  className?: string
}) {
  return (
    <div
      className={cn(
        'grid gap-px bg-cohab-border border border-cohab-border rounded-xl overflow-hidden',
        className,
      )}
      style={{ gridTemplateColumns: `repeat(${columns}, 1fr)` }}
    >
      {items.map((item, i) => (
        <div key={i} className="bg-cohab-card px-[15px] py-[13px]">
          <span className="font-mono font-medium text-[10px] leading-none uppercase tracking-[.06em] text-cohab-subtle">
            {item.label}
          </span>
          <p className="mt-[7px] font-semibold text-sm">{item.value}</p>
        </div>
      ))}
    </div>
  )
}
