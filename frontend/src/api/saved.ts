import { api } from './client'
import type { MatchListItem, SavedMatchOut } from './types'

export const savedApi = {
  list: () => api.get<SavedMatchOut[]>('/saved'),
  save: (matchId: string) => api.post<MatchListItem>(`/saved/${matchId}`),
  unsave: (matchId: string) => api.delete<void>(`/saved/${matchId}`),
}
