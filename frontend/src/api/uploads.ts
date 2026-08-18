import { api } from './client'
import type { UploadImageResponse } from './types'

export type UploadKind = 'avatar' | 'listing'

export const uploadsApi = {
  image: (file: File, kind: UploadKind) => {
    const form = new FormData()
    form.append('kind', kind)
    form.append('file', file)
    return api.postForm<UploadImageResponse>('/uploads/image', form)
  },
}
