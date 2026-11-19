import { useId } from 'react'
import { cn } from '@/lib/utils'

/** The mark (D-14.25): two overlapping roofs on one shared floor. The other
 * person's roof is sun, yours is white, the floor is the match. The same
 * drawing is the favicon (public/favicon-*.svg). */
export function Mark({ size = 30, className }: { size?: number; className?: string }) {
  const id = useId().replace(/:/g, '')
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden className={cn('shrink-0', className)}>
      <defs>
        <linearGradient id={`m${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#4766ff" />
          <stop offset="1" stopColor="#2140f0" />
        </linearGradient>
      </defs>
      <rect width="48" height="48" rx="12" fill={`url(#m${id})`} />
      <path d="M9 31.5 19.5 20.2a2 2 0 0 1 2.94 0L32.94 31.5" fill="none" stroke="#ffc933" strokeWidth="3.6" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M15.06 31.5 25.56 20.2a2 2 0 0 1 2.94 0L39 31.5" fill="none" stroke="#ffffff" strokeWidth="3.6" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M15.5 37.2h17" fill="none" stroke="#ffffff" strokeWidth="3.6" strokeLinecap="round" />
    </svg>
  )
}

/** Wordmark: the mark, then COHAB in the poster cut. "Pilot" stays as a small
 * tag while the product is in pilot. */
export function Logo({
  size = 'default',
  className,
  pilot = true,
  onDark = false,
  ...rest
}: { size?: 'default' | 'lg'; pilot?: boolean; onDark?: boolean } & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('flex items-center gap-2', className)} {...rest}>
      <span className="inline-flex items-center gap-2.5">
        <Mark size={size === 'lg' ? 38 : 30} />
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
