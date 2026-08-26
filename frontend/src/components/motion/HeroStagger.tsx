import { useLayoutEffect, useRef } from 'react'
import { boundedStagger, gsap, MOTION, prefersReducedMotion, settle } from '@/lib/motion'

/** Mount-time staggered entrance for content that is already above the fold.
 *
 * Distinct from `RevealGroup`, which waits for a scroll trigger: on a first
 * screen — the landing panel, an empty state — there is nothing to scroll to,
 * so the stagger has to run on mount or it never runs at all. Children opt in
 * with `data-stagger-item`.
 */
export function HeroStagger({
  children,
  className,
  delay = 0.08,
}: {
  children: React.ReactNode
  className?: string
  delay?: number
}) {
  const ref = useRef<HTMLDivElement>(null)

  useLayoutEffect(() => {
    const root = ref.current
    if (!root) return
    const items = gsap.utils.toArray<HTMLElement>('[data-stagger-item]', root)
    if (items.length === 0) return

    if (prefersReducedMotion()) {
      settle(items)
      return
    }

    const ctx = gsap.context(() => {
      gsap.fromTo(
        items,
        { opacity: 0, y: MOTION.rise },
        {
          opacity: 1,
          y: 0,
          duration: MOTION.base,
          ease: MOTION.easeOut,
          stagger: boundedStagger(items.length),
          delay,
          clearProps: 'transform',
        },
      )
    }, root)

    return () => ctx.revert()
  }, [delay])

  return (
    <div ref={ref} className={className}>
      {children}
    </div>
  )
}
