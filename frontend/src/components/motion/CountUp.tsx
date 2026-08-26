import { useLayoutEffect, useRef } from 'react'
import { gsap, MOTION, prefersReducedMotion } from '@/lib/motion'

function format(n: number, decimals: number, locale?: string): string {
  if (locale) return Math.round(n).toLocaleString(locale)
  return n.toFixed(decimals)
}

/** A number that counts up to its value when scrolled into view.
 *
 * Used only where the number is the point of the block — a compatibility
 * score, a moderator KPI — never for incidental figures like a rent range,
 * which should just be readable the instant it renders.
 *
 * The element is seeded with the *final* string, so a copy-paste, a
 * screenshot before the tween starts, and assistive tech all get the real
 * value rather than a zero.
 */
export function CountUp({
  value,
  decimals = 0,
  /** Pass e.g. 'en-IN' for grouped integers; overrides `decimals`. */
  locale,
  prefix = '',
  suffix = '',
  className,
  duration = MOTION.slow,
}: {
  value: number
  decimals?: number
  locale?: string
  prefix?: string
  suffix?: string
  className?: string
  duration?: number
}) {
  const ref = useRef<HTMLSpanElement>(null)

  useLayoutEffect(() => {
    const el = ref.current
    if (!el || prefersReducedMotion()) return

    const ctx = gsap.context(() => {
      const counter = { n: 0 }
      gsap.to(counter, {
        n: value,
        duration,
        ease: MOTION.easeOut,
        scrollTrigger: { trigger: el, start: 'top 92%', once: true },
        onUpdate: () => {
          el.textContent = prefix + format(counter.n, decimals, locale) + suffix
        },
        onComplete: () => {
          el.textContent = prefix + format(value, decimals, locale) + suffix
        },
      })
    }, el)

    return () => {
      ctx.revert()
      el.textContent = prefix + format(value, decimals, locale) + suffix
    }
  }, [value, decimals, locale, prefix, suffix, duration])

  return (
    <span ref={ref} className={className}>
      {prefix + format(value, decimals, locale) + suffix}
    </span>
  )
}
