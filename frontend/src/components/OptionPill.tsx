import { cn } from '@/lib/utils'

/** A single question option, styled per the mobile mockup's pill pattern
 * (rounded-full, tinted+bordered when selected). Used for both single-select
 * (radio-like) and multi-select (chip) option lists — one visual language
 * rather than switching style per input type. */
export function OptionPill({
  selected,
  onClick,
  children,
  className,
}: {
  selected: boolean
  onClick: () => void
  children: React.ReactNode
  className?: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'cohab-press min-h-12 w-full text-left px-4 py-3 rounded-[14px] text-[15px] leading-tight cursor-pointer transition-colors border-[1.5px]',
        selected
          ? 'bg-cohab-tint border-cohab-primary text-cohab-primary font-bold'
          : 'bg-cohab-card border-cohab-border-soft text-cohab-ink hover:border-cohab-ink',
        className,
      )}
    >
      {children}
    </button>
  )
}

/** Compact variant for chip grids (interests, filters) — inline width, not full-width. */
export function ChipPill({
  selected,
  onClick,
  children,
}: {
  selected: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'cohab-press min-h-10 px-4 rounded-full text-[13.5px] font-semibold cursor-pointer transition-colors border-[1.5px] whitespace-nowrap',
        selected
          ? 'bg-cohab-fill border-cohab-fill text-cohab-on-fill'
          : 'bg-cohab-card border-cohab-border-soft text-cohab-ink hover:border-cohab-ink',
      )}
    >
      {children}
    </button>
  )
}
