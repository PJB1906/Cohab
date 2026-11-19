import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { chatApi, PiiInterruptError } from '@/api/chat'
import { matchesApi } from '@/api/matches'
import { ApiError } from '@/api/client'
import { useSession } from '@/hooks/useSession'
import { AppShell } from '@/components/AppShell'
import { Avatar } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { SafetyActions } from '@/features/safety/SafetyActions'
import { ThreadRail } from '@/features/chat/ThreadList'
import { MessageEnter } from '@/components/motion/MessageEnter'
import { scorePercent } from '@/lib/score'
import { cn } from '@/lib/utils'

function messageTime(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

/** Screen 9 (PRD §9): moderated thread, no contact details visible until
 * Share Contact. Polls every 3s (PRD §9.1's own "3-second poll" reference)
 * rather than a WebSocket — CLAUDE.md/PRD both defer that transport.
 *
 * On desktop this is the mockup's full two-pane screen 9: `ThreadRail` on
 * the left with the conversation on the right, so the people you are
 * talking to stay visible while a thread is open (D-13.15). On mobile the
 * rail hides and this is the conversation alone, reached from /chats. */
export function ChatThread() {
  const { matchId } = useParams<{ matchId: string }>()
  const { data: me } = useSession()
  const queryClient = useQueryClient()

  // True only while the thread's existing history is first painted, so the
  // backlog appears in place and only messages arriving afterwards animate.
  const firstPaintRef = useRef(true)

  const [draft, setDraft] = useState('')
  const [warning, setWarning] = useState<{ message: string; body: string } | null>(null)
  const [sendError, setSendError] = useState<string | null>(null)

  const { data: match, isError: matchFailed } = useQuery({
    queryKey: ['match', matchId],
    queryFn: () => matchesApi.explanation(matchId!),
    enabled: Boolean(matchId),
  })

  const { data: messages, isLoading, isError: messagesFailed } = useQuery({
    queryKey: ['chat', matchId, 'messages'],
    queryFn: () => chatApi.list(matchId!),
    enabled: Boolean(matchId),
    // Stop polling once a request has failed (a bad link would otherwise hit
    // the API every three seconds forever).
    refetchInterval: (q) => (q.state.status === 'error' ? false : 3000),
  })

  const sendMutation = useMutation({
    mutationFn: (opts: { body: string; confirm?: boolean }) =>
      chatApi.send(matchId!, opts.body, opts.confirm),
    onSuccess: () => {
      setDraft('')
      setWarning(null)
      setSendError(null)
      queryClient.invalidateQueries({ queryKey: ['chat', matchId, 'messages'] })
    },
    onError: (err) => {
      if (err instanceof PiiInterruptError) {
        setWarning({ message: err.warning.message, body: draft })
      } else {
        setSendError(err instanceof ApiError ? err.message : 'Message could not be sent')
      }
    },
  })

  // v2: the server no longer marks messages read when they are fetched. Send
  // an explicit receipt only while this thread is actually visible and there
  // is something unread from the other person.
  const unreadFromOther = messages?.some((m) => m.sender_id === match?.candidate_id && !m.is_read) ?? false
  useEffect(() => {
    if (!matchId || !unreadFromOther || document.visibilityState !== 'visible') return
    chatApi
      .markRead(matchId)
      .then(() => queryClient.invalidateQueries({ queryKey: ['chat', matchId, 'messages'] }))
      .catch(() => {})
  }, [matchId, unreadFromOther, queryClient])

  // Runs after the first render that actually had messages in hand, so every
  // later poll (and anything the user sends) counts as new and animates.
  useEffect(() => {
    if (messages && firstPaintRef.current) firstPaintRef.current = false
  }, [messages])

  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!draft.trim()) return
    sendMutation.mutate({ body: draft })
  }

  function dismissWarning() {
    setWarning(null)
  }

  if (matchFailed || messagesFailed) {
    return (
      <AppShell>
        <div className="max-w-md mx-auto px-4 py-12 text-center">
          <p className="text-[15px] font-medium mb-1.5">This conversation isn't available</p>
          <p className="text-[13.5px] text-cohab-muted mb-5">
            The link may be old, or chat hasn't opened for this match yet. Chat opens once you've both said you're interested.
          </p>
          <Link to="/chats" className="text-cohab-primary font-medium text-[14px]">
            Back to your chats
          </Link>
        </div>
      </AppShell>
    )
  }

  if (isLoading || !match) {
    return (
      <AppShell hideBottomNav>
        {/* Same two-pane frame as the loaded state, so the rail does not pop
            in once the conversation resolves. */}
        <div className="cohab-desktop:max-w-[1800px] cohab-desktop:mx-auto cohab-desktop:px-6 cohab-desktop:my-8">
          <div className="cohab-desktop:grid cohab-desktop:grid-cols-[320px_1fr] cohab-desktop:h-[calc(100vh-170px)] cohab-desktop:min-h-[560px] cohab-desktop:bg-cohab-card cohab-desktop:border cohab-desktop:border-cohab-border cohab-desktop:rounded-[18px] cohab-desktop:overflow-hidden">
            <ThreadRail activeMatchId={matchId} />
            <div className="px-4 py-10 text-cohab-muted cohab-desktop:px-6">Loading…</div>
          </div>
        </div>
      </AppShell>
    )
  }

  const pct = scorePercent(match.combined_score)
  const listing = match.listing

  return (
    <AppShell hideBottomNav>
      {/* Desktop is the mockup's two-pane screen 9: the thread rail stays
          visible beside the open conversation, so the other people you are
          talking to are reachable without going back to /chats (D-13.15).
          The rail is desktop-only — on a phone the list and the conversation
          are separate screens, which is also what WhatsApp does. */}
      <div className="cohab-desktop:max-w-[1800px] cohab-desktop:mx-auto cohab-desktop:px-6 cohab-desktop:my-8">
        <div className="cohab-desktop:grid cohab-desktop:grid-cols-[320px_1fr] cohab-desktop:h-[calc(100vh-170px)] cohab-desktop:min-h-[560px] cohab-desktop:bg-cohab-card cohab-desktop:border cohab-desktop:border-cohab-border cohab-desktop:rounded-[18px] cohab-desktop:overflow-hidden">
          {/* ThreadRail carries its own `hidden cohab-desktop:flex`. Wrapping
              it in a div made it a flex *item* that sized to its content, so
              the rail's border stopped halfway down the card. */}
          <ThreadRail activeMatchId={matchId} />

          <div className="cohab-desktop:flex cohab-desktop:flex-col cohab-desktop:min-h-0 cohab-desktop:overflow-hidden">
        {/* Header — mobile */}
        <div className="cohab-desktop:hidden flex items-center gap-2 px-2 py-1.5 border-b border-cohab-border-soft bg-cohab-card">
          <Link
            to={`/matches/${matchId}`}
            className="w-10 h-11 flex items-center justify-center text-cohab-ink text-[22px]"
          >
            ←
          </Link>
          <Avatar name={match.candidate_name} src={match.candidate_avatar_url} size={36} />
          <div className="flex-1 min-w-0">
            <div className="text-[15px] font-semibold text-cohab-ink truncate">{match.candidate_name}</div>
            <div className="text-[12px] text-cohab-primary mt-0.5 truncate">
              Mutual match · {pct}%{listing ? ` · ${listing.locality}` : ''}
            </div>
          </div>
          <SafetyActions userId={match.candidate_id} userName={match.candidate_name} />
        </div>

        {/* Header — desktop */}
        <div className="hidden cohab-desktop:flex items-center gap-3 px-6 py-[15px] border-b border-cohab-border">
          <Avatar name={match.candidate_name} src={match.candidate_avatar_url} size={34} />
          <div className="flex-1">
            <div className="flex items-center gap-[9px]">
              <span className="text-[15px] font-semibold text-cohab-ink">{match.candidate_name}</span>
              <span className="border border-cohab-border rounded-full px-[9px] py-[3px] text-[11px] font-medium text-cohab-primary bg-cohab-tint">
                Mutual match · {pct}
              </span>
            </div>
            {listing && (
              <p className="text-[12px] text-cohab-subtle mt-[3px]">
                {listing.locality} · ₹{listing.rent_per_person.toLocaleString('en-IN')} · available{' '}
                {listing.available_from}
              </p>
            )}
          </div>
          <Link to={`/matches/${matchId}`}>
            <Button variant="secondary" size="sm" className="!rounded-[10px]">
              View match
            </Button>
          </Link>
          <Link to={`/matches/${matchId}/contact-share`}>
            <Button
              size="sm"
              className="!rounded-[10px] !bg-cohab-card !text-cohab-primary border border-cohab-primary hover:!bg-cohab-tint"
            >
              Share contact
            </Button>
          </Link>
          <SafetyActions userId={match.candidate_id} userName={match.candidate_name} />
        </div>

        {/* Message log */}
        <div className="flex-1 min-h-0 overflow-auto px-3 py-3.5 pb-32 cohab-desktop:pb-3.5 bg-cohab-thread-bg cohab-desktop:bg-cohab-bg cohab-desktop:px-6 cohab-desktop:py-[22px]">
          <p className="cohab-desktop:hidden self-center max-w-[88%] mx-auto bg-cohab-accent-tint rounded-2xl px-[13px] py-2 mb-3 text-[11.5px] leading-[1.45] text-center text-cohab-muted-mobile">
            Messages are moderated. Phone numbers, emails and social handles stay hidden until you both agree to
            share contact details.
          </p>
          <p className="hidden cohab-desktop:block text-center text-[11.5px] text-cohab-subtle mb-[18px]">
            Contact details are hidden until you both agree to share them
          </p>

          <div className="flex flex-col gap-[7px] cohab-desktop:gap-3">
            {messages && messages.length === 0 && (
              <p className="text-[13px] text-cohab-subtle text-center py-8">
                Say hi — talk here before sharing any contact details.
              </p>
            )}
            {messages?.map((m) => {
              const mine = m.sender_id === me?.id
              return (
                <MessageEnter
                  key={m.id}
                  id={m.id}
                  mine={mine}
                  firstPaint={firstPaintRef.current}
                  className={cn('flex flex-col max-w-[80%] cohab-desktop:max-w-[62%]', mine ? 'self-end items-end' : 'self-start items-start')}
                >
                  <div
                    className={cn(
                      // Sticker bubbles (D-14.23): yours volt, theirs white with an
                      // ink outline; volt keeps black text in both themes.
                      'text-[15px] font-medium leading-[1.4] px-4 py-2.5',
                      mine
                        ? 'bg-cohab-volt text-[#0b0b0b] rounded-[20px] rounded-br-[5px]'
                        : 'bg-cohab-card text-cohab-ink border-2 border-cohab-ink rounded-[20px] rounded-bl-[5px]',
                    )}
                  >
                    {m.body}
                  </div>
                  <span className="text-[10.5px] cohab-desktop:text-[11px] text-cohab-subtle-mobile cohab-desktop:text-cohab-subtle mt-1">
                    {messageTime(m.created_at)}
                    {mine && m.is_read ? ' · Read' : ''}
                  </span>
                </MessageEnter>
              )
            })}
          </div>
        </div>

        {/* Composer */}
        <div className="fixed bottom-0 inset-x-0 z-30 cohab-desktop:static cohab-desktop:z-auto bg-cohab-thread-bg cohab-desktop:bg-cohab-card px-2.5 py-2 cohab-desktop:px-6 cohab-desktop:pt-3.5 cohab-desktop:pb-4 cohab-desktop:border-t cohab-desktop:border-cohab-border">
          {warning && (
            <>
              {/* PII banner — mobile */}
              <div role="alert" className="cohab-desktop:hidden border border-cohab-warn-border bg-cohab-accent-tint rounded-2xl px-[13px] py-3 mb-2.5">
                <p className="text-[13.5px] font-semibold text-cohab-accent mb-1">
                  You're about to share contact details
                </p>
                <p className="text-[13px] leading-[1.45] text-cohab-warn">{warning.message}</p>
                <div className="flex gap-2 mt-[11px] flex-wrap">
                  <Link
                    to={`/matches/${matchId}/contact-share`}
                    className="h-10 px-3.5 rounded-full bg-cohab-accent text-cohab-on-fill text-[13.5px] font-semibold flex items-center"
                  >
                    Share contact instead
                  </Link>
                  <button
                    type="button"
                    onClick={dismissWarning}
                    className="h-10 px-3.5 rounded-full border border-cohab-warn-border bg-cohab-card text-cohab-warn text-[13.5px] font-semibold cursor-pointer"
                  >
                    Remove it
                  </button>
                  <button
                    type="button"
                    onClick={() => sendMutation.mutate({ body: warning.body, confirm: true })}
                    disabled={sendMutation.isPending}
                    className="text-[12.5px] font-medium text-cohab-muted-mobile underline underline-offset-2"
                  >
                    Send anyway
                  </button>
                </div>
              </div>

              {/* PII banner — desktop */}
              <div role="alert" className="hidden cohab-desktop:flex border-[1.5px] border-cohab-accent rounded-xl px-4 py-3.5 mb-3 gap-3.5 items-start">
                <div className="flex-1">
                  <p className="text-[13px] font-semibold text-cohab-accent mb-1">
                    Careful — that looks like contact info
                  </p>
                  <p className="text-[13px] leading-[1.5] text-cohab-ink">
                    Contact details stay off chat until you both agree to share them. Sharing them here removes
                    that protection and cannot be undone.
                  </p>
                  <button
                    type="button"
                    onClick={() => sendMutation.mutate({ body: warning.body, confirm: true })}
                    disabled={sendMutation.isPending}
                    className="text-[12px] font-medium text-cohab-muted underline underline-offset-2 mt-2"
                  >
                    Send anyway
                  </button>
                </div>
                <div className="flex flex-col gap-2 flex-none">
                  <Link to={`/matches/${matchId}/contact-share`}>
                    <Button size="sm" className="!rounded-[10px] whitespace-nowrap w-full">
                      Share Contact instead
                    </Button>
                  </Link>
                  <Button variant="secondary" size="sm" onClick={dismissWarning} className="!rounded-[10px] whitespace-nowrap">
                    Edit message
                  </Button>
                </div>
              </div>
            </>
          )}

          <form onSubmit={submit} className="flex gap-2 items-end">
            {/* Textarea — mobile pill */}
            <div
              className={cn(
                'cohab-desktop:hidden flex-1 flex items-end bg-cohab-card rounded-full px-3.5 border border-cohab-border',
                warning && 'border border-cohab-accent',
              )}
            >
              <textarea
                rows={1}
                placeholder={`Message ${match.candidate_name.split(' ')[0]}…`}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                className="flex-1 min-h-[42px] max-h-[90px] border-none bg-transparent py-3 text-[14.5px] text-cohab-ink resize-none outline-none box-border"
              />
            </div>
            <button
              type="submit"
              disabled={sendMutation.isPending || !draft.trim()}
              className={cn(
                'cohab-press cohab-desktop:hidden w-[46px] h-[46px] rounded-full border-none text-cohab-on-fill text-[17px] font-semibold flex-none flex items-center justify-center disabled:opacity-50 cursor-pointer',
                warning ? 'bg-cohab-accent' : 'bg-cohab-primary',
              )}
            >
              ↑
            </button>

            {/* Textarea — desktop */}
            <Textarea
              rows={1}
              placeholder={`Message ${match.candidate_name.split(' ')[0]}…`}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              className={cn('hidden cohab-desktop:block flex-1 min-h-11 py-2.5', warning && 'border-cohab-accent')}
            />
            <Button
              type="submit"
              variant={warning ? 'secondary' : 'primary'}
              disabled={sendMutation.isPending || !draft.trim()}
              className="hidden cohab-desktop:inline-flex"
            >
              Send
            </Button>
          </form>
          <p className="hidden cohab-desktop:block text-[11.5px] text-cohab-subtle mt-[9px]">
            Try typing a phone number or an email address to see the check. Abusive content is flagged for
            moderator review, not blocked.
          </p>
          {sendError && <p className="text-[12px] text-cohab-accent text-center pt-2">{sendError}</p>}
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  )
}
