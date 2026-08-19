import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { chatApi } from '@/api/chat'
import { matchesApi } from '@/api/matches'
import { ApiError } from '@/api/client'
import { AppShell } from '@/components/AppShell'
import { Avatar } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'

/** Screen 10 (PRD §9): explicit mutual consent, with in-person meeting
 * guidance shown "at the moment of greatest practical risk" (PRD §10). */
export function ContactShare() {
  const { matchId } = useParams<{ matchId: string }>()
  const queryClient = useQueryClient()

  const { data: match } = useQuery({
    queryKey: ['match', matchId],
    queryFn: () => matchesApi.explanation(matchId!),
    enabled: Boolean(matchId),
  })

  const { data: status, isLoading, error } = useQuery({
    queryKey: ['chat', matchId, 'contact-status'],
    queryFn: () => chatApi.contactStatus(matchId!),
    enabled: Boolean(matchId),
  })

  const shareMutation = useMutation({
    mutationFn: () => chatApi.contactShare(matchId!),
    onSuccess: (updated) => {
      queryClient.setQueryData(['chat', matchId, 'contact-status'], updated)
    },
  })

  if (isLoading || !match) {
    return (
      <AppShell>
        <div className="max-w-md mx-auto px-4 py-10 text-cohab-muted">Loading…</div>
      </AppShell>
    )
  }

  if (error) {
    const notOpenYet = error instanceof ApiError && error.status === 409
    return (
      <AppShell>
        <div className="max-w-md mx-auto px-4 py-10 text-center">
          <p className="text-cohab-accent mb-4">
            {notOpenYet ? "Open chat with them before sharing contact details." : "Couldn't load this."}
          </p>
          {notOpenYet && (
            <Link to={`/matches/${matchId}/chat`}>
              <Button>Open chat</Button>
            </Link>
          )}
        </div>
      </AppShell>
    )
  }

  const bothShared = Boolean(status?.you_consented && status?.other_consented)

  return (
    <AppShell>
      <div className="max-w-md mx-auto px-4 py-8">
        <Link to={`/matches/${matchId}/chat`} className="text-[13px] font-medium text-cohab-primary">
          ← Back to chat
        </Link>

        <div className="flex flex-col items-center text-center mt-6 mb-6">
          <Avatar name={match.candidate_name} src={match.candidate_avatar_url} size={64} />
          <h1 className="text-xl font-semibold mt-3">Share contact with {match.candidate_name}</h1>
          <p className="text-[13.5px] text-cohab-muted mt-2 max-w-xs">
            Your phone number stays private until both of you opt in here.
          </p>
        </div>

        <div className="bg-white border border-cohab-border rounded-2xl p-5">
          <div className="flex items-center justify-between py-2">
            <span className="text-sm">You</span>
            <span className={status?.you_consented ? 'text-cohab-primary text-sm font-semibold' : 'text-cohab-subtle text-sm'}>
              {status?.you_consented ? 'Shared' : 'Not shared yet'}
            </span>
          </div>
          <div className="flex items-center justify-between py-2 border-t border-cohab-border-soft">
            <span className="text-sm">{match.candidate_name}</span>
            <span className={status?.other_consented ? 'text-cohab-primary text-sm font-semibold' : 'text-cohab-subtle text-sm'}>
              {status?.other_consented ? 'Shared' : 'Not shared yet'}
            </span>
          </div>

          {bothShared ? (
            <div className="mt-4 pt-4 border-t border-cohab-border-soft text-center">
              <p className="text-xs uppercase tracking-wide text-cohab-subtle font-mono mb-1">Their number</p>
              {status?.other_phone ? (
                <p className="text-lg font-semibold tabular-nums">{status.other_phone}</p>
              ) : (
                <p className="text-[13px] text-cohab-subtle">
                  They haven't added a phone number to their account yet.
                </p>
              )}
            </div>
          ) : (
            <Button
              onClick={() => shareMutation.mutate()}
              disabled={status?.you_consented || shareMutation.isPending}
              className="w-full mt-4"
            >
              {status?.you_consented ? 'Waiting for them…' : 'Share my contact details'}
            </Button>
          )}
        </div>

        {bothShared && (
          <div className="bg-cohab-tint border border-cohab-border rounded-2xl p-4 mt-4">
            <h2 className="text-sm font-semibold mb-1.5">Meeting for the first time?</h2>
            <p className="text-[13px] text-cohab-muted">
              Meet in a public place first, tell a friend where you're going, and video-call before
              agreeing to anything. Cohab can't verify what happens off-platform.
            </p>
          </div>
        )}
      </div>
    </AppShell>
  )
}
