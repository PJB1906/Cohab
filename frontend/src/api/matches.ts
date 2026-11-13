import { api } from './client'
import type { ExpressInterestResponse, MatchExplanationResponse, MatchListItem } from './types'

export type RejectionReason =
  | 'not_interested'
  | 'budget'
  | 'location'
  | 'lifestyle'
  | 'schedule'
  | 'found_elsewhere'
  | 'safety'
  | 'other'

export const matchesApi = {
  list: () => api.get<MatchListItem[]>('/matches'),
  explanation: (matchId: string) => api.get<MatchExplanationResponse>(`/matches/${matchId}/explanation`),
  expressInterest: (matchId: string) => api.post<ExpressInterestResponse>(`/matches/${matchId}/interest`),
  confirmMoveIn: (matchId: string) => api.post<ExpressInterestResponse>(`/matches/${matchId}/confirm-move-in`),
  reject: (matchId: string, reason?: RejectionReason) =>
    api.post<ExpressInterestResponse>(`/matches/${matchId}/reject`, reason ? { reason } : undefined),
}
