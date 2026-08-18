/** Thin fetch wrapper shared by every api/*.ts module. Cookie session auth
 * only (CLAUDE.md: never localStorage) — every call sends credentials so the
 * httpOnly session cookie rides along. `/api` is proxied to the backend in
 * dev (vite.config.ts) and served same-origin in prod. */

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
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
  postForm: <T>(path: string, body: FormData) => request<T>(path, { method: 'POST', body }),
}
