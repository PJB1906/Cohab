import { cn } from '@/lib/utils'

export function Logo({
  size = 'default',
  className,
  ...rest
}: { size?: 'default' | 'lg' } & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('flex items-baseline gap-2', className)} {...rest}>
      <span
        className={cn(
          'font-bold tracking-tight text-cohab-primary',
          size === 'lg' ? 'text-xl' : 'text-lg',
        )}
      >
        Cohab
      </span>
      <span className="font-mono text-[9px] uppercase tracking-wider text-cohab-subtle border border-cohab-border rounded px-1.5 py-0.5">
        Pilot
      </span>
    </div>
  )
}
