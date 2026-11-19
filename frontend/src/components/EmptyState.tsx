import { cn } from '@/lib/utils'

/** An empty screen that still has a point of view: a photograph, a plain
 * sentence about why it is empty, and what to do next. The photo is scenery,
 * never a claim about a person or a room. */
export function EmptyState({
  photo,
  title,
  children,
  action,
  className,
}: {
  photo: string
  title: string
  children?: React.ReactNode
  action?: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn('surface rounded-[28px] overflow-hidden grid sm:grid-cols-[minmax(0,240px)_1fr]', className)}>
      <div className="relative isolate min-h-[130px]">
        <img src={photo} alt="" aria-hidden className="absolute inset-0 -z-20 w-full h-full object-cover" />
        <div className="absolute inset-0 -z-10 bg-[linear-gradient(135deg,rgb(8_12_46/0.55),rgb(42_75_255/0.35))]" />
      </div>
      <div className="p-6 cohab-desktop:p-7 flex flex-col justify-center gap-2.5">
        <h2 className="poster text-[34px] cohab-desktop:text-[40px]">{title}</h2>
        {children && <p className="text-[14px] leading-[1.55] text-cohab-muted max-w-[52ch]">{children}</p>}
        {action}
      </div>
    </div>
  )
}

export const emptyActionClass =
  'cohab-press self-start mt-1 h-11 px-6 rounded-full bg-cohab-primary text-cohab-on-fill text-[14px] font-bold inline-flex items-center shadow-[0_10px_22px_-10px_rgb(42_75_255/0.75)]'
