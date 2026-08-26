import { cn } from '@/lib/utils'

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
  if (!open) return null

  return (
    <div className="fixed inset-0 bg-black/40 flex items-end cohab-desktop:items-center justify-center z-50 cohab-desktop:p-4">
      <div
        className={cn(
          'bg-cohab-card w-full flex flex-col',
          'rounded-t-2xl max-h-[90vh]',
          'cohab-desktop:rounded-2xl cohab-desktop:max-w-sm cohab-desktop:max-h-[85vh]',
          className,
        )}
      >
        {title !== undefined && (
          <div className="flex-none flex items-center justify-center relative h-11 cohab-desktop:hidden border-b border-cohab-border-soft">
            <span className="text-[15px] font-semibold text-cohab-ink">{title}</span>
            <button
              type="button"
              onClick={onClose}
              className="absolute right-0 top-0 w-11 h-11 flex items-center justify-center text-cohab-subtle-mobile text-xl cursor-pointer"
            >
              ✕
            </button>
          </div>
        )}
        <div className="overflow-y-auto p-6 cohab-desktop:p-6">
          {title !== undefined && (
            <h2 className="hidden cohab-desktop:block text-base font-semibold mb-2">{title}</h2>
          )}
          {children}
        </div>
      </div>
    </div>
  )
}
