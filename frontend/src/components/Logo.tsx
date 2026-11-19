import { cn } from '@/lib/utils'

/** Wordmark: COHAB in the poster cut, with a volt square standing for the
 * shared room. "Pilot" stays as a small tag while the product is in pilot. */
export function Logo({
  size = 'default',
  className,
  pilot = true,
  ...rest
}: { size?: 'default' | 'lg'; pilot?: boolean } & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('flex items-center gap-2', className)} {...rest}>
      <span className="relative inline-flex items-center">
        <span
          aria-hidden
          className={cn('bg-cohab-volt rounded-[5px] mr-1.5', size === 'lg' ? 'w-[18px] h-[18px]' : 'w-3.5 h-3.5')}
        />
        <span className={cn('poster text-cohab-ink', size === 'lg' ? 'text-[34px]' : 'text-[27px]')}>Cohab</span>
      </span>
      {pilot && <span className="label text-[9px] text-cohab-subtle border border-cohab-border rounded-full px-1.5 py-[3px]">Pilot</span>}
    </div>
  )
}
