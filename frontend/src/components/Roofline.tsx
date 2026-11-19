import { useMemo } from 'react'
import { cn } from '@/lib/utils'

/** The neighbourhood (D-14.26): a line drawing of rooftops built from the
 * mark's own roof shape, with a few windows lit in sun that slowly come and
 * go. Used as a quiet background illustration at the foot of pages and on
 * ink panels. Deterministic, so it never reshuffles between renders. */
function rng(seed: number) {
  let s = seed >>> 0
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0
    return s / 4294967296
  }
}

interface House {
  x: number
  w: number
  h: number
  roof: 'pitch' | 'flat' | 'double'
  rh: number
  windows: { x: number; y: number; lit: boolean; delay: number }[]
}

function build(width: number, height: number, seed: number): House[] {
  const r = rng(seed)
  const out: House[] = []
  let x = -20
  while (x < width + 20) {
    const w = 56 + Math.round(r() * 84)
    const h = 34 + Math.round(r() * (height - 70))
    const roofPick = r()
    const roof = roofPick < 0.55 ? 'pitch' : roofPick < 0.8 ? 'flat' : 'double'
    const rh = roof === 'flat' ? 0 : 16 + Math.round(r() * 18)
    const windows: House['windows'] = []
    const cols = Math.max(1, Math.floor((w - 16) / 22))
    const rows = Math.max(1, Math.floor((h - 14) / 24))
    for (let c = 0; c < cols; c++) {
      for (let rr = 0; rr < rows; rr++) {
        if (r() < 0.55) continue
        windows.push({ x: x + 12 + c * 22, y: height - h + 10 + rr * 24, lit: r() < 0.16, delay: Math.round(r() * 6000) })
      }
    }
    out.push({ x, w, h, roof, rh, windows })
    x += w + 4 + Math.round(r() * 10)
  }
  return out
}

export function Roofline({
  className,
  tone = 'page',
  seed = 7,
}: {
  className?: string
  /** page: faint ink on the canvas; panel: faint white on ink panels. */
  tone?: 'page' | 'panel'
  seed?: number
}) {
  const W = 1600
  const H = 170
  const houses = useMemo(() => build(W, H, seed), [seed])
  const stroke = tone === 'panel' ? 'rgb(255 255 255 / 0.13)' : 'var(--roofline)'
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="xMidYMax slice"
      aria-hidden
      className={cn('pointer-events-none select-none', className)}
    >
      <g fill="none" stroke={stroke} strokeWidth="1.4" strokeLinejoin="round" strokeLinecap="round">
        {houses.map((h, i) => {
          const top = H - h.h
          const body = `M${h.x} ${H} V${top} H${h.x + h.w} V${H}`
          let roof = ''
          if (h.roof === 'pitch') roof = `M${h.x - 4} ${top + 2} L${h.x + h.w / 2} ${top - h.rh} L${h.x + h.w + 4} ${top + 2}`
          if (h.roof === 'double') {
            const m = h.x + h.w * 0.42
            roof = `M${h.x - 4} ${top + 2} L${h.x + h.w * 0.25} ${top - h.rh} L${m + 6} ${top + 2} M${m - 6} ${top + 2} L${h.x + h.w * 0.7} ${top - h.rh} L${h.x + h.w + 4} ${top + 2}`
          }
          return (
            <g key={i}>
              <path d={body} />
              {roof && <path d={roof} />}
            </g>
          )
        })}
        <path d={`M0 ${H - 0.7} H${W}`} />
      </g>
      <g>
        {houses.flatMap((h) =>
          h.windows.map((w, j) => (
            <rect
              key={`${h.x}-${j}`}
              x={w.x}
              y={w.y}
              width="8"
              height="10"
              rx="1.5"
              fill={w.lit ? 'var(--color-cohab-sun)' : 'none'}
              stroke={w.lit ? 'none' : stroke}
              strokeWidth="1.1"
              className={w.lit ? 'roof-window' : undefined}
              style={w.lit ? { animationDelay: `${w.delay}ms`, opacity: tone === 'panel' ? 0.85 : 0.6 } : undefined}
            />
          )),
        )}
      </g>
    </svg>
  )
}
