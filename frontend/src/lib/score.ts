/** Score bands per the Prototype mockup's own key: Strong >=80, Good 65-79,
 * Fair <65 (docs/DECISIONS.md D-5.1) — combined_score arrives from the API
 * as a 0-1 float (spec §9's harmonic mean), displayed as a percentage. */

export type ScoreBandName = 'Strong' | 'Good' | 'Fair'

export function scorePercent(combinedScore: number): number {
  return Math.round(combinedScore * 100)
}

export function scoreBand(pct: number): ScoreBandName {
  if (pct >= 80) return 'Strong'
  if (pct >= 65) return 'Good'
  return 'Fair'
}

// Poster identity (D-14.23): a strong match earns the volt fill on its bar
// (volt's one role is "match moment"); the label text stays ink, because
// volt is never text on white. Good is plain ink, Fair is the warning tomato,
// so a weak match differs by hue and not only by bar length.
export const BAND_COLOR: Record<ScoreBandName, string> = {
  Strong: 'var(--color-cohab-ink)',
  Good: 'var(--color-cohab-subtle)',
  Fair: 'var(--color-cohab-accent)',
}

// Static literal classes so Tailwind's scanner can see them at build time.
export const BAND_BAR_CLASS: Record<ScoreBandName, string> = {
  Strong: 'bg-cohab-volt ring-1 ring-inset ring-cohab-ink',
  Good: 'bg-cohab-ink',
  Fair: 'bg-cohab-accent',
}
