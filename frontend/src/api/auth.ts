import { api } from './client'
import type {
  AccountUpdateRequest,
  LoginRequest,
  PasswordResetConfirm,
  RegisterRequest,
  RegisterResponse,
  ResendOtpRequest,
  UserOut,
  VerifyOtpRequest,
} from './types'

export const authApi = {
  register: (body: RegisterRequest) => api.post<RegisterResponse>('/auth/register', body),
  verify: (body: VerifyOtpRequest) => api.post<UserOut>('/auth/verify', body),
  resendOtp: (body: ResendOtpRequest) => api.post<RegisterResponse>('/auth/resend-otp', body),
  login: (body: LoginRequest) => api.post<UserOut>('/auth/login', body),
  logout: () => api.post<void>('/auth/logout'),
  requestPasswordReset: (email: string) => api.post<{ sent: boolean }>('/auth/password-reset/request', { email }),
  confirmPasswordReset: (body: PasswordResetConfirm) => api.post<UserOut>('/auth/password-reset/confirm', body),
  me: () => api.get<UserOut>('/auth/me'),
  updateMe: (body: AccountUpdateRequest) => api.patch<UserOut>('/auth/me', body),
}
