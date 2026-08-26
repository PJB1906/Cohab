import { useLayoutEffect, useRef } from 'react'
import { gsap, MOTION, prefersReducedMotion } from '@/lib/motion'

/** Entrance for a single chat bubble that has just appeared.
 *
 * The thread polls every 3s (ChatThread), so the constraint here is *not*
 * animating on every render — that would make the whole conversation pulse
 * three times a second. A module-level set of message ids that have already
 * played is what keeps this to genuinely new messages: the first render of
 * an id animates, every subsequent poll leaves it alone.
 *
 * `seen` is deliberately module-scoped rather than per-component state. The
 * bubble unmounts and remounts as the polled list is replaced, so anything
 * held in the component would be lost exactly when it is needed.
 *
 * `firstPaint` suppresses the animation for the messages already in the
 * thread when you open it — those arrive via RevealGroup-less bulk load and
 * should simply be there, not fly in one by one.
 */
const seen = new Set<string>()

/** Bounded so a long-lived session cannot grow this without limit. Ids are
 * only needed long enough to tell "already on screen" from "just arrived",
 * so dropping the oldest half is safe: a re-animated old message is not a
 * correctness problem, and in practice they are far above the cut. */
const SEEN_LIMIT = 500

function remember(id: string): void {
  if (seen.size >= SEEN_LIMIT) {
    for (const old of [...seen].slice(0, SEEN_LIMIT / 2)) seen.delete(old)
  }
  seen.add(id)
}

export function MessageEnter({
  id,
  mine,
  firstPaint,
  className,
  children,
}: {
  id: string
  mine: boolean
  /** True while rendering the initial batch, so history does not animate. */
  firstPaint: boolean
  className?: string
  children: React.ReactNode
}) {
  const ref = useRef<HTMLDivElement>(null)

  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return

    if (seen.has(id)) return

    if (firstPaint || prefersReducedMotion()) {
      // Still counts as shown, so it never animates later.
      remember(id)
      return
    }

    const ctx = gsap.context(() => {
      gsap.fromTo(
        el,
        { opacity: 0, scale: 0.96, y: 6 },
        {
          opacity: 1,
          scale: 1,
          y: 0,
          duration: MOTION.fast,
          ease: MOTION.easeOut,
          // Grow from the corner the bubble is anchored to, so it reads as
          // emerging from the composer rather than scaling in place.
          transformOrigin: mine ? 'bottom right' : 'bottom left',
          clearProps: 'transform,opacity',
          // Marked seen only once the tween has actually finished. Marking it
          // up-front breaks under StrictMode's mount/unmount/remount: the
          // first pass would flag the id and its cleanup would revert the
          // tween, so the second pass bailed out and the bubble never moved.
          onComplete: () => remember(id),
        },
      )
    }, el)

    return () => {
      ctx.revert()
      // A StrictMode remount reverts mid-tween, before `onComplete` fired.
      // The remount re-runs this effect and plays the entrance properly, so
      // nothing is lost here; this only guards the case where the bubble is
      // unmounted for real while animating, so a later poll does not replay
      // an entrance the user has already seen.
      if (!el.isConnected) remember(id)
    }
  }, [id, mine, firstPaint])

  return (
    <div ref={ref} className={className}>
      {children}
    </div>
  )
}
