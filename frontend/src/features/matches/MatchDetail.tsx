import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { matchesApi } from '@/api/matches'
import { feedbackApi } from '@/api/feedback'
import { AppShell } from '@/components/AppShell'
import { Avatar } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { Eyebrow } from '@/components/Eyebrow'
import { FactsGrid } from '@/components/FactsGrid'
import { AttributeRow } from '@/components/AttributeRow'
import { Reveal } from '@/components/motion/Reveal'
import { CountUp } from '@/components/motion/CountUp'
import { useBarFill } from '@/hooks/useBarFill'
import { SafetyActions } from '@/features/safety/SafetyActions'
import { FeedbackDialog } from './FeedbackDialog'
import { RejectConfirmDialog } from './RejectConfirmDialog'
import { SaveToggle } from './SaveToggle'
import { scorePercent, scoreBand, BAND_COLOR } from '@/lib/score'
import type { PendingFeedbackOut } from '@/api/types'

/** The mobile combined-score bar. Its own component only so that
 * `useBarFill` has somewhere to live — `MatchDetail` computes `pct` after its
 * loading/error early returns, and a hook cannot be called after those. */
function ScoreBar({ pct, color }: { pct: number; color: string }) {
  const ref = useBarFill<HTMLDivElement>(pct)
  return (
    <div className="h-1 rounded-full bg-cohab-border-soft overflow-hidden">
      <div ref={ref} className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
    </div>
  )
}

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
  const [showAllAttributes, setShowAllAttributes] = useState(false)

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
        <div className="max-w-2xl cohab-desktop:max-w-[1200px] mx-auto px-4 cohab-desktop:px-8 py-10 text-cohab-muted">
          Loading…
        </div>
      </AppShell>
    )
  }

  if (error || !data) {
    return (
      <AppShell>
        <div className="max-w-2xl cohab-desktop:max-w-[1200px] mx-auto px-4 cohab-desktop:px-8 py-10 text-cohab-accent">
          Couldn't load this match.
        </div>
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

  const primaryLabel = canConfirmMoveIn
    ? 'Confirm move-in'
    : canChat
      ? 'Open chat'
      : alreadyInterested
        ? 'Interest sent'
        : 'Express interest'
  const primaryDisabled = canConfirmMoveIn
    ? confirmMoveInMutation.isPending
    : canChat
      ? false
      : alreadyInterested || interestMutation.isPending
  function firePrimaryAction() {
    if (canConfirmMoveIn) confirmMoveInMutation.mutate()
    else if (!canChat) interestMutation.mutate()
  }
  const captionText = canConfirmMoveIn
    ? "Once you've both moved in, confirm here — we'll check in on how it's going."
    : canChat
      ? "It's a mutual match — you can both see this conversation."
      : "They'll see that you're interested. It becomes mutual only if they are too."

  const attributeEntries = Object.entries(data.breakdown)
  const mobileAttributeEntries = showAllAttributes ? attributeEntries : attributeEntries.slice(0, 6)

  return (
    <AppShell>
      {/* Mobile header bar */}
      <div className="cohab-desktop:hidden flex-none h-11 px-1 flex items-center justify-between border-b border-cohab-border-soft">
        <Link to="/matches" className="w-11 h-11 flex items-center justify-center text-cohab-ink text-[22px]">
          ←
        </Link>
        <span className="text-[15px] font-semibold text-cohab-ink truncate px-2">{data.candidate_name}</span>
        <SafetyActions userId={data.candidate_id} userName={data.candidate_name} />
      </div>

      <div className="max-w-2xl cohab-desktop:max-w-[1200px] mx-auto px-4 cohab-desktop:px-8 py-4 cohab-desktop:py-7 pb-28 cohab-desktop:pb-16">
        <Link to="/matches" className="hidden cohab-desktop:inline-block text-[13px] font-medium text-cohab-primary mb-[22px]">
          ← All matches
        </Link>

        {pendingHere && (
          <div className="mt-1 cohab-desktop:mt-0 mb-4 bg-cohab-tint border border-cohab-primary rounded-2xl p-4 flex items-center justify-between gap-3">
            <p className="text-[13.5px] text-cohab-ink">How did it go with {data.candidate_name}?</p>
            <Button onClick={() => setFeedbackTarget(pendingHere)} className="flex-none">
              Give feedback
            </Button>
          </div>
        )}

        {/* Profile + score card */}
        <div className="bg-cohab-card border border-cohab-border rounded-2xl cohab-desktop:rounded-[18px] p-5 cohab-desktop:p-[30px_32px] mt-3 cohab-desktop:mt-0 cohab-desktop:flex cohab-desktop:items-start cohab-desktop:gap-6">
          <div className="cohab-desktop:flex-1 cohab-desktop:min-w-0">
            <div className="flex items-center gap-3.5 cohab-desktop:gap-4 cohab-desktop:mb-1">
              {/* The avatar used to be `cohab-desktop:hidden`, which left the
                  desktop card with a name, a course line and ~200px of empty
                  box below it (reported by the user). It shows on both
                  breakpoints now, larger on desktop. */}
              {/* Fixed 64 rather than a responsive class: `Avatar` sets
                  width/height as inline style, which a utility class cannot
                  override. */}
              <Avatar name={data.candidate_name} src={data.candidate_avatar_url} size={64} />
              <div className="flex-1 min-w-0">
                <h1 className="text-xl cohab-desktop:text-[26px] font-semibold tracking-tight cohab-desktop:tracking-[-.015em] flex items-center gap-2.5 flex-wrap">
                  {data.candidate_name}
                  <span className="hidden cohab-desktop:inline-flex items-center rounded-[30px] border border-cohab-primary bg-cohab-tint px-2.5 py-1 text-[11px] font-medium text-cohab-primary">
                    Verified · Institutional email
                  </span>
                </h1>
                {data.candidate_course && (
                  <p className="text-[13.5px] cohab-desktop:text-sm text-cohab-muted mt-0.5">{data.candidate_course}</p>
                )}
              </div>
              <SaveToggle matchId={matchId!} className="w-9 h-9 border border-cohab-border flex-none" />
            </div>

            {/* Mobile score row */}
            <div className="cohab-desktop:hidden flex items-end gap-3 mt-[18px]">
              <div>
                <CountUp
                  value={pct}
                  suffix="%"
                  className="block text-[34px] font-bold tracking-[-.02em] tabular-nums leading-none"
                />
                <div className="text-xs font-semibold mt-1.5" style={{ color: BAND_COLOR[band] }}>
                  {band} match
                </div>
              </div>
              <div className="flex-1 pb-1">
                <ScoreBar pct={pct} color={BAND_COLOR[band]} />
                <p className="text-xs leading-[1.4] text-cohab-subtle-mobile mt-[7px]">
                  You score them {towards}%, they score you {from}%. Combined using the harmonic mean — the lower of
                  the two carries more weight, not a simple average.
                </p>
              </div>
            </div>

            {/* Why you were matched (D-13.14). These cards were fetched by
                the explanation query and rendered nowhere on this screen —
                the desktop card showed a name, a course and then ~200px of
                empty box, which the user reported. They are also the most
                useful thing to read directly under someone's name, and the
                attribute-by-attribute table further down is the detail
                behind them rather than a substitute. */}
            {(data.agreements.length > 0 || data.divergence) && (
              <div className="hidden cohab-desktop:block mt-5 pt-4 border-t border-cohab-border-soft">
                <Eyebrow className="mb-2.5">Why you were matched</Eyebrow>
                <div className="flex flex-wrap gap-2">
                  {data.agreements.map((card) => (
                    <span
                      key={card.attribute}
                      className="rounded-lg border border-cohab-primary/35 bg-cohab-tint px-2.5 py-1.5 text-[12.5px] leading-[1.35] text-cohab-ink"
                    >
                      {card.text}
                    </span>
                  ))}
                  {data.divergence && (
                    <span className="rounded-lg border border-cohab-accent/45 bg-cohab-accent-tint px-2.5 py-1.5 text-[12.5px] leading-[1.35] text-cohab-warn">
                      <span className="font-semibold">Worth discussing · </span>
                      {data.divergence.text}
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Desktop score side panel */}
          <div className="hidden cohab-desktop:block w-[210px] flex-none border-l border-cohab-border pl-[22px]">
            <Eyebrow>Combined score</Eyebrow>
            <CountUp
              value={pct}
              suffix="%"
              className="block text-[38px] font-semibold tracking-[-.025em] tabular-nums leading-[1.05] mt-2 mb-2.5"
            />
            <p className="text-xs leading-[1.45] text-cohab-muted mb-4">
              You score them {towards}%, they score you {from}%. Combined using the harmonic mean — the lower of the
              two carries more weight, not a simple average.
            </p>
            {canConfirmMoveIn && (
              <Button onClick={() => confirmMoveInMutation.mutate()} disabled={confirmMoveInMutation.isPending} className="w-full">
                Confirm move-in
              </Button>
            )}
            {canChat ? (
              <Link to={`/matches/${matchId}/chat`} className="block w-full">
                <Button variant={canConfirmMoveIn ? 'secondary' : 'primary'} className="w-full">
                  Open chat
                </Button>
              </Link>
            ) : (
              <Button
                onClick={() => interestMutation.mutate()}
                disabled={alreadyInterested || interestMutation.isPending}
                variant={alreadyInterested ? 'secondary' : 'primary'}
                className="w-full"
              >
                {alreadyInterested ? 'Interest sent' : 'Express interest'}
              </Button>
            )}
            {canReject && (
              <Button variant="danger" size="sm" onClick={() => setShowReject(true)} className="w-full mt-2">
                Not going ahead with this match
              </Button>
            )}
          </div>
        </div>

        {/* Listing card */}
        {data.listing && (
          <Reveal className="bg-cohab-card border border-cohab-border rounded-2xl cohab-desktop:rounded-[18px] p-5 cohab-desktop:p-[26px_30px] mt-3.5 cohab-desktop:mt-4">
            <div className="flex items-baseline justify-between mb-1 gap-3">
              <h2 className="text-base cohab-desktop:text-[17px] font-semibold">Their listing</h2>
              <span className="text-[13px] text-cohab-muted flex-none">{data.listing.locality}</span>
            </div>
            <p className="text-[13px] leading-[1.45] text-cohab-muted mb-4 cohab-desktop:mb-[18px]">
              Rent and dates below are the values used as your hard constraints — not a preference they stated.
            </p>

            {data.listing.photos.length > 0 && (
              <>
                {/* Desktop: 3-up equal-height row */}
                <div className="hidden cohab-desktop:grid grid-cols-[2fr_1fr_1fr] gap-2.5 h-[180px] mb-5">
                  {data.listing.photos.slice(0, 3).map((url) => (
                    <div key={url} className="min-w-0 min-h-0 overflow-hidden rounded-xl">
                      <img src={url} alt="" className="w-full h-full object-cover" />
                    </div>
                  ))}
                </div>
                {/* Mobile: one big + up to two stacked small, per s8's collage grid */}
                <div className="cohab-desktop:hidden grid grid-cols-[minmax(0,2fr)_minmax(0,1fr)] gap-0.5 h-40 mb-4 rounded-xl overflow-hidden">
                  <img src={data.listing.photos[0]} alt="" className="min-w-0 w-full h-full object-cover" />
                  {data.listing.photos.length > 1 && (
                    <div className="grid grid-rows-[1fr_1fr] gap-0.5">
                      {data.listing.photos.slice(1, 3).map((url) => (
                        <img key={url} src={url} alt="" className="min-w-0 w-full h-full object-cover" />
                      ))}
                    </div>
                  )}
                </div>
              </>
            )}

            <FactsGrid
              columns={2}
              className="cohab-desktop:hidden"
              items={[
                { label: 'Rent', value: `₹${data.listing.rent_per_person.toLocaleString('en-IN')}/mo` },
                { label: 'Deposit', value: `₹${data.listing.deposit.toLocaleString('en-IN')}` },
                { label: 'Room', value: data.listing.room_type === 'private' ? 'Private' : 'Shared' },
                { label: 'Available', value: data.listing.available_from },
              ]}
            />
            <FactsGrid
              columns={4}
              className="hidden cohab-desktop:grid"
              items={[
                { label: 'Rent', value: `₹${data.listing.rent_per_person.toLocaleString('en-IN')}/mo` },
                { label: 'Deposit', value: `₹${data.listing.deposit.toLocaleString('en-IN')}` },
                { label: 'Room', value: data.listing.room_type === 'private' ? 'Private' : 'Shared' },
                { label: 'Available', value: data.listing.available_from },
              ]}
            />

            {data.listing.amenities.length > 0 && (
              <div className="flex flex-wrap gap-1.5 cohab-desktop:gap-2 mt-4">
                {data.listing.amenities.map((a) => (
                  <span
                    key={a}
                    className="text-[12.5px] cohab-desktop:text-xs text-cohab-ink border border-cohab-border rounded-[10px] cohab-desktop:rounded-lg px-2.5 py-1.5"
                  >
                    {a}
                  </span>
                ))}
              </div>
            )}
          </Reveal>
        )}

        {/* Attribute breakdown card */}
        <Reveal className="bg-cohab-card border border-cohab-border rounded-2xl cohab-desktop:rounded-[18px] p-5 cohab-desktop:p-[26px_30px] mt-3.5 cohab-desktop:mt-4">
          <h2 className="hidden cohab-desktop:block text-[17px] font-semibold mb-1.5">Attribute breakdown</h2>
          <p className="hidden cohab-desktop:block text-[13px] leading-[1.45] text-cohab-muted mb-5">
            Tolerance attributes score differently in each direction — the arrow shows which way the difference runs.
          </p>
          <p className="cohab-desktop:hidden font-semibold text-[11px] uppercase tracking-[.07em] text-cohab-subtle-mobile mb-3">
            How you compare
          </p>

          <div className="hidden cohab-desktop:grid grid-cols-[150px_1fr_1fr_128px] gap-2.5 pb-[9px] border-b border-cohab-border">
            <Eyebrow>Attribute</Eyebrow>
            <Eyebrow>You</Eyebrow>
            <Eyebrow>{data.candidate_name}</Eyebrow>
            <Eyebrow className="text-right">Score</Eyebrow>
          </div>

          <div className="cohab-desktop:hidden">
            {mobileAttributeEntries.map(([attr, cell]) => (
              <AttributeRow key={attr} attribute={attr} simA={cell.sim_a} simB={cell.sim_b} />
            ))}
          </div>
          <div className="hidden cohab-desktop:block">
            {attributeEntries.map(([attr, cell]) => (
              <AttributeRow key={attr} attribute={attr} simA={cell.sim_a} simB={cell.sim_b} />
            ))}
          </div>

          {!showAllAttributes && attributeEntries.length > 6 && (
            <button
              type="button"
              onClick={() => setShowAllAttributes(true)}
              className="cohab-desktop:hidden block text-[13.5px] font-medium text-cohab-primary mt-3.5"
            >
              Show all {attributeEntries.length} attributes
            </button>
          )}

          {data.divergence && (
            <div className="hidden cohab-desktop:flex gap-3 items-start mt-[18px] border border-cohab-accent rounded-xl px-4 py-3.5">
              <Eyebrow className="text-cohab-accent mt-0.5 flex-none">Divergence</Eyebrow>
              <p className="text-[13.5px] leading-[1.5] text-cohab-score">{data.divergence.text}</p>
            </div>
          )}
        </Reveal>

        {/* Desktop footer — mockup's separate Report/Block links collapse to the
            shared SafetyActions trigger + modal (out of scope to rewrite here) */}
        <div className="hidden cohab-desktop:flex items-center gap-4 mt-4">
          <SafetyActions userId={data.candidate_id} userName={data.candidate_name} />
        </div>
      </div>

      {/* Mobile sticky footer */}
      <div className="cohab-desktop:hidden fixed bottom-0 inset-x-0 bg-cohab-card border-t border-cohab-border">
        <div className="max-w-2xl mx-auto px-5 py-3 flex flex-col gap-1.5">
          <div className="flex gap-2.5">
            {canReject && (
              <Button variant="secondary" className="rounded-full flex-none" onClick={() => setShowReject(true)}>
                Not for me
              </Button>
            )}
            {canChat ? (
              <Link to={`/matches/${matchId}/chat`} className="flex-1">
                <Button className="rounded-full w-full">{primaryLabel}</Button>
              </Link>
            ) : (
              <Button onClick={firePrimaryAction} disabled={primaryDisabled} className="rounded-full flex-1">
                {primaryLabel}
              </Button>
            )}
          </div>
          <p className="text-[11.5px] leading-[1.45] text-cohab-subtle text-center">{captionText}</p>
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
