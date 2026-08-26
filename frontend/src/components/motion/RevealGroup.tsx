import { useLayoutEffect, useRef } from 'react'
import {
  boundedStagger,
  gsap,
  MOTION,
  prefersReducedMotion,
  ScrollTrigger,
  settle,
} from '@/lib/motion'

/** Staggered entrance for a list, batched by what is actually on screen.
 *
 * `ScrollTrigger.batch` — rather than one trigger per card — is what keeps a
 * long ranked list honest: cards that share a screenful arrive together as
 * one stagger, and cards further down wait until they are scrolled to
 * instead of having silently played their entrance offscreen.
 *
 * Children opt in with `data-reveal-item`; anything else inside (an empty
 * state, a loading line, the pending-feedback banner) is left alone.
 */
export function RevealGroup({
  children,
  className,
  /** Change this whenever the list's contents change — a new filter or sort
   * re-runs the stagger, which is the feedback that the results updated. */
  runKey,
}: {
  children: React.ReactNode
  className?: string
  runKey?: string | number
}) {
  const ref = useRef<HTMLDivElement>(null)

  useLayoutEffect(() => {
    const root = ref.current
    if (!root) return
    const items = gsap.utils.toArray<HTMLElement>('[data-reveal-item]', root)
    if (items.length === 0) return

    if (prefersReducedMotion()) {
      settle(items)
      return
    }

    const stagger = boundedStagger(items.length)
    const ctx = gsap.context(() => {
      gsap.set(items, { opacity: 0, y: MOTION.rise })
      ScrollTrigger.batch(items, {
        start: 'top 92%',
        once: true,
        onEnter: (batch) =>
          gsap.to(batch, {
            opacity: 1,
            y: 0,
            duration: MOTION.base,
            ease: MOTION.easeOut,
            stagger,
            overwrite: true,
          }),
      })
    }, root)

    return () => ctx.revert()
  }, [runKey])

  return (
    <div ref={ref} className={className} data-reveal-root="">
      {children}
    </div>
  )
}
