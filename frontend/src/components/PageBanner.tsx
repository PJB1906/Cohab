import { cn } from '@/lib/utils'

/** The head of a page: a real photograph under a navy-to-cobalt wash, the
 * title in the poster cut, and room for a line of supporting content. The
 * photo is scenery, never a claim about a specific member or room. */
export function PageBanner({
  photo,
  label,
  title,
  size = 'md',
  className,
  aside,
  children,
}: {
  photo: string
  label?: string
  title: string
  size?: 'sm' | 'md' | 'lg'
  className?: string
  aside?: React.ReactNode
  children?: React.ReactNode
}) {
  return (
    <section
      className={cn(
        'relative isolate overflow-hidden rounded-[28px] text-white shadow-[var(--shadow-soft)]',
        size === 'sm' && 'min-h-[150px]',
        size === 'md' && 'min-h-[170px] cohab-desktop:min-h-[220px]',
        size === 'lg' && 'min-h-[220px] cohab-desktop:min-h-[300px]',
        className,
      )}
    >
      <img src={photo} alt="" aria-hidden className="absolute inset-0 -z-20 w-full h-full object-cover" />
      <div className="absolute inset-0 -z-10 bg-[linear-gradient(105deg,rgb(8_12_46/0.95)_0%,rgb(27_52_209/0.84)_52%,rgb(42_75_255/0.32)_100%)]" />
      <div className="relative h-full p-5 cohab-desktop:p-8 flex flex-col cohab-desktop:flex-row cohab-desktop:items-end gap-5 justify-between">
        <div className="min-w-0 flex flex-col gap-2.5">
          {label && <span className="label text-[10px] self-start bg-cohab-sun text-cohab-on-sun rounded-full px-2.5 py-1">{label}</span>}
          <h1 className="poster text-white text-[44px] cohab-desktop:text-[72px]">{title}</h1>
          {children}
        </div>
        {aside && <div className="shrink-0">{aside}</div>}
      </div>
    </section>
  )
}
