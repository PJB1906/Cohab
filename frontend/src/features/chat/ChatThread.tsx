import { useState } from 'react'
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
import { cn } from '@/lib/utils'

/** Screen 9 (PRD §9): moderated thread, no contact details visible until
 * Share Contact. Polls every 3s (PRD §9.1's own "3-second poll" reference)
 * rather than a WebSocket — CLAUDE.md/PRD both defer that transport. */
export function ChatThread() {
  const { matchId } = useParams<{ matchId: string }>()
  const { data: me } = useSession()
  const queryClient = useQueryClient()

  const [draft, setDraft] = useState('')
  const [warning, setWarning] = useState<{ message: string; body: string } | null>(null)
  const [sendError, setSendError] = useState<string | null>(null)

  const { data: match } = useQuery({
    queryKey: ['match', matchId],
    queryFn: () => matchesApi.explanation(matchId!),
    enabled: Boolean(matchId),
  })

  const { data: messages, isLoading } = useQuery({
    queryKey: ['chat', matchId, 'messages'],
    queryFn: () => chatApi.list(matchId!),
    enabled: Boolean(matchId),
    refetchInterval: 3000,
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

  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!draft.trim()) return
    sendMutation.mutate({ body: draft })
  }

  if (isLoading || !match) {
    return (
      <AppShell>
        <div className="max-w-2xl mx-auto px-4 py-10 text-cohab-muted">Loading…</div>
      </AppShell>
    )
  }

  return (
    <AppShell>
      <div className="max-w-2xl mx-auto px-4 py-5 pb-32">
        <div className="flex items-center justify-between mb-4">
          <Link to={`/matches/${matchId}`} className="text-[13px] font-medium text-cohab-primary">
            ← Match detail
          </Link>
          <Link to={`/matches/${matchId}/contact-share`} className="text-[13px] font-medium text-cohab-primary">
            Share contact →
          </Link>
        </div>

        <div className="flex items-center gap-3 mb-5">
          <Avatar name={match.candidate_name} src={match.candidate_avatar_url} size={40} />
          <h1 className="text-lg font-semibold flex-1">{match.candidate_name}</h1>
          <SafetyActions userId={match.candidate_id} userName={match.candidate_name} />
        </div>

        <div className="flex flex-col gap-2.5">
          {messages && messages.length === 0 && (
            <p className="text-[13px] text-cohab-subtle text-center py-8">
              Say hi — talk here before sharing any contact details.
            </p>
          )}
          {messages?.map((m) => {
            const mine = m.sender_id === me?.id
            return (
              <div
                key={m.id}
                className={cn(
                  'max-w-[80%] rounded-2xl px-4 py-2.5 text-[14px]',
                  mine
                    ? 'self-end bg-cohab-primary text-white rounded-br-sm'
                    : 'self-start bg-white border border-cohab-border rounded-bl-sm',
                )}
              >
                {m.body}
              </div>
            )
          })}
        </div>
      </div>

      <div className="fixed bottom-0 inset-x-0 bg-white border-t border-cohab-border">
        <form onSubmit={submit} className="max-w-2xl mx-auto px-4 py-3 flex gap-2 items-end">
          <Textarea
            rows={1}
            placeholder="Type a message…"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            className="flex-1 min-h-11 py-2.5"
          />
          <Button type="submit" disabled={sendMutation.isPending || !draft.trim()}>
            Send
          </Button>
        </form>
        {sendError && <p className="text-[12px] text-cohab-accent text-center pb-2">{sendError}</p>}
      </div>

      {warning && (
        <div className="fixed inset-0 bg-black/40 flex items-end sm:items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl p-6 max-w-sm w-full">
            <h2 className="text-base font-semibold mb-2">Careful — that looks like contact info</h2>
            <p className="text-[13.5px] text-cohab-muted mb-5">{warning.message}</p>
            <div className="flex flex-col gap-2">
              <Button
                variant="secondary"
                onClick={() => setWarning(null)}
                className="w-full"
              >
                Edit my message
              </Button>
              <Link to={`/matches/${matchId}/contact-share`} className="w-full">
                <Button variant="secondary" className="w-full">
                  Use Share Contact instead
                </Button>
              </Link>
              <Button
                variant="ghost"
                onClick={() => sendMutation.mutate({ body: warning.body, confirm: true })}
                disabled={sendMutation.isPending}
              >
                Send anyway
              </Button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  )
}
