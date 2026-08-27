import { useLayoutEffect, useRef } from 'react'
import { gsap, MOTION, prefersReducedMotion, refreshScrollTriggers } from '@/lib/motion'

/** Same enter-only transition as `PageTransition`, but keyed on an arbitrary
 * step string instead of the route pathname.
 *
 * `PageTransition` only fires on a real React Router navigation. The auth/
 * signup flow switches screens (login <-> signup, and the wizard's seeker /
 * form / otp / avatar steps) entirely through local `useState` — the URL
 * never changes — so `PageTransition`'s pathname key never re-fires there.
 * This is that same mechanism keyed on whatever string identifies the
 * current step instead. */
export function StepTransition({
  step,
  className,
  children,
}: {
  step: string
  className?: string
  children: React.ReactNode
}) {
  const ref = useRef<HTMLDivElement>(null)

  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return

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
  }, [step])

  return (
    <div ref={ref} className={className}>
      {children}
    </div>
  )
}
