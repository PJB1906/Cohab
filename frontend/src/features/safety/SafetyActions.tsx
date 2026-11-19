import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { ReportDialog } from './ReportDialog'
import { BlockConfirmDialog } from './BlockConfirmDialog'

/** Small "Report or block" trigger + the two dialogs it opens. Shared by
 * match detail and chat, so a user always has a safety exit on any screen
 * where they're looking at, or talking to, a specific other person. */
export function SafetyActions({ userId, userName }: { userId: string; userName: string }) {
  const [open, setOpen] = useState<'menu' | 'report' | 'block' | null>(null)

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen('menu')}
        className="text-[12.5px] text-cohab-subtle underline underline-offset-2 cursor-pointer flex-none"
      >
        Report or block
      </button>

      {open === 'menu' && (
        <div className="fixed inset-0 bg-[#0b1033]/55 backdrop-blur-[2px] flex items-end sm:items-center justify-center p-4 z-50">
          <div className="bg-cohab-card rounded-2xl p-6 max-w-sm w-full">
            <h2 className="text-base font-semibold mb-4">{userName}</h2>
            <div className="flex flex-col gap-2">
              <Button variant="secondary" onClick={() => setOpen('report')} className="w-full">
                Report {userName}
              </Button>
              <Button variant="danger" onClick={() => setOpen('block')} className="w-full">
                Block {userName}
              </Button>
              <Button variant="ghost" onClick={() => setOpen(null)} className="w-full">
                Cancel
              </Button>
            </div>
          </div>
        </div>
      )}

      {open === 'report' && (
        <ReportDialog
          reportedUserId={userId}
          reportedUserName={userName}
          onClose={() => setOpen(null)}
          onBlockRequested={() => setOpen('block')}
        />
      )}
      {open === 'block' && (
        <BlockConfirmDialog blockedUserId={userId} blockedUserName={userName} onClose={() => setOpen(null)} />
      )}
    </>
  )
}
