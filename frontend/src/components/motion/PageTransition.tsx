import { useLayoutEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'
import { gsap, MOTION, prefersReducedMotion, refreshScrollTriggers } from '@/lib/motion'

/** Entrance for whatever route just mounted.
 *
 * Deliberately an enter-only transition, not a cross-fade: an exit animation
 * would hold the old screen on-screen after the user has already committed
 * to leaving it, which makes every navigation feel slower than it is. This
 * plays on the incoming content only, and it is short.
 *
 * It also resets scroll to the top on a route change — React Router does not
 * do this — and refreshes ScrollTrigger once the new screen has laid out, so
 * the reveals on it measure against the correct document height.
 */
export function PageTransition({ children }: { children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null)
  const { pathname } = useLocation()

  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return

    window.scrollTo({ top: 0, left: 0, behavior: 'auto' })

    if (prefersReducedMotion()) {
      refreshScrollTriggers()
      return
    }

    const ctx = gsap.context(() => {
      gsap.fromTo(
        el,
        { opacity: 0, y: MOTION.pageRise },
        {
          opacity: 1,
          y: 0,
          duration: MOTION.page,
          ease: MOTION.easeOut,
          clearProps: 'transform',
          onComplete: refreshScrollTriggers,
        },
      )
    }, el)

    return () => ctx.revert()
  }, [pathname])

  return <div ref={ref}>{children}</div>
}
