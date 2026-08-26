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

// The *thresholds* above stay mockup-sourced (Cohab Prototype.html states the
// legend verbatim: "Strong 80+ · Good 65-79 · Fair below 65"). The colours no
// longer are — D-13.2 replaced the mockup palette with Modal's, so a band now
// reads: Strong = Lime Pulse (the rationed accent, earned by the top band),
// Good = Sage 60, Fair = the desaturated brick kept as the one non-green
// signal so a weak match is distinguishable from a strong one by hue and not
// only by bar length.
export const BAND_COLOR: Record<ScoreBandName, string> = {
  Strong: '#7fee64',
  Good: '#8cab87',
  Fair: '#c96a4d',
}

// Static literal classes (not built from BAND_COLOR) so Tailwind's scanner
// can see them at build time — arbitrary-value classes assembled from a JS
// variable at runtime won't be generated.
export const BAND_BAR_CLASS: Record<ScoreBandName, string> = {
  Strong: 'bg-[#7fee64]',
  Good: 'bg-[#8cab87]',
  Fair: 'bg-[#c96a4d]',
}
