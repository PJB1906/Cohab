/** v2 API surface: match insights, evidence page, playground, and the
 * anonymous study endpoints. Product calls go through the cookie client;
 * study calls carry an `X-Study-Token` header instead (no product account). */
import { api, ApiError } from './client'

// --- match insights ----------------------------------------------------------

export interface PoolReason {
  reason: string
  label: string
  count: number
}

export interface PoolSuggestion {
  kind: string
  label: string
  adds: number
}

export interface MatchInsights {
  pool: {
    eligible: number
    considered: number
    excluded_by_reason: PoolReason[]
    suggestions: PoolSuggestion[]
  } | null
  tie_hint: {
    tied: boolean
    set_overlap: number | null
    order_change: number | null
    method: string | null
    top3_candidate_ids: string[]
  } | null
  calibration: { active: boolean; version: number | null; data_source: string | null; target: string | null } | null
}

export const insightsApi = {
  get: () => api.get<MatchInsights>('/matches/insights'),
}

// --- evidence ----------------------------------------------------------------

export type DataSource = 'real' | 'dryrun' | 'simulation' | 'public'

export interface AnalysisRecord<T = Record<string, unknown>> {
  kind: string
  data_source: DataSource
  created_at: string
  provenance: Record<string, unknown>
  payload: T
}

export interface PlaygroundCandidate {
  index: number
  label: string
  important: string[]
  present: string[]
  sim_to: Record<string, number>
  sim_from: Record<string, number>
}

export interface Playground {
  seed: number
  subject: number
  subject_important: string[]
  attributes: string[]
  weights: Record<string, number>
  candidates: PlaygroundCandidate[]
  server_top10: number[]
  data_source: string
}

export const evidenceApi = {
  summary: () => api.get<Record<string, AnalysisRecord>>('/evidence/summary'),
  playground: (seed = 7, subject?: number) =>
    api.get<Playground>(`/evidence/playground?seed=${seed}${subject !== undefined ? `&subject=${subject}` : ''}`),
  rank: (seed: number, subject: number, weights: Record<string, number>) =>
    api.post<{ top10: number[]; scores: number[] }>('/evidence/playground/rank', { seed, subject, weights }),
}

// --- study (anonymous, token header) ----------------------------------------------

export interface StudyInstrument {
  open: boolean
  consent_version: string
  pair_consent_version: string
  rater_fields: string[]
  card_fields: string[]
  study_attributes: string[]
  gameable_fields: string[]
  outcome_items: Record<string, string>
}

export interface StudyProgress {
  answered: number
  total: number
  consented: boolean
  profile_done: boolean
  completed: boolean
}

export interface StudyCard {
  id: string
  answers: Record<string, string>
}

export interface StudyTrial {
  trial_id: string
  kind: 'pair' | 'repeat' | 'attention' | 'rank'
  cards: StudyCard[]
}

async function studyRequest<T>(path: string, token: string | null, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`/api/study${path}`, {
      ...init,
      credentials: 'omit',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'X-Study-Token': token } : {}),
      },
    })
  } catch {
    throw new ApiError(0, "Can't reach Cohab right now. Check your connection and try again.")
  }
  if (!res.ok) {
    let detail: unknown =
      res.status >= 500 ? 'Cohab is having trouble right now. Please try again in a moment.' : res.statusText || 'Request failed'
    try {
      detail = (await res.json()).detail ?? detail
    } catch {
      // keep statusText
    }
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

const json = (body: unknown) => JSON.stringify(body)

export const studyApi = {
  instrument: () => studyRequest<StudyInstrument>('/instrument', null),
  createRater: (cohort = 'main') =>
    studyRequest<{ token: string }>('/lab/raters', null, { method: 'POST', body: json({ cohort }) }),
  consent: (token: string, version: string) =>
    studyRequest<StudyProgress>('/lab/consent', token, { method: 'POST', body: json({ consent_version: version }) }),
  saveProfile: (token: string, answers: Record<string, string>, important: string[]) =>
    studyRequest<StudyProgress>('/lab/profile', token, {
      method: 'PUT',
      body: json({ answers, important_attributes: important }),
    }),
  next: (token: string) =>
    studyRequest<{ trial: StudyTrial | null; progress: StudyProgress }>('/lab/next', token),
  respond: (token: string, trialId: string, body: Record<string, unknown>) =>
    studyRequest<StudyProgress>(`/lab/trials/${trialId}/response`, token, { method: 'POST', body: json(body) }),
  withdraw: (token: string) => studyRequest<void>('/lab/me', token, { method: 'DELETE' }),
  createPair: () => studyRequest<{ token: string; invite_token: string }>('/pairs', null, { method: 'POST' }),
  joinPair: (invite: string) =>
    studyRequest<{ token: string }>('/pairs/join', null, { method: 'POST', body: json({ invite_token: invite }) }),
  submitPair: (token: string, body: Record<string, unknown>) =>
    studyRequest<PairStatus>('/pairs/me', token, { method: 'PUT', body: json(body) }),
  pairStatus: (token: string) => studyRequest<PairStatus>('/pairs/me', token),
}

export interface PairStatus {
  role: string
  submitted: boolean
  roommate_joined: boolean
  roommate_submitted: boolean
}

/** The study token resumes a session. It identifies nothing but anonymous
 * study answers, so it lives in sessionStorage (cleared with the tab), and
 * the page shows it as a resume code the participant can copy — never in a
 * URL query string, which would reach server logs (docs/DECISIONS.md D-14.11). */
export const studyToken = {
  get: (key: string): string | null => {
    try {
      return sessionStorage.getItem(`cohab-study-${key}`)
    } catch {
      return null
    }
  },
  set: (key: string, value: string) => {
    try {
      sessionStorage.setItem(`cohab-study-${key}`, value)
    } catch {
      // private mode: the resume code on screen still works
    }
  },
  clear: (key: string) => {
    try {
      sessionStorage.removeItem(`cohab-study-${key}`)
    } catch {
      // ignore
    }
  },
}

// --- taste learning (D-14.22) -----------------------------------------------------

export interface TasteWeight {
  attribute: string
  label: string
  stated: number
  learned: number
  shift: number
}

export interface Taste {
  enabled: boolean
  active: boolean
  decisions: number
  positives: number
  negatives: number
  needed: number
  weights: TasteWeight[]
  insights: { attribute: string; direction: 'up' | 'down'; text: string }[]
}

export const tasteApi = {
  get: () => api.get<Taste>('/me/taste'),
  set: (enabled: boolean) => api.put<Taste>('/me/taste', { enabled }),
}
