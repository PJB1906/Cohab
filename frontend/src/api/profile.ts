import { api } from './client'
import type { ProfileOut, ProfileUpsertRequest } from './types'

export const profileApi = {
  get: () => api.get<ProfileOut>('/profile'),
  put: (body: ProfileUpsertRequest) => api.put<ProfileOut>('/profile', body),
}
