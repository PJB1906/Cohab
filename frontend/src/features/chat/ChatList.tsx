import { AppShell } from '@/components/AppShell'
import { RevealGroup } from '@/components/motion/RevealGroup'
import { ThreadRail, ThreadRow, useThreads } from '@/features/chat/ThreadList'
import { cn } from '@/lib/utils'

/** Chat thread list — the desktop mockup's screen 9 left panel
 * (`grid-template-columns:320px 1fr`). Mounted at `/chats` (`AppShell`'s
 * "Chat" nav link and `BottomNav`'s "Chats" tab both point here).
 *
 * The rail itself now lives in ThreadList.tsx, because `ChatThread` renders
 * the same rail beside an open conversation (D-13.15). This screen is the
 * nothing-selected state of that two-pane layout.
 */
export function ChatList() {
  const { threads, isLoading, error } = useThreads()

  return (
    <AppShell>
      {/* Desktop */}
      <div className="hidden cohab-desktop:block max-w-[1800px] mx-auto px-6 py-6">
        <div
          className="grid grid-cols-[320px_1fr] bg-cohab-card border border-cohab-border rounded-[18px] overflow-hidden"
          style={{ height: 'calc(100vh - 170px)', minHeight: 560 }}
        >
          <ThreadRail />
          <div className="flex items-center justify-center text-[13px] text-cohab-subtle">
            Select a conversation to view it.
          </div>
        </div>
      </div>

      {/* Mobile */}
      <div className="cohab-desktop:hidden max-w-2xl mx-auto px-4 py-7">
        <h1 className="poster text-[56px] cohab-desktop:text-[72px] mb-2">Chats</h1>
        <p className="text-[13.5px] text-cohab-muted mb-6">
          Threads open only after both of you express interest.
        </p>

        {isLoading && <p className="text-cohab-muted">Loading…</p>}
        {error && <p className="text-cohab-accent">Couldn't load your chats. Try again shortly.</p>}
        {!isLoading && threads.length === 0 && (
          <p className="text-cohab-muted">
            No open threads yet — chat unlocks once a match expresses interest back.
          </p>
        )}

        <RevealGroup className={cn('flex flex-col gap-3')} runKey={threads.length}>
          {threads.map((item) => (
            <ThreadRow key={item.match_id} item={item} variant="mobile" />
          ))}
        </RevealGroup>
      </div>
    </AppShell>
  )
}
