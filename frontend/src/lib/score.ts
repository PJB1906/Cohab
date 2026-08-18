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

// Colours beyond "Strong" are a UI extrapolation, not sourced from either
// mockup — the mockups only ever showed the Strong (primary) and Good
// (muted sage) bars.
export const BAND_COLOR: Record<ScoreBandName, string> = {
  Strong: '#0f5f52',
  Good: '#7d9c92',
  Fair: '#a8442a',
}

// Static literal classes (not built from BAND_COLOR) so Tailwind's scanner
// can see them at build time — arbitrary-value classes assembled from a JS
// variable at runtime won't be generated.
export const BAND_BAR_CLASS: Record<ScoreBandName, string> = {
  Strong: 'bg-[#0f5f52]',
  Good: 'bg-[#7d9c92]',
  Fair: 'bg-[#a8442a]',
}
