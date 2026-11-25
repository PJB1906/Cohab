import { Illustration, type IllustrationName } from '@/components/Illustration'
import { cn } from '@/lib/utils'

/** An empty screen with a point of view: an illustration, a plain sentence
 * about why it is empty, and what to do next. */
export function EmptyState({
  art,
  title,
  children,
  action,
  className,
}: {
  art: IllustrationName
  title: string
  children?: React.ReactNode
  action?: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn('surface rounded-[28px] overflow-hidden grid sm:grid-cols-[minmax(0,280px)_1fr] items-stretch', className)}>
      <div className="relative bg-cohab-row-tint grid place-items-center p-6 border-b sm:border-b-0 sm:border-r border-cohab-border-soft min-h-[180px]">
        <Illustration name={art} className="w-full max-w-[220px] h-[150px]" />
      </div>
      <div className="p-6 cohab-desktop:p-8 flex flex-col justify-center gap-2.5">
        <h2 className="poster text-[34px] cohab-desktop:text-[42px]">{title}</h2>
        {children && <p className="text-[14px] leading-[1.55] text-cohab-muted max-w-[52ch]">{children}</p>}
        {action}
      </div>
    </div>
  )
}

export const emptyActionClass =
  'cohab-press btn-ink self-start mt-2 h-11 px-6 rounded-full text-[14px] font-bold inline-flex items-center gap-2'
