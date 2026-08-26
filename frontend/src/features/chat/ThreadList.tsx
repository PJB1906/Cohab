import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { matchesApi } from '@/api/matches'
import { Avatar } from '@/components/ui/avatar'
import type { MatchListItem } from '@/api/types'
import { cn } from '@/lib/utils'

/** Screen 9 (PRD §9) left panel / mockup "CHAT" screen: a thread only exists
 * once both sides have expressed interest and the match has actually moved
 * into conversation — `chatting` or `contact_shared` (docs/DECISIONS.md
 * D-4.6/D-6.5). `mutual` hasn't opened a thread yet (that's what
 * MatchDetail's "start chatting" action is for); `cohabiting`/`rejected`
 * are past it. */
export const CHAT_STATES = new Set(['chatting', 'contact_shared'])

export function threadSummary(item: MatchListItem): string {
  // No last-message-preview field exists on MatchListItem yet (would need a
  // new API field backed by the most recent chat message) — falling back to
  // the same city/budget summary MatchCard already shows, rather than
  // fabricating a snippet.
  return `${item.city} · ₹${item.budget_min.toLocaleString('en-IN')}–${item.budget_max.toLocaleString('en-IN')}`
}

export function useThreads() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['matches'],
    queryFn: () => matchesApi.list(),
  })
  return { threads: data?.filter((m) => CHAT_STATES.has(m.state)) ?? [], isLoading, error }
}

export function ThreadRow({
  item,
  variant,
  active = false,
}: {
  item: MatchListItem
  variant: 'desktop' | 'mobile'
  active?: boolean
}) {
  if (variant === 'desktop') {
    return (
      <Link
        to={`/matches/${item.match_id}/chat`}
        aria-current={active ? 'page' : undefined}
        className={cn(
          'flex items-center gap-3 w-full box-border border-l-[3px] border-b border-cohab-border-soft px-[18px] py-3.5 text-left transition-colors',
          active
            ? 'border-l-cohab-primary bg-cohab-tint'
            : 'border-l-transparent bg-cohab-card hover:bg-cohab-tint',
        )}
      >
        <Avatar name={item.candidate_name} src={item.avatar_url} size={38} />
        <div className="flex-1 min-w-0 text-left">
          <span
            className={cn(
              'block text-[14px] truncate',
              active ? 'font-semibold text-cohab-primary' : 'font-semibold text-cohab-ink',
            )}
          >
            {item.candidate_name}
          </span>
          <p className="text-[12.5px] text-cohab-muted mt-1 truncate">{threadSummary(item)}</p>
        </div>
      </Link>
    )
  }

  return (
    <Link
      to={`/matches/${item.match_id}/chat`}
      data-reveal-item=""
      className="block cohab-lift bg-cohab-card border border-cohab-border-soft rounded-2xl p-[15px] no-underline"
    >
      <div className="flex gap-3 items-center">
        <Avatar name={item.candidate_name} src={item.avatar_url} size={44} />
        <div className="flex-1 min-w-0">
          <div className="text-[16px] font-semibold text-cohab-ink truncate">{item.candidate_name}</div>
          <div className="text-[12.5px] text-cohab-muted-mobile mt-0.5 truncate">{threadSummary(item)}</div>
        </div>
      </div>
    </Link>
  )
}

/** The desktop left rail, shared by `/chats` (nothing selected) and
 * `/matches/:matchId/chat` (that thread highlighted). Extracted from
 * ChatList so the open conversation can show the other people's names
 * beside it, the way WhatsApp Web does — previously the thread route
 * rendered the conversation alone and you had to go back to `/chats` to
 * see who else you were talking to. */
export function ThreadRail({ activeMatchId }: { activeMatchId?: string }) {
  const { threads, isLoading, error } = useThreads()

  return (
    // `hidden cohab-desktop:flex` lives here rather than on a wrapper: as a
    // direct grid child the rail stretches to the row height, which is what
    // keeps its right border running the full height of the card.
    <div className="hidden cohab-desktop:flex border-r border-cohab-border flex-col min-h-0">
      <div className="px-5 pt-[18px] pb-3.5 border-b border-cohab-border">
        <h2 className="text-[17px] font-semibold text-cohab-ink m-0 mb-2">Chats</h2>
        <p className="text-[12px] text-cohab-subtle m-0">
          Threads open only after both of you express interest.
        </p>
      </div>
      <div className="overflow-auto flex-1">
        {isLoading && <p className="text-[13px] text-cohab-muted px-[18px] py-4">Loading…</p>}
        {error && (
          <p className="text-[13px] text-cohab-accent px-[18px] py-4">
            Couldn't load your chats. Try again shortly.
          </p>
        )}
        {!isLoading && threads.length === 0 && (
          <p className="text-[13px] text-cohab-muted px-[18px] py-4">
            No open threads yet — chat unlocks once a match expresses interest back.
          </p>
        )}
        {threads.map((item) => (
          <ThreadRow
            key={item.match_id}
            item={item}
            variant="desktop"
            active={item.match_id === activeMatchId}
          />
        ))}
      </div>
      <div className="border-t border-cohab-border px-5 py-3.5">
        <p className="text-[12px] text-cohab-subtle leading-relaxed m-0">
          Messages are stored encrypted but readable by moderators when a report is filed. They are not
          end-to-end encrypted.
        </p>
      </div>
    </div>
  )
}
