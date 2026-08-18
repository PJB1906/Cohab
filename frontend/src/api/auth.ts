import { api } from './client'
import type { LoginRequest, RegisterRequest, RegisterResponse, UserOut, VerifyOtpRequest } from './types'

export const authApi = {
  register: (body: RegisterRequest) => api.post<RegisterResponse>('/auth/register', body),
  verify: (body: VerifyOtpRequest) => api.post<UserOut>('/auth/verify', body),
  login: (body: LoginRequest) => api.post<UserOut>('/auth/login', body),
  logout: () => api.post<void>('/auth/logout'),
  me: () => api.get<UserOut>('/auth/me'),
}
