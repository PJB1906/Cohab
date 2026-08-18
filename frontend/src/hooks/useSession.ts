import { useQuery, useQueryClient } from '@tanstack/react-query'
import { authApi } from '@/api/auth'
import { ApiError } from '@/api/client'
import type { UserOut } from '@/api/types'

export const SESSION_QUERY_KEY = ['session'] as const

export function useSession() {
  const query = useQuery<UserOut | null>({
    queryKey: SESSION_QUERY_KEY,
    queryFn: async () => {
      try {
        return await authApi.me()
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null
        throw e
      }
    },
    retry: false,
    staleTime: 60_000,
  })
  return query
}

export function useSetSession() {
  const queryClient = useQueryClient()
  return (user: UserOut | null) => queryClient.setQueryData(SESSION_QUERY_KEY, user)
}
