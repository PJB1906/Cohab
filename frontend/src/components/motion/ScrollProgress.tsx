import { useLayoutEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'
import { gsap, prefersReducedMotion, ScrollTrigger } from '@/lib/motion'

/** A 2px reading-progress rule pinned under the header.
 *
 * The one piece of scroll-*driven* (as opposed to scroll-triggered) motion
 * in the app: it is scrubbed directly by scroll position, so it can never
 * disagree with where the user actually is. It hides itself on pages short
 * enough not to scroll, where a permanently-full bar would be noise.
 */
export function ScrollProgress() {
  const ref = useRef<HTMLDivElement>(null)
  const { pathname } = useLocation()

  useLayoutEffect(() => {
    const el = ref.current
    if (!el || prefersReducedMotion()) return

    const ctx = gsap.context(() => {
      gsap.set(el, { scaleX: 0, transformOrigin: 'left center' })
      ScrollTrigger.create({
        start: 0,
        end: () => document.documentElement.scrollHeight - window.innerHeight,
        onRefresh: (self) => {
          const scrollable = self.end - self.start > 40
          gsap.set(el, { autoAlpha: scrollable ? 1 : 0 })
        },
        onUpdate: (self) => gsap.set(el, { scaleX: self.progress }),
      })
    }, el)

    return () => ctx.revert()
  }, [pathname])

  return (
    <div
      ref={ref}
      aria-hidden="true"
      className="absolute left-0 right-0 -bottom-px h-0.5 bg-cohab-fill opacity-0"
    />
  )
}
