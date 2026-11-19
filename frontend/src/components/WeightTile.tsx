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
        'relative flex items-center gap-3.5 text-left cursor-pointer transition-colors',
        'min-h-[62px] rounded-2xl px-3.5 py-3',
        'cohab-desktop:block cohab-desktop:min-h-0 cohab-desktop:rounded-2xl cohab-desktop:px-[18px] cohab-desktop:pt-[18px] cohab-desktop:pb-5',
        selected
          ? 'bg-cohab-tint border-[1.5px] border-cohab-primary'
          : 'bg-cohab-card border border-cohab-border',
      )}
    >
      {/* Mobile: rank shown inline as a leading circle (proto s6's row list). */}
      <span
        className={cn(
          'flex-none w-[26px] h-[26px] rounded-full flex items-center justify-center text-[13px] font-semibold',
          'cohab-desktop:hidden',
          selected ? 'bg-cohab-fill text-cohab-on-fill' : 'bg-cohab-row-tint text-cohab-subtle',
        )}
      >
        {rank ?? ''}
      </span>
      {/* Desktop: rank shown as an absolute badge on the tile (desktop s6). */}
      {selected && (
        <span className="hidden cohab-desktop:flex absolute top-[18px] right-[18px] w-5 h-5 rounded-full bg-cohab-fill text-cohab-on-fill text-[11px] font-semibold items-center justify-center">
          {rank}
        </span>
      )}
      <span className="flex-1 min-w-0">
        <span className="block text-[15px] font-semibold text-cohab-ink mb-1 cohab-desktop:mb-[5px] leading-[1.25] cohab-desktop:leading-[1.2]">
          {title}
        </span>
        <span className="block text-[13px] cohab-desktop:text-[12.5px] text-cohab-muted leading-[1.35] cohab-desktop:leading-[1.4]">
          {sub}
        </span>
      </span>
    </button>
  )
}
