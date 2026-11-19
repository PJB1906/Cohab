import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { evidenceApi, type Playground as PG, type PlaygroundCandidate } from '@/api/v2'
import { AppShell } from '@/components/AppShell'
import { Button } from '@/components/ui/button'
import { attributeLabel } from '@/data/attributes'
import { cn } from '@/lib/utils'

const MULTIPLIER = 1.5

/** Mirrors cohab/services/matching/scoring.py `blend` exactly, including its
 * degenerate-case fallback. Checked against the server by the "Verify"
 * button and by tests/api/test_showcase.py. */
function blend(defaults: Record<string, number>, important: string[]): Record<string, number> {
  const imp = new Set(important)
  const boosted: Record<string, number> = {}
  for (const [k, w] of Object.entries(defaults)) boosted[k] = imp.has(k) ? w * MULTIPLIER : w
  const sel = Object.entries(boosted).filter(([k]) => imp.has(k)).reduce((s, [, w]) => s + w, 0)
  const rest = Object.entries(boosted).filter(([k]) => !imp.has(k)).reduce((s, [, w]) => s + w, 0)
  if (rest <= 0 || sel >= 1) {
    const total = Object.values(boosted).reduce((s, w) => s + w, 0) || 1
    return Object.fromEntries(Object.entries(boosted).map(([k, w]) => [k, w / total]))
  }
  const scale = (1 - sel) / rest
  return Object.fromEntries(Object.entries(boosted).map(([k, w]) => [k, imp.has(k) ? w : w * scale]))
}

function harmonic(a: number, b: number): number {
  return a + b === 0 ? 0 : (2 * a * b) / (a + b)
}

function score(c: PlaygroundCandidate, subjectImportant: string[], weights: Record<string, number>) {
  const wa = blend(weights, subjectImportant)
  const wb = blend(weights, c.important)
  const ta = c.present.reduce((s, n) => s + (wa[n] ?? 0), 0) || 1
  const tb = c.present.reduce((s, n) => s + (wb[n] ?? 0), 0) || 1
  const sab = c.present.reduce((s, n) => s + ((wa[n] ?? 0) / ta) * c.sim_to[n], 0)
  const sba = c.present.reduce((s, n) => s + ((wb[n] ?? 0) / tb) * c.sim_from[n], 0)
  // The attribute this candidate most gains/loses from the current weights,
  // relative to the defaults, explains its movement.
  return { combined: harmonic(sab, sba), sab, sba }
}

function normalise(w: Record<string, number>): Record<string, number> {
  const t = Object.values(w).reduce((s, v) => s + v, 0) || 1
  return Object.fromEntries(Object.entries(w).map(([k, v]) => [k, v / t]))
}

export function PlaygroundPage() {
  const [seed, setSeed] = useState(7)
  const { data } = useQuery({ queryKey: ['evidence', 'playground', seed], queryFn: () => evidenceApi.playground(seed) })
  return (
    <AppShell>
      <div className="max-w-[1400px] mx-auto px-4 cohab-desktop:px-6 py-7 pb-14">
        <div className="flex flex-wrap items-end justify-between gap-3 mb-1">
          <h1 className="poster text-[64px]">Policy playground</h1>
          <Link to="/evidence" className="text-[13.5px] font-medium text-cohab-primary">
            ← Evidence
          </Link>
        </div>
        <p className="text-[13.5px] leading-[1.55] text-cohab-muted mb-5 max-w-[820px]">
          Move a weight and watch one person's shortlist reorder. Every score is the same arithmetic the matcher runs:
          per-attribute scores in both directions, each person's "top 3" boost, renormalisation, harmonic mean. The
          population is <strong>synthetic</strong>, generated from the seed distribution; no member's answers are used.
        </p>
        {data ? <Board key={`${data.seed}-${data.subject}`} pg={data} onReseed={() => setSeed((s) => s + 1)} /> : <p className="text-cohab-muted">Loading…</p>}
      </div>
    </AppShell>
  )
}

function Board({ pg, onReseed }: { pg: PG; onReseed: () => void }) {
  const [weights, setWeights] = useState<Record<string, number>>(pg.weights)
  const norm = useMemo(() => normalise(weights), [weights])

  const baseline = useMemo(() => {
    const scored = pg.candidates.map((c) => ({ c, ...score(c, pg.subject_important, normalise(pg.weights)) }))
    scored.sort((a, b) => b.combined - a.combined)
    return new Map(scored.map((s, i) => [s.c.index, i]))
  }, [pg])

  const ranked = useMemo(() => {
    const scored = pg.candidates.map((c) => ({ c, ...score(c, pg.subject_important, norm) }))
    scored.sort((a, b) => b.combined - a.combined)
    return scored
  }, [pg, norm])

  const verify = useMutation({ mutationFn: () => evidenceApi.rank(pg.seed, pg.subject, norm) })
  const clientTop = ranked.slice(0, 10).map((r) => r.c.index)
  const loaded = new Set(pg.candidates.map((c) => c.index))
  const verdict = verify.data
    ? verify.data.top10.every((i) => loaded.has(i))
      ? verify.data.top10.join() === clientTop.join()
        ? 'match'
        : 'differ'
      : 'outside'
    : null

  const changed = Object.keys(weights).some((k) => Math.abs(norm[k] - pg.weights[k]) > 1e-6)

  return (
    <div className="grid gap-5 cohab-desktop:grid-cols-[360px_1fr] items-start">
      <aside className="bg-cohab-card border border-cohab-border rounded-2xl p-5 cohab-desktop:sticky cohab-desktop:top-[88px]">
        <div className="flex items-baseline justify-between mb-3">
          <h2 className="text-[15px] font-semibold">Weights</h2>
          <button type="button" className="text-xs font-medium text-cohab-primary cursor-pointer" onClick={() => setWeights(pg.weights)}>
            Reset to active set
          </button>
        </div>
        <div className="flex flex-col gap-2.5">
          {pg.attributes.map((a) => (
            <label key={a} className="grid grid-cols-[120px_1fr_44px] items-center gap-2 text-[12.5px]">
              <span className={cn('truncate', pg.subject_important.includes(a) && 'font-semibold text-cohab-ink')} title={attributeLabel(a)}>
                {attributeLabel(a)}
              </span>
              <input
                type="range"
                min={0}
                max={0.4}
                step={0.005}
                value={weights[a]}
                onChange={(e) => setWeights((w) => ({ ...w, [a]: Number(e.target.value) }))}
                className="w-full accent-[var(--color-cohab-primary)]"
              />
              <span className="tabular-nums text-right text-cohab-muted">{(norm[a] * 100).toFixed(1)}%</span>
            </label>
          ))}
        </div>
        <p className="text-[11.5px] text-cohab-subtle mt-3">
          Bold = this person's own "top 3", boosted 1.5×. Percentages are after renormalising to 100%.
        </p>
        <div className="border-t border-cohab-border-soft mt-4 pt-4 flex flex-col gap-2">
          <Button size="sm" variant="secondary" onClick={() => verify.mutate()} disabled={verify.isPending}>
            Verify against the server matcher
          </Button>
          {verdict === 'match' && <p className="text-[12px] text-cohab-primary">✓ Server top 10 is identical to this page's.</p>}
          {verdict === 'differ' && <p className="text-[12px] text-cohab-accent">Server order differs: {verify.data!.top10.join(', ')}</p>}
          {verdict === 'outside' && (
            <p className="text-[12px] text-cohab-muted">Server's new top 10 includes people outside the 25 loaded here (not a mismatch).</p>
          )}
          <Button size="sm" variant="ghost" onClick={onReseed}>
            Try another synthetic population
          </Button>
        </div>
      </aside>

      <section>
        <p className="text-[13px] text-cohab-muted mb-3">
          Person {String(pg.subject).padStart(3, '0')}'s shortlist · {pg.candidates.length} highest under the active weights
          {changed ? ', re-ranked live' : ''}
        </p>
        <ol className="flex flex-col gap-2">
          {ranked.slice(0, 15).map((r, i) => {
            const before = baseline.get(r.c.index) ?? i
            const move = before - i
            return (
              <li
                key={r.c.index}
                className={cn(
                  'grid grid-cols-[28px_1fr_auto] items-center gap-3 bg-cohab-card border rounded-xl px-3.5 py-2.5 transition-colors',
                  i < 10 ? 'border-cohab-border' : 'border-cohab-border-soft opacity-70',
                )}
              >
                <span className="text-[13px] tabular-nums text-cohab-subtle">{i + 1}</span>
                <div className="min-w-0">
                  <div className="text-[13.5px] font-medium">{r.c.label}</div>
                  <div className="text-[11.5px] text-cohab-subtle tabular-nums">
                    you→them {r.sab.toFixed(3)} · them→you {r.sba.toFixed(3)}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-[15px] font-semibold tabular-nums">{r.combined.toFixed(3)}</div>
                  <div className={cn('text-[11.5px] tabular-nums', move > 0 ? 'text-cohab-primary' : move < 0 ? 'text-cohab-accent' : 'text-cohab-subtle')}>
                    {move > 0 ? `▲ ${move}` : move < 0 ? `▼ ${-move}` : '—'}
                  </div>
                </div>
              </li>
            )
          })}
        </ol>
        <p className="text-[11.5px] text-cohab-subtle mt-3">
          Only candidates who pass every hard constraint appear here; no weight can bring in someone Stage 1 excluded.
        </p>
      </section>
    </div>
  )
}
