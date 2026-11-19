/** Feeds the cursor position to `.spotlight` cards (index.css) as CSS vars. */
export function spotlightMove(e: React.PointerEvent<HTMLElement>): void {
  const el = e.currentTarget
  const r = el.getBoundingClientRect()
  el.style.setProperty('--mx', `${e.clientX - r.left}px`)
  el.style.setProperty('--my', `${e.clientY - r.top}px`)
}
