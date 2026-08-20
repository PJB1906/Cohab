import { api } from './client'
import type { ExpressInterestResponse, MatchExplanationResponse, MatchListItem } from './types'

export const matchesApi = {
  list: () => api.get<MatchListItem[]>('/matches'),
  explanation: (matchId: string) => api.get<MatchExplanationResponse>(`/matches/${matchId}/explanation`),
  expressInterest: (matchId: string) => api.post<ExpressInterestResponse>(`/matches/${matchId}/interest`),
  confirmMoveIn: (matchId: string) => api.post<ExpressInterestResponse>(`/matches/${matchId}/confirm-move-in`),
  reject: (matchId: string) => api.post<ExpressInterestResponse>(`/matches/${matchId}/reject`),
}
