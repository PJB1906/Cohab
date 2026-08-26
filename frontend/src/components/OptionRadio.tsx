import { cn } from '@/lib/utils'

export function OptionRadio({
  selected,
  onClick,
  children,
  sub,
  className,
}: {
  selected: boolean
  onClick: () => void
  children: React.ReactNode
  sub?: React.ReactNode
  className?: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'cohab-press flex w-full items-center gap-2.5 rounded-full cohab-desktop:rounded-xl text-left cursor-pointer transition-colors',
        'min-h-[46px] cohab-desktop:min-h-0 px-3.5 py-3 cohab-desktop:px-[15px] cohab-desktop:py-[13px]',
        'text-[14.5px] leading-[1.35] cohab-desktop:leading-[1.3] text-cohab-ink',
        sub && 'items-start',
        selected
          ? 'bg-cohab-tint border-[1.5px] border-cohab-primary'
          : 'bg-cohab-card border border-cohab-border',
        className,
      )}
    >
      <span
        className={cn(
          'flex-none rounded-full box-border',
          'w-[18px] h-[18px] cohab-desktop:w-[15px] cohab-desktop:h-[15px]',
          selected
            ? 'border-[6px] cohab-desktop:border-[4.5px] border-cohab-primary bg-cohab-card'
            : 'border-[1.5px] cohab-desktop:border border-cohab-border bg-cohab-card',
        )}
      />
      <span className="flex-1">
        {children}
        {sub && <span className="block mt-1 text-[13px] text-cohab-muted font-normal">{sub}</span>}
      </span>
    </button>
  )
}
