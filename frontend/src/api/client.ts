/** Thin fetch wrapper shared by every api/*.ts module. Cookie session auth
 * only (CLAUDE.md: never localStorage) — every call sends credentials so the
 * httpOnly session cookie rides along. `/api` is proxied to the backend in
 * dev (vite.config.ts) and served same-origin in prod. */

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
    super(typeof detail === 'string' ? detail : JSON.stringify(detail))
    this.status = status
    this.detail = detail
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    credentials: 'include',
    ...init,
    headers:
      init?.body instanceof FormData
        ? init.headers
        : { 'Content-Type': 'application/json', ...init?.headers },
  })

  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? detail
    } catch {
      // no JSON body — keep statusText
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
