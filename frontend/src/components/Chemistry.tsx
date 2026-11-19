import { useEffect, useRef, useState } from 'react'
import { cn } from '@/lib/utils'
import { prefersReducedMotion } from '@/lib/motion'

export interface ChemistryRow {
  key: string
  label: string
  /** How well they suit you on this habit, 0-1 (the matcher's sim_a). */
  you: number
  /** How well you suit them, 0-1 (sim_b). */
  them: number
}

/** The match "chemistry" chart (D-14.23, borrowed from The Pudding's mirrored
 * bars): each habit is a row, your side grows left from the spine and theirs
 * grows right. Both long = you suit each other; one short = the match suits
 * only one of you, which is exactly what the harmonic mean penalises.
 *
 * Fills carry meaning, not decoration: cobalt when both sides are strong
 * (>= 0.8), tomato when either side is weak (< 0.5), ink otherwise. */
export function Chemistry({
  rows,
  youLabel = 'For you',
  themLabel = 'For them',
  className,
  dark = false,
}: {
  rows: ChemistryRow[]
  youLabel?: string
  themLabel?: string
  className?: string
  dark?: boolean
}) {
  const ref = useRef<HTMLDivElement>(null)
  const [shown, setShown] = useState(() => prefersReducedMotion())

  useEffect(() => {
    if (shown || !ref.current) return
    const el = ref.current
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setShown(true)
          io.disconnect()
        }
      },
      { threshold: 0.2 },
    )
    io.observe(el)
    // Never leave the chart empty if the observer cannot fire (hidden tab,
    // print, old browser): grow the bars after a short delay regardless.
    const t = window.setTimeout(() => setShown(true), 1500)
    return () => {
      io.disconnect()
      window.clearTimeout(t)
    }
  }, [shown])

  // Cobalt ramp for strength (D-14.24): both sides strong is solid cobalt, a
  // middling row is the lighter blue, a weak side is coral. On the navy band
  // the strong tone is sun, the one match-moment colour.
  const tone = (r: ChemistryRow) =>
    r.you >= 0.8 && r.them >= 0.8
      ? dark
        ? 'bg-cohab-sun'
        : 'bg-cohab-primary'
      : r.you < 0.5 || r.them < 0.5
        ? 'bg-cohab-accent'
        : dark
          ? 'bg-white/70'
          : 'bg-cohab-sky'

  return (
    <div ref={ref} className={cn('w-full', className)}>
      <div className={cn('grid grid-cols-[1fr_auto_1fr] gap-x-3 mb-2 label text-[10px]', dark ? 'text-white/55' : 'text-cohab-subtle')}>
        <span className="text-right">{youLabel}</span>
        <span className="w-[112px] cohab-desktop:w-[140px]" />
        <span>{themLabel}</span>
      </div>
      <ul className="flex flex-col gap-[7px]">
        {rows.map((r, i) => (
          <li key={r.key} className="grid grid-cols-[1fr_auto_1fr] gap-x-3 items-center">
            <div className="flex justify-end">
              <div
                className={cn('h-[14px] rounded-l-full transition-[width] ease-[cubic-bezier(.22,1,.36,1)]', tone(r))}
                style={{ width: shown ? `${Math.max(3, r.you * 100)}%` : '0%', transitionDuration: '900ms', transitionDelay: `${i * 45}ms` }}
                title={`${Math.round(r.you * 100)}% for you`}
              />
            </div>
            <span
              className={cn(
                'w-[112px] cohab-desktop:w-[140px] text-center text-[12.5px] font-semibold truncate',
                dark ? 'text-white' : 'text-cohab-ink',
              )}
            >
              {r.label}
            </span>
            <div className="flex justify-start">
              <div
                className={cn('h-[14px] rounded-r-full transition-[width] ease-[cubic-bezier(.22,1,.36,1)]', tone(r))}
                style={{ width: shown ? `${Math.max(3, r.them * 100)}%` : '0%', transitionDuration: '900ms', transitionDelay: `${i * 45}ms` }}
                title={`${Math.round(r.them * 100)}% for them`}
              />
            </div>
          </li>
        ))}
      </ul>
      <div className={cn('flex flex-wrap gap-x-4 gap-y-1 mt-3 text-[11.5px]', dark ? 'text-white/60' : 'text-cohab-subtle')}>
        <span className="inline-flex items-center gap-1.5">
          <span className={cn('w-3 h-2 rounded-full', dark ? 'bg-cohab-sun' : 'bg-cohab-primary')} /> both strong
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className={cn('w-3 h-2 rounded-full', dark ? 'bg-white/70' : 'bg-cohab-sky')} /> fine
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="w-3 h-2 rounded-full bg-cohab-accent" /> weak on one side
        </span>
      </div>
    </div>
  )
}
