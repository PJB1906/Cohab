import { AppShell } from '@/components/AppShell'
import { RevealGroup } from '@/components/motion/RevealGroup'
import { ThreadRail, ThreadRow, useThreads } from '@/features/chat/ThreadList'
import { cn } from '@/lib/utils'
import { PageBanner } from '@/components/PageBanner'
import { EmptyState } from '@/components/EmptyState'

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
          className="grid grid-cols-[320px_1fr] surface rounded-[26px] overflow-hidden"
          style={{ height: 'calc(100vh - 170px)', minHeight: 560 }}
        >
          <ThreadRail />
          <div className="relative isolate grain flex flex-col items-center justify-center gap-2 text-center text-white px-8">
            <img src="/photos/friends-couch.webp" alt="" aria-hidden className="absolute inset-0 -z-20 w-full h-full object-cover" />
            <div className="absolute inset-0 -z-10 bg-[linear-gradient(135deg,rgb(8_12_46/0.94),rgb(27_52_209/0.8))]" />
            <h2 className="poster text-white text-[56px]">Pick a conversation</h2>
            <p className="text-[14px] text-white/80 max-w-[40ch]">Chat opens once you both say yes. Choose a thread on the left to read it.</p>
          </div>
        </div>
      </div>

      {/* Mobile */}
      <div className="cohab-desktop:hidden max-w-2xl mx-auto px-4 py-7">
        <PageBanner photo="/photos/friends-couch.webp" title="Chats" size="sm" className="mb-5">
          <p className="text-[13px] leading-[1.4] text-white/85">Threads open only after both of you say yes.</p>
        </PageBanner>

        {isLoading && <p className="text-cohab-muted">Loading…</p>}
        {error && <p className="text-cohab-accent">Couldn't load your chats. Try again shortly.</p>}
        {!isLoading && threads.length === 0 && (
          <EmptyState photo="/photos/friends-laughing.webp" title="No chats yet">
            Chat unlocks once a match says yes back. Express interest on a few people to get started.
          </EmptyState>
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
