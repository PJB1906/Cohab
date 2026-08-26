import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'

gsap.registerPlugin(ScrollTrigger)

/** The `[data-reveal]` hidden-state CSS in index.css is scoped to this flag,
 * which only gets set once this module has actually evaluated. If the bundle
 * fails to load, the attribute is never set, the rule never applies, and the
 * page renders fully visible with no motion — rather than as a blank shell.
 * Reduced-motion callers skip the flag entirely for the same reason. */
if (typeof document !== 'undefined') {
  const reduce =
    typeof window !== 'undefined' &&
    window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (!reduce) document.documentElement.dataset.motion = 'on'
}

/** Motion tokens (docs/DECISIONS.md D-12.1).
 *
 * The two mockups are editorial and restrained — a warm off-white page, a
 * single deep-teal accent, no gradients or shadows beyond a 1px hairline.
 * Motion has to read the same way: short travel, no overshoot, no bounce.
 * These are the only durations/eases/distances anything in the app should
 * use, so the whole surface moves as one system rather than per-screen
 * improvisation. */
export const MOTION = {
  /** Hover/press feedback and other state changes the user caused directly. */
  fast: 0.28,
  /** The default entrance. */
  base: 0.55,
  /** Hero/first-paint moments only. */
  slow: 0.9,
  /** Entrances decelerate into place; nothing overshoots. */
  easeOut: 'power3.out',
  /** Two-way state changes. */
  easeInOut: 'power2.inOut',
  /** Vertical travel for an entrance, in px. Deliberately small — an
   * editorial layout that slides 40px reads as a slideshow, not a page. */
  rise: 16,
  /** Route change. Longer than `fast` and travelling further than a reveal,
   * because a whole screen replacing another is a bigger event than one card
   * arriving — at 0.28s/10px the change was easy to miss entirely (D-13.16).
   * Still enter-only, so navigation never feels slower than it is. */
  page: 0.42,
  pageRise: 24,
  /** Per-item delay in a staggered group. */
  stagger: 0.06,
  /** Cap on total stagger time, so a 40-card list does not take 2.4s to
   * finish arriving. */
  staggerMax: 0.45,
} as const

/** `prefers-reduced-motion` is a stated accessibility need, not a
 * preference to weigh against the design. Everything below degrades to
 * "final state, immediately" rather than to a shorter animation. */
export function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/** Stagger that shrinks as the group grows, so total time stays bounded. */
export function boundedStagger(count: number): number {
  if (count <= 1) return 0
  return Math.min(MOTION.stagger, MOTION.staggerMax / (count - 1))
}

/** The set-then-animate pair used by every entrance here.
 *
 * Elements are hidden by the `[data-reveal]` CSS rule in index.css rather
 * than by JS, so there is no first-paint flash before GSAP runs. That makes
 * clearing the hidden state this module's responsibility: if an animation
 * is skipped for any reason (reduced motion, no trigger fired), it must
 * still call `settle()` or the content stays invisible. */
export function settle(targets: gsap.TweenTarget): void {
  gsap.set(targets, { opacity: 1, y: 0, clearProps: 'transform' })
}

/** Refresh ScrollTrigger after layout-changing renders (filtered lists,
 * lazily-loaded images). Debounced to one call per frame. */
let refreshQueued = false
export function refreshScrollTriggers(): void {
  if (refreshQueued) return
  refreshQueued = true
  requestAnimationFrame(() => {
    refreshQueued = false
    ScrollTrigger.refresh()
  })
}

export { gsap, ScrollTrigger }
