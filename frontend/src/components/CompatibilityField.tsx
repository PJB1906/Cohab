import { useEffect, useRef, useState } from 'react'
import { prefersReducedMotion } from '@/lib/motion'

/** The ambient graphic (docs/DECISIONS.md D-13.5, extended by D-13.11).
 *
 * What it draws is the product's own thesis rather than a generic particle
 * field: two populations of points drift on a dark ground, and a line is
 * struck between a pair only while they are close enough to be compatible —
 * brighter the closer they sit. Most pairs never connect. That is the
 * two-stage matcher in one image: a hard threshold first (no line at all
 * beyond the cutoff), then a graded score (opacity by proximity).
 *
 * Originally confined to the login marketing panel. The user asked for it on
 * every page's blank space, so `AmbientField` below mounts one fixed instance
 * behind the whole app. `density` and the caller's own opacity are what keep
 * that readable: behind live data it runs far sparser and dimmer than the
 * hero does, because the failure mode on an operator screen is a moderation
 * queue that looks decorated rather than legible.
 *
 * Canvas rather than hand-authored SVG, per the artifact-design guidance for
 * generative graphics. Honours `prefers-reduced-motion` by painting a single
 * static frame instead of animating.
 */
export function CompatibilityField({
  className,
  /** Divisor on area-per-node: larger means fewer, more spread-out points.
   * The hero's original value is the default so that panel is unchanged. */
  density = 14_000,
  /** Ceiling on point count. Link drawing is O(n²), so this is what keeps a
   * large viewport from turning a decorative canvas into a busy loop. */
  maxNodes = 48,
  /** Separation beyond which no line is drawn — the Stage 1 hard cutoff. */
  linkDistance = 132,
}: {
  className?: string
  density?: number
  maxNodes?: number
  linkDistance?: number
}) {
  const ref = useRef<HTMLCanvasElement>(null)
  // Re-runs the effect when the theme is switched, so the canvas repaints in
  // the new palette instead of holding the old one until a reload.
  const [theme, setTheme] = useState<string | undefined>(
    () => document.documentElement.dataset.theme,
  )

  useEffect(() => {
    const observer = new MutationObserver(() => {
      setTheme(document.documentElement.dataset.theme)
    })
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme'],
    })
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Canvas paints raw pixels, so it cannot inherit the CSS tokens the rest
    // of the app re-themes through (D-13.12). On a light ground the phosphor
    // greens wash out to near-invisible, so the palette is chosen per theme
    // and the effect re-runs when the stamped theme changes.
    const light = document.documentElement.dataset.theme === 'light'
    const LIME = light ? '47, 125, 30' : '127, 238, 100'
    const SAGE = light ? '107, 125, 103' : '140, 171, 135'
    // The dark field reads at 0.42 alpha on black; the same alpha on paper is
    // heavier than intended, so line weight drops in the light theme.
    const LINK_ALPHA = light ? 0.3 : 0.42
    const DOT_ALPHA = light ? [0.62, 0.4] : [0.85, 0.55]
    // Beyond this separation no line is drawn at all — the Stage 1 hard
    // constraint. Within it, opacity grades with closeness — Stage 2.
    const LINK_DISTANCE = linkDistance

    let width = 0
    let height = 0
    let dpr = 1
    let frame = 0

    type Node = { x: number; y: number; vx: number; vy: number; r: number; seeker: boolean }
    let nodes: Node[] = []

    // Deterministic layout: a hero that reshuffles on every reload is
    // impossible to screenshot consistently for the report.
    let seed = 8_675_309
    const rand = () => {
      seed = (seed * 1103515245 + 12345) & 0x7fffffff
      return seed / 0x7fffffff
    }

    function build() {
      const rect = canvas!.getBoundingClientRect()
      width = rect.width
      height = rect.height
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      canvas!.width = Math.round(width * dpr)
      canvas!.height = Math.round(height * dpr)
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0)

      const count = Math.max(10, Math.min(maxNodes, Math.round((width * height) / density)))
      nodes = Array.from({ length: count }, () => ({
        x: rand() * width,
        y: rand() * height,
        vx: (rand() - 0.5) * 0.16,
        vy: (rand() - 0.5) * 0.16,
        r: 1.6 + rand() * 2.2,
        // Roughly a third "have a place" — the seeker split the matcher
        // actually pairs across.
        seeker: rand() > 0.34,
      }))
    }

    function draw() {
      ctx!.clearRect(0, 0, width, height)

      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i]
          const b = nodes[j]
          // Two people who both already have a flat have nothing to offer
          // each other — the matcher will not pair them, so no line.
          if (!a.seeker && !b.seeker) continue
          const dx = a.x - b.x
          const dy = a.y - b.y
          const dist = Math.hypot(dx, dy)
          if (dist > LINK_DISTANCE) continue
          const strength = 1 - dist / LINK_DISTANCE
          ctx!.strokeStyle = `rgba(${LIME}, ${(strength * LINK_ALPHA).toFixed(3)})`
          ctx!.lineWidth = strength * 1.1
          ctx!.beginPath()
          ctx!.moveTo(a.x, a.y)
          ctx!.lineTo(b.x, b.y)
          ctx!.stroke()
        }
      }

      for (const n of nodes) {
        ctx!.fillStyle = n.seeker ? `rgba(${LIME}, ${DOT_ALPHA[0]})` : `rgba(${SAGE}, ${DOT_ALPHA[1]})`
        ctx!.beginPath()
        ctx!.arc(n.x, n.y, n.r, 0, Math.PI * 2)
        ctx!.fill()
      }
    }

    function step() {
      for (const n of nodes) {
        n.x += n.vx
        n.y += n.vy
        // Reflect at the edges so the field never drains out of frame.
        if (n.x < 0 || n.x > width) n.vx *= -1
        if (n.y < 0 || n.y > height) n.vy *= -1
      }
      draw()
      frame = requestAnimationFrame(step)
    }

    build()
    const reduced = prefersReducedMotion()
    if (reduced) draw()
    else frame = requestAnimationFrame(step)

    const observer = new ResizeObserver(() => {
      build()
      if (reduced) draw()
    })
    observer.observe(canvas)

    return () => {
      cancelAnimationFrame(frame)
      observer.disconnect()
    }
  }, [density, maxNodes, linkDistance, theme])

  return <canvas ref={ref} aria-hidden="true" className={className} />
}

/** One app-wide instance of the field, fixed behind every page (D-13.11).
 *
 * `fixed` rather than absolute so a single canvas covers the viewport on
 * every route instead of one per page stretching to each page's scroll
 * height — which on the 88k-row analytics screen would mean an enormous
 * canvas and a node count to match.
 *
 * Three things keep it from interfering with the app:
 * `-z-10` puts it behind all content, `pointer-events-none` means it never
 * eats a click, and it is sparser and much dimmer than the hero. `AppShell`
 * sets a transparent background on itself so this shows through; the page's
 * own black comes from `body`.
 */
export function AmbientField() {
  return (
    // Denser and more connected at the user's request: density 46k → 17k
    // (roughly 2.7x the points) and the cap raised from 48 to 110, with a
    // longer link distance so more pairs fall inside the threshold and the
    // field reads as a network rather than scattered dots. Opacity comes down
    // to compensate, so the busier field is no louder behind live data.
    <CompatibilityField
      density={17_000}
      maxNodes={110}
      linkDistance={172}
      className="fixed inset-0 w-full h-full pointer-events-none -z-10 opacity-[0.45]"
    />
  )
}
