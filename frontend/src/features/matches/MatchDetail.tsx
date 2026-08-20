import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { matchesApi } from '@/api/matches'
import { feedbackApi } from '@/api/feedback'
import { AppShell } from '@/components/AppShell'
import { Avatar } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { AttributeRow } from '@/components/AttributeRow'
import { SafetyActions } from '@/features/safety/SafetyActions'
import { FeedbackDialog } from './FeedbackDialog'
import { RejectConfirmDialog } from './RejectConfirmDialog'
import { scorePercent, scoreBand, BAND_COLOR } from '@/lib/score'
import type { PendingFeedbackOut } from '@/api/types'

export function MatchDetail() {
  const { matchId } = useParams<{ matchId: string }>()
  const queryClient = useQueryClient()
  // Captured once, on click, rather than read live from `pendingHere` on
  // every render — the dialog's own onSuccess strips this match from the
  // ['feedback', 'pending'] cache, which would otherwise make `pendingHere`
  // go undefined and unmount the dialog before its "Thanks" success screen
  // ever painted (found live: the dialog vanished the instant Submit was
  // clicked, no success state visible).
  const [feedbackTarget, setFeedbackTarget] = useState<PendingFeedbackOut | null>(null)
  const [showReject, setShowReject] = useState(false)

  const { data, isLoading, error } = useQuery({
    queryKey: ['match', matchId],
    queryFn: () => matchesApi.explanation(matchId!),
    enabled: Boolean(matchId),
  })

  const { data: pending } = useQuery({
    queryKey: ['feedback', 'pending'],
    queryFn: () => feedbackApi.pending(),
  })
  const pendingHere = pending?.find((p) => p.match_id === matchId)

  const interestMutation = useMutation({
    mutationFn: () => matchesApi.expressInterest(matchId!),
    onSuccess: (res) => {
      queryClient.setQueryData(['match', matchId], (prev: typeof data) =>
        prev ? { ...prev, state: res.state, you_expressed_interest: true } : prev,
      )
    },
  })

  const confirmMoveInMutation = useMutation({
    mutationFn: () => matchesApi.confirmMoveIn(matchId!),
    onSuccess: (res) => {
      queryClient.setQueryData(['match', matchId], (prev: typeof data) => (prev ? { ...prev, state: res.state } : prev))
      queryClient.invalidateQueries({ queryKey: ['feedback', 'pending'] })
    },
  })

  if (isLoading) {
    return (
      <AppShell>
        <div className="max-w-2xl mx-auto px-4 py-10 text-cohab-muted">Loading…</div>
      </AppShell>
    )
  }

  if (error || !data) {
    return (
      <AppShell>
        <div className="max-w-2xl mx-auto px-4 py-10 text-cohab-accent">Couldn't load this match.</div>
      </AppShell>
    )
  }

  const pct = scorePercent(data.combined_score)
  const band = scoreBand(pct)
  const towards = scorePercent(data.score_towards_candidate)
  const from = scorePercent(data.score_from_candidate)
  const alreadyInterested = data.you_expressed_interest
  const canChat = ['mutual', 'chatting', 'contact_shared', 'cohabiting'].includes(data.state)
  const canConfirmMoveIn = data.state === 'contact_shared'
  const canReject = ['viewed', 'interested', 'mutual', 'chatting', 'contact_shared'].includes(data.state)

  return (
    <AppShell>
      <div className="max-w-2xl mx-auto px-4 py-7 pb-28">
        <Link to="/matches" className="text-[13px] font-medium text-cohab-primary">
          ← All matches
        </Link>

        {pendingHere && (
          <div className="mt-4 bg-cohab-tint border border-cohab-primary rounded-2xl p-4 flex items-center justify-between gap-3">
            <p className="text-[13.5px] text-cohab-ink">How did it go with {data.candidate_name}?</p>
            <Button onClick={() => setFeedbackTarget(pendingHere)} className="flex-none">
              Give feedback
            </Button>
          </div>
        )}

        <div className="bg-white border border-cohab-border rounded-2xl p-6 mt-4">
          <div className="flex items-start gap-4">
            <Avatar name={data.candidate_name} src={data.candidate_avatar_url} size={64} />
            <div className="flex-1 min-w-0">
              <h1 className="text-xl font-semibold tracking-tight">{data.candidate_name}</h1>
              {data.candidate_course && (
                <p className="text-[13.5px] text-cohab-muted mt-0.5">{data.candidate_course}</p>
              )}
            </div>
            <SafetyActions userId={data.candidate_id} userName={data.candidate_name} />
          </div>

          <div className="mt-5 pt-5 border-t border-cohab-border-soft flex items-end gap-4">
            <div>
              <div className="text-3xl font-bold tabular-nums">{pct}%</div>
              <div className="text-xs font-semibold mt-1" style={{ color: BAND_COLOR[band] }}>
                {band} match
              </div>
            </div>
            <p className="text-[12px] text-cohab-subtle flex-1">
              You score them {towards}%, they score you {from}%. Combined using the harmonic
              mean — the lower of the two carries more weight, not a simple average.
            </p>
          </div>
        </div>

        {data.listing && (
          <div className="bg-white border border-cohab-border rounded-2xl p-6 mt-4">
            <div className="flex items-baseline justify-between mb-1">
              <h2 className="text-base font-semibold">Their listing</h2>
              <span className="text-[13px] text-cohab-muted">{data.listing.locality}</span>
            </div>
            <p className="text-[13px] text-cohab-muted mb-4">
              Rent and dates below are the values used as your hard constraints.
            </p>
            {data.listing.photos.length > 0 && (
              <div className="grid grid-cols-3 gap-2 mb-4">
                {data.listing.photos.slice(0, 3).map((url) => (
                  <img key={url} src={url} alt="" className="aspect-square object-cover rounded-lg" />
                ))}
              </div>
            )}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-px bg-cohab-border rounded-xl overflow-hidden border border-cohab-border">
              {[
                { k: 'Rent', v: `₹${data.listing.rent_per_person.toLocaleString('en-IN')}/mo` },
                { k: 'Deposit', v: `₹${data.listing.deposit.toLocaleString('en-IN')}` },
                { k: 'Room', v: data.listing.room_type === 'private' ? 'Private' : 'Shared' },
                { k: 'Available', v: data.listing.available_from },
              ].map((f) => (
                <div key={f.k} className="bg-white p-3">
                  <span className="block font-mono text-[10px] uppercase tracking-wide text-cohab-subtle">
                    {f.k}
                  </span>
                  <span className="block text-sm font-semibold mt-1">{f.v}</span>
                </div>
              ))}
            </div>
            {data.listing.amenities.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-4">
                {data.listing.amenities.map((a) => (
                  <span key={a} className="text-[12px] border border-cohab-border rounded-lg px-2.5 py-1.5">
                    {a}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="bg-white border border-cohab-border rounded-2xl p-6 mt-4">
          <h2 className="text-base font-semibold mb-1">Attribute breakdown</h2>
          <p className="text-[13px] text-cohab-muted mb-2">
            Tolerance attributes score differently in each direction.
          </p>
          {Object.entries(data.breakdown).map(([attr, cell]) => (
            <AttributeRow key={attr} attribute={attr} simA={cell.sim_a} simB={cell.sim_b} />
          ))}

          {data.divergence && (
            <div className="flex gap-3 items-start mt-4 border border-cohab-accent rounded-xl px-4 py-3.5">
              <span className="font-mono text-[10px] uppercase tracking-wide text-cohab-accent mt-0.5 flex-none">
                Divergence
              </span>
              <p className="text-[13.5px] text-cohab-ink">{data.divergence.text}</p>
            </div>
          )}
        </div>
      </div>

      <div className="fixed bottom-0 inset-x-0 bg-white border-t border-cohab-border">
        <div className="max-w-2xl mx-auto px-4 py-3 flex flex-col items-center gap-1.5">
          {canConfirmMoveIn && (
            <Button
              onClick={() => confirmMoveInMutation.mutate()}
              disabled={confirmMoveInMutation.isPending}
              className="w-full"
            >
              Confirm move-in
            </Button>
          )}
          {canChat ? (
            <Link to={`/matches/${matchId}/chat`} className="w-full">
              <Button variant={canConfirmMoveIn ? 'secondary' : 'primary'} className="w-full">
                Open chat
              </Button>
            </Link>
          ) : (
            <Button
              onClick={() => interestMutation.mutate()}
              disabled={alreadyInterested || interestMutation.isPending}
              className="w-full"
            >
              {alreadyInterested ? 'Interest sent' : 'Express interest'}
            </Button>
          )}
          <p className="text-[11.5px] text-cohab-subtle text-center">
            {canConfirmMoveIn
              ? "Once you've both moved in, confirm here — we'll check in on how it's going."
              : canChat
                ? "It's a mutual match — you can both see this conversation."
                : "They'll see that you're interested. It becomes mutual only if they are too."}
          </p>
          {canReject && (
            <Button variant="danger" size="sm" onClick={() => setShowReject(true)}>
              Not going ahead with this match
            </Button>
          )}
        </div>
      </div>

      {feedbackTarget && (
        <FeedbackDialog
          matchId={feedbackTarget.match_id}
          otherUserName={data.candidate_name}
          state={feedbackTarget.state as 'cohabiting' | 'rejected'}
          onClose={() => setFeedbackTarget(null)}
        />
      )}
      {showReject && (
        <RejectConfirmDialog
          matchId={matchId!}
          candidateId={data.candidate_id}
          candidateName={data.candidate_name}
          onClose={() => setShowReject(false)}
        />
      )}
    </AppShell>
  )
}
