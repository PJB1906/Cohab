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

// Daylight (D-14.24): strength of fit is a cobalt ramp (strong solid, good a
// lighter blue), and a weak match is coral, so Fair differs by hue and not only
// by bar length. Sun is reserved for the big score moment, never a bar.
export const BAND_COLOR: Record<ScoreBandName, string> = {
  Strong: 'var(--color-cohab-primary)',
  Good: 'var(--color-cohab-subtle)',
  Fair: 'var(--color-cohab-accent)',
}

// Static literal classes so Tailwind's scanner can see them at build time.
export const BAND_BAR_CLASS: Record<ScoreBandName, string> = {
  Strong: 'bg-cohab-primary',
  Good: 'bg-cohab-sky',
  Fair: 'bg-cohab-accent',
}
