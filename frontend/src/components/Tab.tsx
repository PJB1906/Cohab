import { cn } from '@/lib/utils'

export function Tab({
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
        // rounded-[10px], not `rounded` (4px): at 4px these read as square
        // boxes rather than the mockup's soft pills, and they sit beside
        // the rent Inputs which are already rounded-[10px].
        'cohab-press rounded-full cursor-pointer px-3.5 py-[7px] text-[12.5px] font-semibold transition-colors border-2',
        selected
          ? 'bg-cohab-ink border-cohab-ink text-cohab-card'
          : 'bg-transparent border-cohab-border text-cohab-ink hover:border-cohab-ink',
        className,
      )}
    >
      {children}
    </button>
  )
}
