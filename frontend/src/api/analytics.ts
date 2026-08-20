import { api } from './client'
import type { AnalyticsSummaryOut } from './types'

export const analyticsApi = {
  summary: () => api.get<AnalyticsSummaryOut>('/analytics/summary'),
}
