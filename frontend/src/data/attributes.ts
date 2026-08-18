/** Display metadata for the `breakdown` keys `GET /matches/{id}/explanation`
 * returns — mirrors `attributes.py`'s `ATTRIBUTES` registry (name, type).
 * The API exposes only computed `sim_a`/`sim_b` per attribute, not either
 * party's raw questionnaire answer, so the full breakdown renders scores,
 * not a "you said X / they said Y" comparison — that level of detail only
 * exists for the top-3-agreements + 1-divergence the API already renders as
 * finished sentences (`agreements`/`divergence`). */

export type AttributeType = 'similarity' | 'tolerance' | 'absolute' | 'continuous' | 'semantic'

export const ATTRIBUTE_META: Record<string, { label: string; type: AttributeType }> = {
  cleanliness_level: { label: 'Cleanliness', type: 'similarity' },
  chore_approach: { label: 'Chore approach', type: 'similarity' },
  sharing_norm: { label: 'Sharing things', type: 'tolerance' },
  sleep_schedule: { label: 'Sleep schedule', type: 'similarity' },
  noise: { label: 'Noise', type: 'tolerance' },
  guests: { label: 'Guests', type: 'tolerance' },
  payment_reliability: { label: 'Paying on time', type: 'absolute' },
  cost_split_preference: { label: 'Splitting costs', type: 'similarity' },
  communication_style: { label: 'Communication', type: 'similarity' },
  budget_proximity: { label: 'Budget', type: 'continuous' },
  diet: { label: 'Diet', type: 'similarity' },
  nonveg_cooking: { label: 'Non-veg cooking', type: 'tolerance' },
  smoking: { label: 'Smoking', type: 'tolerance' },
  alcohol: { label: 'Alcohol', type: 'tolerance' },
  life_stage: { label: 'Life stage', type: 'similarity' },
  daytime_presence: { label: 'Daytime presence', type: 'similarity' },
  home_orientation: { label: 'Time at home', type: 'similarity' },
  sociability: { label: 'Sociability', type: 'similarity' },
  interests: { label: 'Interests', type: 'similarity' },
  lifestyle_notes: { label: 'Lifestyle notes', type: 'semantic' },
}

export function attributeLabel(key: string): string {
  return ATTRIBUTE_META[key]?.label ?? key
}

export function attributeType(key: string): AttributeType | null {
  return ATTRIBUTE_META[key]?.type ?? null
}
