/** Small SVG chart primitives for the evidence page. Colours come from the
 * theme tokens so every chart follows light/dark mode. No chart library:
 * each chart is a few dozen lines and draws exactly what the report needs. */
import { cn } from '@/lib/utils'
import type { DataSource } from '@/api/v2'

// Poster palette roles for charts (D-14.23): the learned/real series is ink,
// the expert baseline is a mid grey, warnings tomato. Volt is not used on
// these light chart surfaces (it has no contrast against white).
export const C = {
  ink: 'var(--color-cohab-ink)',
  muted: 'var(--color-cohab-muted)',
  subtle: 'var(--color-cohab-subtle)',
  grid: 'var(--color-cohab-border-soft)',
  primary: 'var(--color-cohab-ink)',
  accent: 'var(--color-cohab-accent)',
  expert: 'var(--color-cohab-placeholder)',
}

const SOURCE: Record<DataSource, { label: string; tone: string }> = {
  real: { label: 'Real study data', tone: 'border-cohab-primary text-cohab-primary' },
  dryrun: { label: 'Synthetic dry run · not evidence', tone: 'border-cohab-accent text-cohab-accent' },
  simulation: { label: 'Simulation · stated assumptions', tone: 'border-cohab-border text-cohab-muted' },
  public: { label: 'Public dataset', tone: 'border-cohab-border text-cohab-muted' },
}

export function SourceBadge({ source }: { source: DataSource }) {
  const s = SOURCE[source] ?? { label: source, tone: 'border-cohab-border text-cohab-muted' }
  return <span className={cn('inline-block rounded-full border px-2 py-0.5 text-[11px] font-medium whitespace-nowrap', s.tone)}>{s.label}</span>
}

export function fmt(v: number | null | undefined, digits = 3): string {
  return v == null || Number.isNaN(v) ? '—' : v.toFixed(digits)
}

export function ci(v?: (number | null)[] | null, digits = 3): string {
  if (!v || v[0] == null || v[1] == null) return ''
  return `[${(v[0] as number).toFixed(digits)}, ${(v[1] as number).toFixed(digits)}]`
}

/** Learned weight with a 95% interval next to the expert value, per attribute. */
export function ForestChart({
  labels,
  expert,
  learned,
  low,
  high,
}: {
  labels: string[]
  expert: number[]
  learned: number[]
  low: number[]
  high: number[]
}) {
  const order = labels.map((_, i) => i).sort((a, b) => expert[b] - expert[a])
  const max = Math.max(...high, ...expert) * 1.08
  const W = 560
  const L = 150
  const row = 22
  const H = order.length * row + 34
  const x = (v: number) => L + (v / max) * (W - L - 16)
  const ticks = [0, max / 4, max / 2, (3 * max) / 4].map((t) => Math.round(t * 100) / 100)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label="Learned versus expert weights with 95% intervals">
      {ticks.map((t) => (
        <g key={t}>
          <line x1={x(t)} x2={x(t)} y1={6} y2={H - 26} stroke={C.grid} />
          <text x={x(t)} y={H - 12} fill={C.subtle} fontSize={10} textAnchor="middle">
            {t.toFixed(2)}
          </text>
        </g>
      ))}
      {order.map((i, r) => {
        const y = 14 + r * row
        return (
          <g key={labels[i]}>
            <text x={L - 8} y={y + 4} fill={C.muted} fontSize={11} textAnchor="end">
              {labels[i]}
            </text>
            <line x1={x(low[i])} x2={x(high[i])} y1={y} y2={y} stroke={C.primary} strokeWidth={2} strokeLinecap="round" />
            <rect x={x(expert[i]) - 4} y={y - 4} width={8} height={8} fill={C.expert} />
            <circle cx={x(learned[i])} cy={y} r={4.5} fill={C.primary} />
          </g>
        )
      })}
    </svg>
  )
}

export function Legend({ items }: { items: { label: string; color: string; shape?: 'dot' | 'square' | 'dash' }[] }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11.5px] text-cohab-muted">
      {items.map((it) => (
        <span key={it.label} className="inline-flex items-center gap-1.5">
          <svg width="14" height="10" aria-hidden>
            {it.shape === 'square' ? (
              <rect x="3" y="1" width="8" height="8" fill={it.color} />
            ) : it.shape === 'dash' ? (
              <line x1="0" x2="14" y1="5" y2="5" stroke={it.color} strokeDasharray="3 2" strokeWidth={2} />
            ) : (
              <circle cx="7" cy="5" r="4" fill={it.color} />
            )}
          </svg>
          {it.label}
        </span>
      ))}
    </div>
  )
}

/** Vertical bars with interval whiskers and an optional reference line. */
export function BarsWithCI({
  items,
  min = 0,
  max = 1,
  reference,
  highlight,
}: {
  items: { label: string; value: number; low?: number; high?: number }[]
  min?: number
  max?: number
  reference?: { value: number; label: string }
  highlight?: string[]
}) {
  const W = 560
  const H = 220
  const top = 14
  const bottom = 30
  const left = 34
  const bw = (W - left - 10) / items.length
  const y = (v: number) => top + (1 - (v - min) / (max - min)) * (H - top - bottom)
  const ticks = [min, min + (max - min) / 2, max]
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img">
      {ticks.map((t) => (
        <g key={t}>
          <line x1={left} x2={W - 6} y1={y(t)} y2={y(t)} stroke={C.grid} />
          <text x={left - 6} y={y(t) + 3} fill={C.subtle} fontSize={10} textAnchor="end">
            {t.toFixed(2)}
          </text>
        </g>
      ))}
      {items.map((it, i) => {
        const cx = left + bw * i + bw / 2
        const hl = highlight?.includes(it.label)
        return (
          <g key={it.label}>
            <rect
              x={cx - bw * 0.32}
              y={y(it.value)}
              width={bw * 0.64}
              height={Math.max(0, y(min) - y(it.value))}
              fill={hl ? (it.label === highlight?.[highlight.length - 1] ? C.primary : C.subtle) : C.expert}
              rx={3}
            />
            {it.low != null && it.high != null && (
              <line x1={cx} x2={cx} y1={y(it.high)} y2={y(it.low)} stroke={C.ink} strokeWidth={1.5} />
            )}
            <text x={cx} y={H - 12} fill={C.muted} fontSize={11} textAnchor="middle">
              {it.label}
            </text>
            <text x={cx} y={y(it.value) - 5} fill={C.ink} fontSize={10.5} textAnchor="middle">
              {it.value.toFixed(3)}
            </text>
          </g>
        )
      })}
      {reference && (
        <g>
          <line x1={left} x2={W - 6} y1={y(reference.value)} y2={y(reference.value)} stroke={C.accent} strokeDasharray="5 4" />
          <text x={left + 4} y={y(reference.value) - 4} fill={C.accent} fontSize={10.5} textAnchor="start">
            {reference.label}
          </text>
        </g>
      )}
    </svg>
  )
}

/** Predicted vs observed with the diagonal. */
export function ReliabilityChart({ series }: { series: { label: string; color: string; bins: { mean_p: number; observed: number; n: number }[] }[] }) {
  const S = 260
  const p = 30
  const x = (v: number) => p + v * (S - p - 8)
  const y = (v: number) => S - p - v * (S - p - 8)
  return (
    <svg viewBox={`0 0 ${S} ${S}`} className="w-full max-w-[320px] h-auto" role="img" aria-label="Reliability diagram">
      {[0, 0.5, 1].map((t) => (
        <g key={t}>
          <line x1={x(t)} x2={x(t)} y1={y(0)} y2={y(1)} stroke={C.grid} />
          <line x1={x(0)} x2={x(1)} y1={y(t)} y2={y(t)} stroke={C.grid} />
          <text x={x(t)} y={S - 12} fill={C.subtle} fontSize={10} textAnchor="middle">
            {t}
          </text>
          <text x={p - 6} y={y(t) + 3} fill={C.subtle} fontSize={10} textAnchor="end">
            {t}
          </text>
        </g>
      ))}
      <line x1={x(0)} y1={y(0)} x2={x(1)} y2={y(1)} stroke={C.subtle} strokeDasharray="3 3" />
      {series.map((s) => (
        <g key={s.label}>
          <polyline fill="none" stroke={s.color} strokeWidth={2} points={s.bins.map((b) => `${x(b.mean_p)},${y(b.observed)}`).join(' ')} />
          {s.bins.map((b, i) => (
            <circle key={i} cx={x(b.mean_p)} cy={y(b.observed)} r={Math.min(6, 2 + Math.sqrt(b.n) / 6)} fill={s.color} />
          ))}
        </g>
      ))}
    </svg>
  )
}

/** One line per series over a shared numeric x axis. */
export function LineChart({
  series,
  xLabel,
  yLabel,
  yMin = 0,
  yMax = 1,
  reference,
}: {
  series: { label: string; color: string; points: [number, number][] }[]
  xLabel: string
  yLabel: string
  yMin?: number
  yMax?: number
  reference?: number
}) {
  const W = 560
  const H = 240
  const L = 40
  const B = 34
  const xs = series.flatMap((s) => s.points.map((p) => p[0]))
  const xmin = Math.min(...xs)
  const xmax = Math.max(...xs)
  const x = (v: number) => L + ((v - xmin) / Math.max(xmax - xmin, 1e-9)) * (W - L - 12)
  const T = 24
  const y = (v: number) => T + (1 - (v - yMin) / (yMax - yMin)) * (H - T - B)
  const xt = Array.from(new Set(xs)).sort((a, b) => a - b)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img">
      {[yMin, (yMin + yMax) / 2, yMax].map((t) => (
        <g key={t}>
          <line x1={L} x2={W - 8} y1={y(t)} y2={y(t)} stroke={C.grid} />
          <text x={L - 6} y={y(t) + 3} fill={C.subtle} fontSize={10} textAnchor="end">
            {t.toFixed(1)}
          </text>
        </g>
      ))}
      {xt.map((t) => (
        <text key={t} x={x(t)} y={H - 18} fill={C.subtle} fontSize={10} textAnchor="middle">
          {t}
        </text>
      ))}
      <text x={(L + W) / 2} y={H - 3} fill={C.muted} fontSize={10.5} textAnchor="middle">
        {xLabel}
      </text>
      <text x={L} y={11} fill={C.muted} fontSize={10.5}>
        {yLabel}
      </text>
      {reference != null && <line x1={L} x2={W - 8} y1={y(reference)} y2={y(reference)} stroke={C.accent} strokeDasharray="4 4" />}
      {series.map((s) => (
        <g key={s.label}>
          <polyline fill="none" stroke={s.color} strokeWidth={2} points={s.points.map(([a, b]) => `${x(a)},${y(b)}`).join(' ')} />
          {s.points.map(([a, b]) => (
            <circle key={a} cx={x(a)} cy={y(b)} r={3} fill={s.color} />
          ))}
        </g>
      ))}
    </svg>
  )
}

/** Histogram (stairs) with a marked observed value. */
export function NullHistogram({ counts, edges, observed }: { counts: number[]; edges: number[]; observed: number }) {
  const W = 560
  const H = 170
  const B = 26
  const lo = Math.min(edges[0], observed)
  const hi = Math.max(edges[edges.length - 1], observed)
  const x = (v: number) => 10 + ((v - lo) / Math.max(hi - lo, 1e-9)) * (W - 20)
  const max = Math.max(...counts, 1)
  const y = (c: number) => H - B - (c / max) * (H - B - 12)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img">
      {counts.map((c, i) => (
        <rect key={i} x={x(edges[i])} y={y(c)} width={Math.max(1, x(edges[i + 1]) - x(edges[i]) - 1)} height={H - B - y(c)} fill={C.expert} />
      ))}
      <line x1={x(observed)} x2={x(observed)} y1={8} y2={H - B} stroke={C.primary} strokeWidth={2.5} />
      <text x={x(observed) + 4} y={18} fill={C.primary} fontSize={11}>
        real pairs
      </text>
      {[edges[0], edges[edges.length - 1]].map((t, i) => (
        <text key={t} x={x(t)} y={H - 8} fill={C.subtle} fontSize={10} textAnchor={i === 0 ? 'start' : 'end'}>
          {t.toFixed(3)}
        </text>
      ))}
    </svg>
  )
}

export const SERIES_COLORS = ['var(--color-cohab-ink)', 'var(--color-cohab-accent)', '#2563eb', '#0d9488', '#c99a1a', '#8a8f98', '#9a5b2e']
