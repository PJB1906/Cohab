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
        'cohab-press rounded-[10px] cursor-pointer px-3 py-[7px] cohab-desktop:px-3.5 text-[12.5px] font-medium transition-colors',
        selected
          ? 'bg-cohab-tint border-[1.5px] border-cohab-primary text-cohab-primary'
          : 'bg-cohab-card border border-cohab-border text-cohab-score',
        className,
      )}
    >
      {children}
    </button>
  )
}
