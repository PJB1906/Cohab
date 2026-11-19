import gsap from 'gsap'

/** Magnetic raised buttons (D-14.26): a raised button leans a few pixels
 * toward the pointer and springs back when it leaves. One delegated listener
 * covers every `.btn-raised`, including links styled as buttons. Fine
 * pointers only; off for reduced motion. The CSS hover lift and press scale
 * use the individual `translate`/`scale` properties so they compose with the
 * transform GSAP writes here. */
export function installMagnetic(): void {
  if (typeof window === 'undefined') return
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  if (!window.matchMedia('(pointer: fine)').matches) return

  type Mover = { x: (v: number) => void; y: (v: number) => void }
  const movers = new WeakMap<HTMLElement, Mover>()
  const get = (el: HTMLElement): Mover => {
    let m = movers.get(el)
    if (!m) {
      m = {
        x: gsap.quickTo(el, 'x', { duration: 0.5, ease: 'power3.out' }),
        y: gsap.quickTo(el, 'y', { duration: 0.5, ease: 'power3.out' }),
      }
      movers.set(el, m)
    }
    return m
  }
  const target = (t: EventTarget | null) => (t instanceof Element ? (t.closest('.btn-raised') as HTMLElement | null) : null)

  document.addEventListener(
    'pointermove',
    (e) => {
      const el = target(e.target)
      if (!el || (el as HTMLButtonElement).disabled) return
      const r = el.getBoundingClientRect()
      const m = get(el)
      m.x(Math.max(-8, Math.min(8, (e.clientX - (r.left + r.width / 2)) * 0.18)))
      m.y(Math.max(-6, Math.min(6, (e.clientY - (r.top + r.height / 2)) * 0.3)))
    },
    { passive: true },
  )
  document.addEventListener('pointerout', (e) => {
    const el = target(e.target)
    if (!el) return
    if (e.relatedTarget instanceof Node && el.contains(e.relatedTarget)) return
    const m = get(el)
    m.x(0)
    m.y(0)
  })
}
