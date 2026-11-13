import { useEffect, useId, useRef } from 'react'
import { cn } from '@/lib/utils'

/** Modal sheet (mobile) / centred dialog (desktop).
 *
 * v2 audit: this had no dialog semantics (screen readers announced nothing),
 * no Escape or backdrop close, and on desktop no close control at all, so
 * the only way out was the dialog's own buttons. It now carries
 * role="dialog" + aria-modal + aria-labelledby, closes on Escape and on a
 * backdrop click, moves focus into itself on open, and gives focus back to
 * whatever opened it on close. */
export function Dialog({
  open,
  onClose,
  title,
  children,
  className,
}: {
  open: boolean
  onClose: () => void
  title?: React.ReactNode
  children: React.ReactNode
  className?: string
}) {
  const titleId = useId()
  const panelRef = useRef<HTMLDivElement>(null)
  // Keep the latest onClose without re-running the effect (and stealing
  // focus back) every time a parent re-renders with a new closure.
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose

  useEffect(() => {
    if (!open) return
    const opener = document.activeElement as HTMLElement | null
    panelRef.current?.focus()
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onCloseRef.current()
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      opener?.focus?.()
    }
  }, [open])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-end cohab-desktop:items-center justify-center z-50 cohab-desktop:p-4"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title !== undefined ? titleId : undefined}
        tabIndex={-1}
        className={cn(
          'bg-cohab-card w-full flex flex-col outline-none',
          'rounded-t-2xl max-h-[90vh]',
          'cohab-desktop:rounded-2xl cohab-desktop:max-w-sm cohab-desktop:max-h-[85vh]',
          className,
        )}
      >
        {title !== undefined && (
          <div className="flex-none flex items-center justify-center relative h-11 cohab-desktop:hidden border-b border-cohab-border-soft">
            <span className="text-[15px] font-semibold text-cohab-ink px-11 truncate">{title}</span>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="absolute right-0 top-0 w-11 h-11 flex items-center justify-center text-cohab-subtle-mobile text-xl cursor-pointer"
            >
              ✕
            </button>
          </div>
        )}
        <div className="overflow-y-auto p-6 cohab-desktop:p-6">
          {title !== undefined && (
            // aria-labelledby may point at an element hidden with
            // display:none, so this one id labels the dialog at every width.
            <div className="hidden cohab-desktop:flex items-start justify-between gap-3 mb-2">
              <h2 id={titleId} className="text-base font-semibold">
                {title}
              </h2>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close"
                className="-mt-1 -mr-2 w-8 h-8 flex-none rounded-full flex items-center justify-center text-cohab-subtle hover:bg-cohab-tint cursor-pointer"
              >
                ✕
              </button>
            </div>
          )}
          {children}
        </div>
      </div>
    </div>
  )
}
