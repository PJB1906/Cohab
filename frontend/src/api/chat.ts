import { api, ApiError } from './client'
import type { ChatMessage, ContactStatus, PiiWarning } from './types'

/** The PII interrupt (cohab/api/chat.py: 422 `{"detail": "pii_detected",
 * "message": "..."}`) is the one error shape the UI has to act on
 * specifically — `ApiError.detail` carries the server's JSON body's
 * `detail` field verbatim (see client.ts), which for this endpoint is that
 * structured object rather than a plain string. `send()` recognises it here
 * and re-throws a typed error so `ChatThread` can render the interrupt
 * dialog instead of a generic error toast. */
export class PiiInterruptError extends Error {
  warning: PiiWarning
  constructor(warning: PiiWarning) {
    super(warning.message)
    this.warning = warning
  }
}

function isPiiWarning(value: unknown): value is PiiWarning {
  return Boolean(value) && typeof value === 'object' && (value as PiiWarning).detail === 'pii_detected'
}

export const chatApi = {
  list: (matchId: string, since?: string) =>
    api.get<ChatMessage[]>(
      `/chat/${matchId}/messages${since ? `?since=${encodeURIComponent(since)}` : ''}`,
    ),
  send: async (matchId: string, body: string, confirm = false): Promise<ChatMessage> => {
    try {
      return await api.post<ChatMessage>(`/chat/${matchId}/messages`, { body, confirm })
    } catch (err) {
      if (err instanceof ApiError && err.status === 422 && isPiiWarning(err.detail)) {
        throw new PiiInterruptError(err.detail)
      }
      throw err
    }
  },
  contactStatus: (matchId: string) => api.get<ContactStatus>(`/chat/${matchId}/contact-status`),
  contactShare: (matchId: string) => api.post<ContactStatus>(`/chat/${matchId}/contact-share`),
  withdrawContactShare: (matchId: string) => api.delete<ContactStatus>(`/chat/${matchId}/contact-share`),
}
