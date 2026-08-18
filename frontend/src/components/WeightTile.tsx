import { cn } from '@/lib/utils'

export function WeightTile({
  title,
  sub,
  rank,
  onClick,
}: {
  title: string
  sub: string
  rank: number | null
  onClick: () => void
}) {
  const selected = rank !== null
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'relative text-left rounded-2xl px-4 py-4 cursor-pointer transition-colors',
        selected
          ? 'bg-cohab-tint border-[1.5px] border-cohab-primary'
          : 'bg-white border border-cohab-border',
      )}
    >
      {selected && (
        <span className="absolute top-3 right-3 w-5 h-5 rounded-full bg-cohab-primary text-white text-[11px] font-semibold flex items-center justify-center">
          {rank}
        </span>
      )}
      <span className="block text-[15px] font-semibold text-cohab-ink mb-1">{title}</span>
      <span className="block text-[12.5px] text-cohab-muted">{sub}</span>
    </button>
  )
}
