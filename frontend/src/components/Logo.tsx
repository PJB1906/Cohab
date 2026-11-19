import { cn } from '@/lib/utils'

/** Wordmark: a cobalt tile holding two overlapping circles (two people, one
 * shared room), then COHAB in the poster cut. "Pilot" stays as a small tag
 * while the product is in pilot. */
export function Logo({
  size = 'default',
  className,
  pilot = true,
  onDark = false,
  ...rest
}: { size?: 'default' | 'lg'; pilot?: boolean; onDark?: boolean } & React.HTMLAttributes<HTMLDivElement>) {
  const px = size === 'lg' ? 34 : 28
  return (
    <div className={cn('flex items-center gap-2', className)} {...rest}>
      <span className="inline-flex items-center gap-2">
        <svg width={px} height={px} viewBox="0 0 32 32" aria-hidden>
          <rect width="32" height="32" rx="9" fill="#2a4bff" />
          <circle cx="12.5" cy="16" r="6.5" fill="#ffffff" />
          <circle cx="19.5" cy="16" r="6.5" fill="#ffc933" />
          <path d="M16 10.6a6.5 6.5 0 010 10.8 6.5 6.5 0 010-10.8z" fill="#0b1033" />
        </svg>
        <span className={cn('poster', onDark ? 'text-white' : 'text-cohab-ink', size === 'lg' ? 'text-[36px]' : 'text-[28px]')}>
          Cohab
        </span>
      </span>
      {pilot && (
        <span
          className={cn(
            'label text-[9px] rounded-full px-1.5 py-[3px] border',
            onDark ? 'text-white/70 border-white/25' : 'text-cohab-subtle border-cohab-border',
          )}
        >
          Pilot
        </span>
      )}
    </div>
  )
}
