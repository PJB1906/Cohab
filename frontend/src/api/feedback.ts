import { api } from './client'
import type { FeedbackOut, FeedbackRequest, PendingFeedbackOut } from './types'

export const feedbackApi = {
  submit: (matchId: string, body: FeedbackRequest) => api.post<FeedbackOut>(`/matches/${matchId}/feedback`, body),
  pending: () => api.get<PendingFeedbackOut[]>('/feedback/pending'),
}
