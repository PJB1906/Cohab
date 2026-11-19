import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { matchesApi } from '@/api/matches'
import { feedbackApi } from '@/api/feedback'
import { AppShell } from '@/components/AppShell'
import { Button } from '@/components/ui/button'
import { FactsGrid } from '@/components/FactsGrid'
import { Chemistry, type ChemistryRow } from '@/components/Chemistry'
import { attributeLabel } from '@/data/attributes'
import { Reveal } from '@/components/motion/Reveal'
import { CountUp } from '@/components/motion/CountUp'
import { SafetyActions } from '@/features/safety/SafetyActions'
import { FeedbackDialog } from './FeedbackDialog'
import { RejectConfirmDialog } from './RejectConfirmDialog'
import { SaveToggle } from './SaveToggle'
import { scorePercent, scoreBand } from '@/lib/score'
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
      // Each decision refits your taste model; the list order may change.
      queryClient.invalidateQueries({ queryKey: ['me', 'taste'] })
      queryClient.invalidateQueries({ queryKey: ['matches'] })
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
        <div className="max-w-md mx-auto px-4 py-12 text-center">
          <p className="text-[15px] font-medium mb-1.5">This match isn't available</p>
          <p className="text-[13.5px] text-cohab-muted mb-5">
            The link may be old, or the match has ended or been removed.
          </p>
          <Link to="/matches" className="text-cohab-primary font-medium text-[14px]">
            Back to your matches
          </Link>
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

  const firstName = data.candidate_name.split(' ')[0]
  const chemistryRows: ChemistryRow[] = Object.entries(data.breakdown).map(([attr, cell]) => ({
    key: attr,
    label: attributeLabel(attr),
    you: cell.sim_a,
    them: cell.sim_b,
  }))
    // Strongest shared ground first, the friction at the bottom.
    .sort((x, y) => Math.min(y.you, y.them) - Math.min(x.you, x.them))

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

        {/* Poster header (D-14.23): the person, the number, the decision. */}
        <section className="relative isolate overflow-hidden mt-3 cohab-desktop:mt-0 text-white rounded-[30px] p-6 cohab-desktop:p-10 grid cohab-desktop:grid-cols-[minmax(0,1fr)_260px] gap-8 items-end shadow-[var(--shadow-soft)]">
          <img src="/photos/room-sunlight.webp" alt="" aria-hidden className="absolute inset-0 -z-20 w-full h-full object-cover" />
          <div className="absolute inset-0 -z-10 bg-[linear-gradient(110deg,rgb(8_12_46/0.96)_0%,rgb(27_52_209/0.86)_55%,rgb(42_75_255/0.45)_100%)]" />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2 mb-5">
              <span className="label text-[10px] bg-white text-cohab-on-sun rounded-full px-2.5 py-1">Verified student</span>
              {data.candidate_course && <span className="text-[13px] text-white/65">{data.candidate_course}</span>}
              <SaveToggle matchId={matchId!} className="ml-auto w-9 h-9 bg-white text-cohab-on-sun rounded-full" />
            </div>
            <h1 className="poster text-white text-[60px] cohab-desktop:text-[104px] break-words">{data.candidate_name}</h1>
            {(data.agreements.length > 0 || data.divergence) && (
              <div className="flex flex-wrap gap-2 mt-6">
                {data.agreements.map((card) => (
                  <span key={card.attribute} className="rounded-full bg-white/10 text-white text-[13px] font-semibold px-3 py-1.5">
                    {card.text}
                  </span>
                ))}
                {data.divergence && (
                  <span className="rounded-full bg-[#ff8a7a] text-cohab-on-sun text-[13px] font-bold px-3 py-1.5">
                    Talk about: {data.divergence.text}
                  </span>
                )}
              </div>
            )}
          </div>

          <div className="cohab-desktop:text-right">
            <span className="label text-[10px] text-white/55">Compatibility</span>
            <CountUp value={pct} className="poster-num block text-[112px] cohab-desktop:text-[150px] text-cohab-sun mt-1" />
            <span className="label text-[11px] text-cohab-sun">{band} match</span>
            <p className="text-[12.5px] leading-[1.45] text-white/60 mt-3">
              They suit you {towards}. You suit them {from}. The lower side counts more.
            </p>
            <div className="hidden cohab-desktop:flex flex-col gap-2 mt-6">
              {canConfirmMoveIn && (
                <button
                  type="button"
                  onClick={() => confirmMoveInMutation.mutate()}
                  disabled={confirmMoveInMutation.isPending}
                  className="cohab-press h-12 rounded-full bg-cohab-sun text-cohab-on-sun font-bold disabled:opacity-40"
                >
                  Confirm move-in
                </button>
              )}
              {canChat ? (
                <Link
                  to={`/matches/${matchId}/chat`}
                  className="cohab-press h-12 rounded-full bg-white text-cohab-on-sun font-bold inline-flex items-center justify-center"
                >
                  Open chat
                </Link>
              ) : (
                <button
                  type="button"
                  onClick={() => interestMutation.mutate()}
                  disabled={alreadyInterested || interestMutation.isPending}
                  className="cohab-press h-12 rounded-full bg-white text-cohab-on-sun font-bold disabled:bg-white/20 disabled:text-white/70"
                >
                  {alreadyInterested ? 'Interest sent' : "I'm interested"}
                </button>
              )}
              {canReject && (
                <button
                  type="button"
                  onClick={() => setShowReject(true)}
                  className="cohab-press h-11 rounded-full border border-white/35 text-white/90 text-[14px] font-semibold hover:bg-white/10"
                >
                  Not for me
                </button>
              )}
              <p className="text-[11.5px] text-white/45 mt-1">{captionText}</p>
            </div>
          </div>
        </section>

        {/* Listing card */}
        {data.listing && (
          <Reveal className="surface rounded-[28px] p-5 cohab-desktop:p-8 mt-4">
            <div className="flex items-baseline justify-between mb-1 gap-3">
              <h2 className="poster text-[36px] cohab-desktop:text-[44px]">Their place</h2>
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

        {/* Chemistry (D-14.23): the same per-attribute scores the ranking is
            made of, drawn both ways. Nothing here is computed in the browser. */}
        <Reveal className="surface rounded-[28px] p-5 cohab-desktop:p-8 mt-4">
          <div className="flex flex-wrap items-end justify-between gap-3 mb-6">
            <div>
              <span className="label text-[10px] text-cohab-subtle">Habit by habit</span>
              <h2 className="poster text-[40px] cohab-desktop:text-[56px] mt-1">Your chemistry</h2>
            </div>
            <p className="text-[13.5px] leading-[1.5] text-cohab-muted max-w-[46ch]">
              Left: how well {firstName} suits you. Right: how well you suit {firstName}. Some habits score differently
              each way, like guests or smoking.
            </p>
          </div>
          <Chemistry
            rows={chemistryRows}
            youLabel={`${firstName} for you`}
            themLabel={`You for ${firstName}`}
          />
          {data.divergence && (
            <div className="mt-6 bg-cohab-accent-tint rounded-[16px] px-4 py-3.5 flex gap-3 items-start">
              <span className="label text-[10px] text-cohab-accent mt-[3px] shrink-0">Talk about</span>
              <p className="text-[14px] leading-[1.5] text-cohab-ink">{data.divergence.text}</p>
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
            {canChat && !canConfirmMoveIn ? (
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
