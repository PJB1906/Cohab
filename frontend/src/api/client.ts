/** Thin fetch wrapper shared by every api/*.ts module. Cookie session auth
 * only (CLAUDE.md: never localStorage) — every call sends credentials so the
 * httpOnly session cookie rides along. `/api` is proxied to the backend in
 * dev (vite.config.ts) and served same-origin in prod. */

/** Turn any error body into a sentence a person can read. FastAPI's 422
 * `detail` is a list of `{loc, msg}` objects; printing that raw is what put
 * a block of JSON on screen in place of an error message. */
function readableDetail(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const parts = detail
      .map((d) => {
        if (!d || typeof d !== 'object') return null
        const { loc, msg } = d as { loc?: unknown[]; msg?: string }
        const field = Array.isArray(loc) ? loc.filter((x) => x !== 'body').join(' ').replace(/_/g, ' ') : ''
        const text = (msg ?? '').replace(/^Value error, /, '')
        return field ? `${field}: ${text}` : text
      })
      .filter(Boolean)
    if (parts.length) return `Please check: ${parts.join('; ')}`
  }
  if (detail && typeof detail === 'object') {
    const d = detail as { message?: unknown; problems?: unknown }
    if (typeof d.message === 'string') return d.message
    if (Array.isArray(d.problems)) return `Please check: ${d.problems.join('; ')}`
  }
  return 'Something went wrong. Please try again.'
}

export class ApiError extends Error {
  status: number
  /** The raw `detail` field from the response body, before string coercion.
   * Most endpoints return a plain string here, which is also `message`
   * unchanged. A few (e.g. chat's PII interrupt) return a structured object
   * a caller needs to branch on — `Error`'s constructor coerces whatever's
   * passed to `message` via ToString (so a plain object becomes the useless
   * "[object Object]"), so callers that need the real shape read `detail`
   * instead of `message`. */
  detail: unknown
  constructor(status: number, detail: unknown) {
    super(readableDetail(detail))
    this.status = status
    this.detail = detail
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`/api${path}`, {
      credentials: 'include',
      ...init,
      headers:
        init?.body instanceof FormData
          ? init.headers
          : { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    // Offline or server down: fetch rejects with a bare TypeError
    // ("Failed to fetch"), which is not something to show a person.
    throw new ApiError(0, "Can't reach Cohab right now. Check your connection and try again.")
  }

  if (!res.ok) {
    // Never show a raw status line or an HTML error page as the message.
    let detail: unknown =
      res.status >= 500 ? 'Cohab is having trouble right now. Please try again in a moment.' : res.statusText || 'Request failed'
    try {
      const body = await res.json()
      detail = body.detail ?? detail
    } catch {
      // no JSON body: keep the fallback above
    }
    throw new ApiError(res.status, detail)
  }

  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body !== undefined ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PUT', body: body !== undefined ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PATCH', body: body !== undefined ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  postForm: <T>(path: string, body: FormData) => request<T>(path, { method: 'POST', body }),
}
