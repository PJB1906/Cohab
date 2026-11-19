import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { chatApi } from '@/api/chat'
import { matchesApi } from '@/api/matches'
import { ApiError } from '@/api/client'
import { AppShell } from '@/components/AppShell'
import { Avatar } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const SAFETY_TIPS = [
  { title: 'Meet in a public place first.', body: 'A café near campus, in daylight, before you see the flat.' },
  {
    title: "Tell someone where you're going.",
    body: 'Share the address and the time with a friend or family member.',
  },
  { title: 'See the room in person.', body: 'Photos are photos. Visit before you commit to anything.' },
  {
    title: 'Never send a deposit before viewing.',
    body: 'No genuine flatmate needs money to hold a room for a day.',
  },
  { title: 'If something feels wrong, leave.', body: 'You can report or block at any point, before or after sharing.', danger: true },
]

/** Screen 10 (PRD §9): explicit mutual consent, with in-person meeting
 * guidance shown "at the moment of greatest practical risk" (PRD §10). */
export function ContactShare() {
  const { matchId } = useParams<{ matchId: string }>()
  const queryClient = useQueryClient()

  const { data: match, isError: matchFailed } = useQuery({
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

  const withdrawMutation = useMutation({
    mutationFn: () => chatApi.withdrawContactShare(matchId!),
    onSuccess: (updated) => {
      queryClient.setQueryData(['chat', matchId, 'contact-status'], updated)
    },
  })

  if (matchFailed) {
    return (
      <AppShell>
        <div className="max-w-md mx-auto px-4 py-12 text-center">
          <p className="text-[15px] font-medium mb-1.5">This match isn't available</p>
          <p className="text-[13.5px] text-cohab-muted mb-5">The link may be old, or the match has ended.</p>
          <Link to="/matches" className="text-cohab-primary font-medium text-[14px]">
            Back to your matches
          </Link>
        </div>
      </AppShell>
    )
  }

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
            {notOpenYet ? 'Open chat with them before sharing contact details.' : "Couldn't load this."}
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

  const youConsented = Boolean(status?.you_consented)
  const otherConsented = Boolean(status?.other_consented)
  const bothShared = youConsented && otherConsented
  const firstName = match.candidate_name.split(' ')[0]

  // Shown under the consent controls in both layouts. Before the v2 audit a
  // failed opt-in or withdrawal did nothing visible at all.
  const actionError = shareMutation.error ?? withdrawMutation.error
  const actionErrorText = actionError
    ? actionError instanceof ApiError
      ? actionError.message
      : 'That did not go through. Please try again.'
    : null
  const errorNote = actionErrorText && (
    <p role="alert" className="text-[13px] text-cohab-accent mt-3">
      {actionErrorText}{' '}
      {/phone number/i.test(actionErrorText) && (
        <Link to="/profile" className="underline font-medium">
          Go to Profile
        </Link>
      )}
    </p>
  )

  function toggleConsent() {
    if (youConsented) withdrawMutation.mutate()
    else shareMutation.mutate()
  }

  const consentStatusText = bothShared
    ? 'Both of you have agreed — contact details below.'
    : youConsented
      ? `Waiting for ${firstName} to agree.`
      : otherConsented
        ? `${firstName} has agreed. Agree to reveal both numbers.`
        : 'Neither of you has agreed yet.'

  return (
    <AppShell>
      {/* Mobile */}
      <div className="cohab-desktop:hidden pb-28">
        <div className="flex items-center gap-1 px-2 py-1.5 border-b border-cohab-border-soft bg-cohab-card">
          <Link
            to={`/matches/${matchId}/chat`}
            className="w-11 h-11 flex items-center justify-center text-cohab-ink text-[22px]"
          >
            ←
          </Link>
          <span className="text-[15px] font-semibold text-cohab-ink">Share contact details</span>
        </div>

        <div className="px-5 py-5">
          <h1 className="poster text-[40px] text-cohab-ink mb-3">
            Both of you have to agree
          </h1>
          <p className="text-[14.5px] leading-[1.55] text-cohab-muted-mobile mb-5">
            Nothing is released until you each tick this separately. Either of you can withdraw before that, and
            you can keep chatting here instead.
          </p>

          <div className="border border-cohab-border-soft rounded-[18px] overflow-hidden mb-5">
            <div className="flex items-center gap-3 px-[15px] py-3.5 border-b border-cohab-border-soft">
              <Avatar name={match.candidate_name} src={match.candidate_avatar_url} size={38} />
              <div className="flex-1">
                <div className="text-[14.5px] font-semibold text-cohab-ink">{match.candidate_name}</div>
                <div className="text-[12.5px] text-cohab-primary mt-[3px]">
                  {otherConsented ? 'Agreed' : 'Not agreed yet'}
                </div>
              </div>
              {otherConsented && (
                <div className="w-[22px] h-[22px] rounded-full bg-cohab-primary text-cohab-on-fill text-[12px] font-semibold flex items-center justify-center flex-none">
                  ✓
                </div>
              )}
            </div>
            <button
              type="button"
              onClick={toggleConsent}
              disabled={shareMutation.isPending || withdrawMutation.isPending}
              className="flex items-center gap-3 px-[15px] py-3.5 w-full bg-cohab-card border-none cursor-pointer text-left disabled:opacity-60"
            >
              <div className="w-[38px] h-[38px] rounded-full bg-cohab-bg flex-none" />
              <div className="flex-1">
                <div className="text-[14.5px] font-semibold text-cohab-ink">You</div>
                <div className="text-[12.5px] text-cohab-muted-mobile mt-[3px]">
                  Share my phone number with {firstName}
                </div>
              </div>
              <div
                className={cn(
                  'w-6 h-6 rounded-xl flex-none flex items-center justify-center',
                  youConsented ? 'bg-cohab-primary border border-cohab-primary' : 'bg-transparent border border-cohab-border',
                )}
              >
                {youConsented && <span className="text-cohab-on-fill text-[13px] font-semibold">✓</span>}
              </div>
            </button>
          </div>

          {errorNote && <div className="-mt-1 mb-3">{errorNote}</div>}
          <p className="text-[13px] font-medium text-cohab-primary mb-5">{consentStatusText}</p>

          {bothShared && (
            <div className="border border-cohab-border bg-cohab-tint rounded-[18px] p-[15px] mb-[22px]">
              <p className="text-[11px] font-semibold tracking-[.07em] uppercase text-cohab-primary mb-2.5">
                Contact details
              </p>
              {status?.other_phone ? (
                <p className="text-[17px] font-semibold text-cohab-ink tabular-nums">{status.other_phone}</p>
              ) : (
                <p className="text-[13px] text-cohab-subtle">
                  They haven't added a phone number to their account yet.
                </p>
              )}
              <p className="text-[13px] text-cohab-ink/80 mt-[5px]">{match.candidate_name} · shared</p>
            </div>
          )}

          <div className="border-t border-cohab-border-soft pt-[18px]">
            <h2 className="text-[15px] font-semibold text-cohab-ink mb-3">Before you meet</h2>
            <div className="flex flex-col gap-[13px]">
              {SAFETY_TIPS.map((tip) => (
                <div key={tip.title} className="flex gap-[11px]">
                  <div
                    className={cn(
                      'w-1.5 h-1.5 rounded-full mt-[7px] flex-none',
                      tip.danger ? 'bg-cohab-accent' : 'bg-cohab-primary',
                    )}
                  />
                  <p className="text-[14px] leading-[1.5] text-cohab-ink">
                    <span className="font-semibold">{tip.title}</span> {tip.body}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="fixed bottom-0 inset-x-0 px-5 pt-3 pb-2 border-t border-cohab-border-soft bg-cohab-card">
          <Link
            to={`/matches/${matchId}/chat`}
            className="block h-12 rounded-full border border-cohab-border text-cohab-ink text-[15px] font-semibold text-center leading-[46px] bg-cohab-card"
          >
            Back to chat
          </Link>
        </div>
      </div>

      {/* Desktop */}
      <div className="hidden cohab-desktop:block max-w-[760px] mx-auto px-8 py-9 pb-[60px]">
        <Link to={`/matches/${matchId}/chat`} className="text-[13px] font-medium text-cohab-primary">
          ← Back to chat
        </Link>
        <h1 className="poster text-[56px] text-cohab-ink mt-5 mb-3">
          Share contact details with {firstName}
        </h1>
        <p className="text-[15px] leading-[1.55] text-cohab-ink/85 mb-[26px]">
          Nothing is released until both of you have agreed. Either of you can withdraw before the other consents.
          Once shared, it cannot be taken back.
        </p>

        <div className="grid grid-cols-2 gap-3.5 mb-5">
          <div
            className={cn(
              'rounded-2xl px-[22px] py-5 border',
              youConsented ? 'bg-cohab-tint border-cohab-primary' : 'bg-cohab-card border-cohab-border',
            )}
          >
            <span className="font-mono text-[10px] tracking-[.06em] uppercase text-cohab-subtle">You</span>
            <p className="text-[15px] font-semibold text-cohab-ink my-[11px] mb-1.5">
              {youConsented ? 'You have agreed' : 'Not agreed yet'}
            </p>
            <p className="text-[13px] leading-[1.45] text-cohab-ink/85">
              Phone number and preferred contact time. Your address is never shared by Cohab.
            </p>
          </div>
          <div className="surface rounded-[22px] px-[22px] py-5">
            <span className="font-mono text-[10px] tracking-[.06em] uppercase text-cohab-subtle">{firstName}</span>
            <p className="text-[15px] font-semibold text-cohab-ink my-[11px] mb-1.5">
              {otherConsented ? `${firstName} has agreed` : 'Has not agreed yet'}
            </p>
            <p className="text-[13px] leading-[1.45] text-cohab-ink/85">
              {otherConsented
                ? 'Their contact details are ready to view below once you agree too.'
                : `${firstName} will be asked once you agree. They have not been told that you opened this screen.`}
            </p>
          </div>
        </div>

        {bothShared && (
          <div className="surface rounded-[22px] p-5 mb-5 text-center">
            <p className="text-xs uppercase tracking-wide text-cohab-subtle font-mono mb-1">Their number</p>
            {status?.other_phone ? (
              <p className="text-lg font-semibold tabular-nums">{status.other_phone}</p>
            ) : (
              <p className="text-[13px] text-cohab-subtle">
                They haven't added a phone number to their account yet.
              </p>
            )}
          </div>
        )}

        <div className="surface rounded-[22px] px-[26px] py-6 mb-5">
          <h2 className="text-[17px] font-semibold text-cohab-ink mb-3.5">Before you meet in person</h2>
          <div className="flex flex-col gap-[11px]">
            {SAFETY_TIPS.map((tip) => (
              <div key={tip.title} className="flex gap-[11px] items-start">
                <span
                  className={cn(
                    'w-[5px] h-[5px] rounded-full mt-2 flex-none',
                    tip.danger ? 'bg-cohab-accent' : 'bg-cohab-primary',
                  )}
                />
                <p className="text-[14px] leading-[1.5] text-cohab-ink/85">
                  <span className="font-semibold text-cohab-ink">{tip.title}</span> {tip.body}
                </p>
              </div>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-3.5">
          {bothShared ? (
            <Button
              variant="destructive"
              className="!bg-transparent !text-cohab-accent border border-cohab-accent !rounded-xl"
              onClick={() => withdrawMutation.mutate()}
              disabled={withdrawMutation.isPending}
            >
              Withdraw my consent
            </Button>
          ) : youConsented ? (
            <Button
              variant="destructive"
              className="!bg-transparent !text-cohab-accent border border-cohab-accent !rounded-xl"
              onClick={() => withdrawMutation.mutate()}
              disabled={withdrawMutation.isPending}
            >
              Withdraw my consent
            </Button>
          ) : (
            <Button
              className="!rounded-xl"
              onClick={() => shareMutation.mutate()}
              disabled={shareMutation.isPending}
            >
              Agree to share my contact details
            </Button>
          )}
          <Link to={`/matches/${matchId}/chat`}>
            <Button variant="secondary" className="!rounded-xl">
              Keep talking in chat
            </Button>
          </Link>
        </div>
        {errorNote}
        <p className="text-[12px] leading-[1.5] text-cohab-subtle mt-4 max-w-[600px]">{consentStatusText}</p>
      </div>
    </AppShell>
  )
}
