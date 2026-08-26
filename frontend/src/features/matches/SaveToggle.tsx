import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { savedApi } from '@/api/saved'
import { cn } from '@/lib/utils'

/** Filled/outline bookmark, cross-referenced against `GET /saved` client-side
 * (no `is_saved` flag on `MatchListItem`/`MatchExplanationResponse` yet — a
 * documented judgment call, see SavedList.tsx). Stops propagation because
 * every caller sits inside a `<Link>` card. */
export function SaveToggle({ matchId, className }: { matchId: string; className?: string }) {
  const queryClient = useQueryClient()
  const { data: saved } = useQuery({ queryKey: ['saved'], queryFn: () => savedApi.list() })
  const isSaved = saved?.some((s) => s.match.match_id === matchId) ?? false

  const mutation = useMutation({
    mutationFn: async () => {
      if (isSaved) await savedApi.unsave(matchId)
      else await savedApi.save(matchId)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['saved'] })
      queryClient.invalidateQueries({ queryKey: ['matches'] })
    },
  })

  return (
    <button
      type="button"
      onClick={(e) => {
        e.preventDefault()
        e.stopPropagation()
        mutation.mutate()
      }}
      disabled={mutation.isPending}
      aria-label={isSaved ? 'Remove from saved matches' : 'Save this match'}
      aria-pressed={isSaved}
      className={cn(
        'cohab-press flex items-center justify-center rounded-full cursor-pointer disabled:opacity-50 transition-colors',
        isSaved ? 'text-cohab-primary' : 'text-cohab-subtle hover:text-cohab-ink',
        className,
      )}
    >
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        // `currentColor` rather than literals: the old `#7fee64` was the
        // dark-theme lime and stayed lime on the light theme's beige, where
        // it barely reads (D-13.16). Colour now comes from the class below,
        // so it follows the theme tokens like everything else.
        fill={isSaved ? 'currentColor' : 'none'}
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinejoin="round"
      >
        <path d="M6.5 4.5h11v15l-5.5-3.8-5.5 3.8z" />
      </svg>
    </button>
  )
}
