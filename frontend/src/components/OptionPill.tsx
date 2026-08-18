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
        'min-h-11 w-full text-left px-3.5 py-3 rounded-full text-[14.5px] leading-tight cursor-pointer transition-colors',
        selected
          ? 'bg-cohab-tint border-[1.5px] border-cohab-primary text-cohab-ink font-medium'
          : 'bg-white border border-cohab-border text-cohab-ink',
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
        'min-h-10 px-3.5 rounded-full text-[13.5px] font-medium cursor-pointer transition-colors',
        selected
          ? 'bg-cohab-tint border-[1.5px] border-cohab-primary text-cohab-primary'
          : 'bg-white border border-cohab-border text-cohab-muted',
      )}
    >
      {children}
    </button>
  )
}
