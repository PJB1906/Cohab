import { api } from './client'
import type { ListingOut, ListingUpsertRequest } from './types'

export const listingApi = {
  get: () => api.get<ListingOut>('/listing'),
  put: (body: ListingUpsertRequest) => api.put<ListingOut>('/listing', body),
}
