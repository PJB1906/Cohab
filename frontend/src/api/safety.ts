import { api } from './client'
import type { ReportOut, ReportRequest } from './types'

export const safetyApi = {
  fileReport: (body: ReportRequest) => api.post<ReportOut>('/reports', body),
  block: (blockedId: string) => api.post<void>('/blocks', { blocked_id: blockedId }),
  unblock: (blockedId: string) => api.delete<void>(`/blocks/${blockedId}`),
  listBlocks: () => api.get<string[]>('/blocks'),
}
