import { useLayoutEffect, useRef } from 'react'
import { gsap, MOTION, prefersReducedMotion } from '@/lib/motion'

/** Fills a score bar from 0 to its width when it scrolls into view.
 *
 * Returns a ref for the *inner* bar element. The element must already carry
 * its final `width` in a style/class — the tween animates from 0 up to that,
 * and reverts to it on cleanup, so the bar is never left at a value that
 * disagrees with the number printed beside it.
 *
 * Every bar in this app is an explanation of a score, so the fill duration
 * is tied to the value: a 0.9 bar takes visibly longer to travel than a 0.3
 * one, which makes a column of them legible as a shape while it settles.
 */
export function useBarFill<T extends HTMLElement>(pct: number) {
  const ref = useRef<T>(null)

  useLayoutEffect(() => {
    const el = ref.current
    if (!el || prefersReducedMotion()) return

    const clamped = Math.max(0, Math.min(100, pct))
    const ctx = gsap.context(() => {
      gsap.from(el, {
        width: 0,
        duration: MOTION.base + (clamped / 100) * 0.35,
        ease: MOTION.easeOut,
        scrollTrigger: { trigger: el, start: 'top 95%', once: true },
      })
    }, el)

    return () => ctx.revert()
  }, [pct])

  return ref
}
