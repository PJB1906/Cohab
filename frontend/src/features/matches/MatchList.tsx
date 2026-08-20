import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { matchesApi } from '@/api/matches'
import { feedbackApi } from '@/api/feedback'
import { MatchCard } from './MatchCard'
import { AppShell } from '@/components/AppShell'

export function MatchList() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['matches'],
    queryFn: () => matchesApi.list(),
  })

  const { data: pending } = useQuery({
    queryKey: ['feedback', 'pending'],
    queryFn: () => feedbackApi.pending(),
  })

  return (
    <AppShell>
      <div className="max-w-2xl mx-auto px-4 py-7">
        <h1 className="text-2xl font-semibold tracking-tight mb-1">
          {data ? `${data.length} ${data.length === 1 ? 'match' : 'matches'}` : 'Your matches'}
        </h1>
        <p className="text-[13.5px] text-cohab-muted mb-6">
          Ranked by compatibility computed in both directions. Every card shows the strongest
          agreements and the single largest difference. A score is not a recommendation to move
          in — it's a shortlist.
        </p>

        {pending && pending.length > 0 && (
          <div className="bg-cohab-tint border border-cohab-primary rounded-2xl p-4 mb-6">
            <p className="text-[13.5px] font-medium text-cohab-ink mb-2">
              {pending.length === 1 ? 'One match is' : `${pending.length} matches are`} waiting on your
              feedback.
            </p>
            <div className="flex flex-col gap-1.5">
              {pending.map((p) => (
                <Link
                  key={p.match_id}
                  to={`/matches/${p.match_id}`}
                  className="text-[13px] text-cohab-primary font-medium"
                >
                  How did it go with {p.other_user_name}? →
                </Link>
              ))}
            </div>
          </div>
        )}

        {isLoading && <p className="text-cohab-muted">Loading…</p>}
        {error && <p className="text-cohab-accent">Couldn't load your matches. Try again shortly.</p>}
        {data && data.length === 0 && (
          <p className="text-cohab-muted">
            No matches yet — once more verified profiles join your area, they'll show up here.
          </p>
        )}

        <div className="flex flex-col gap-3">
          {data?.map((item) => (
            <MatchCard key={item.match_id} item={item} />
          ))}
        </div>
      </div>
    </AppShell>
  )
}
