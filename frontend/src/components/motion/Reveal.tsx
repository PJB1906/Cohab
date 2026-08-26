import { useLayoutEffect, useRef } from 'react'
import { gsap, MOTION, prefersReducedMotion, settle } from '@/lib/motion'

/** Scroll-triggered entrance for a single block.
 *
 * Renders a plain element with the caller's own classes — it adds a ref and
 * `data-reveal`, nothing else — so wrapping existing markup in it cannot
 * change layout. `as` exists because several call sites need the wrapper to
 * be the grid/flex child itself rather than an extra div inside it.
 */
export function Reveal({
  children,
  className,
  as: Tag = 'div',
  delay = 0,
  y = MOTION.rise,
  start = 'top 88%',
}: {
  children: React.ReactNode
  className?: string
  as?: 'div' | 'section' | 'aside' | 'header' | 'li'
  delay?: number
  /** Travel distance in px; pass 0 for a pure fade (headers, sticky rails). */
  y?: number
  /** ScrollTrigger `start`. The 88% default fires just as the block clears
   * the fold, so content is already settled by the time it is read. */
  start?: string
}) {
  const ref = useRef<HTMLElement>(null)

  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    if (prefersReducedMotion()) {
      settle(el)
      return
    }
    const ctx = gsap.context(() => {
      gsap.fromTo(
        el,
        { opacity: 0, y },
        {
          opacity: 1,
          y: 0,
          duration: MOTION.base,
          delay,
          ease: MOTION.easeOut,
          scrollTrigger: { trigger: el, start, once: true },
        },
      )
    }, el)
    return () => ctx.revert()
  }, [delay, y, start])

  return (
    <Tag ref={ref as never} className={className} data-reveal="">
      {children}
    </Tag>
  )
}
