import { motion } from 'motion/react'
import { cn } from '@/lib/utils'

const item = {
  hidden: { opacity: 0, y: 18, filter: 'blur(6px)' },
  show: { opacity: 1, y: 0, filter: 'blur(0px)', transition: { duration: 0.75, ease: [0.22, 1, 0.36, 1] as const } },
}

/** The head of a page (D-14.26): a photograph in its own colour, slowly
 * pushing in, under a neutral shade that only darkens where the words sit.
 * Title and copy rise in one after another. The photo is scenery, never a
 * claim about a member or a room. */
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
        'relative isolate grain overflow-hidden rounded-[28px] text-white bg-[#0d0f14] shadow-[var(--shadow-soft)]',
        size === 'sm' && 'min-h-[150px]',
        size === 'md' && 'min-h-[170px] cohab-desktop:min-h-[230px]',
        size === 'lg' && 'min-h-[220px] cohab-desktop:min-h-[300px]',
        className,
      )}
    >
      <img src={photo} alt="" aria-hidden className="kenburns absolute inset-0 -z-20 w-full h-full object-cover" />
      <div className="absolute inset-0 -z-10 bg-[linear-gradient(100deg,rgb(10_11_15/0.88)_0%,rgb(10_11_15/0.66)_38%,rgb(10_11_15/0.18)_72%,rgb(10_11_15/0)_100%),linear-gradient(0deg,rgb(10_11_15/0.45)_0%,rgb(10_11_15/0)_55%)]" />
      <motion.div
        initial="hidden"
        animate="show"
        variants={{ show: { transition: { staggerChildren: 0.08, delayChildren: 0.05 } } }}
        className="relative h-full p-5 cohab-desktop:p-8 flex flex-col cohab-desktop:flex-row cohab-desktop:items-end gap-5 justify-between"
      >
        <div className="min-w-0 flex flex-col gap-2.5">
          {label && (
            <motion.span data-m="" variants={item} className="label text-[10px] self-start bg-cohab-sun text-cohab-on-sun rounded-full px-2.5 py-1">
              {label}
            </motion.span>
          )}
          <motion.h1 data-m="" variants={item} className="poster text-white text-[44px] cohab-desktop:text-[76px]">
            {title}
          </motion.h1>
          {children && (
            <motion.div data-m="" variants={item} className="flex flex-col gap-2.5">
              {children}
            </motion.div>
          )}
        </div>
        {aside && (
          <motion.div data-m="" variants={item} className="shrink-0">
            {aside}
          </motion.div>
        )}
      </motion.div>
    </section>
  )
}
