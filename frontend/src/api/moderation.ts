import { api } from './client'
import type { ReportDetailOut, ReportSummaryOut, ResolveReportRequest } from './types'

export const moderationApi = {
  listReports: (reportStatus?: string) =>
    api.get<ReportSummaryOut[]>(
      `/moderation/reports${reportStatus ? `?report_status=${encodeURIComponent(reportStatus)}` : ''}`,
    ),
  getReport: (reportId: string) => api.get<ReportDetailOut>(`/moderation/reports/${reportId}`),
  claim: (reportId: string) => api.post<ReportDetailOut>(`/moderation/reports/${reportId}/claim`),
  resolve: (reportId: string, body: ResolveReportRequest) =>
    api.post<ReportDetailOut>(`/moderation/reports/${reportId}/resolve`, body),
}
