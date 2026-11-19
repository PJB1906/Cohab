import { useEffect, useState } from 'react'
import { Moon, Sun } from 'lucide-react'
import { getStoredChoice, resolveTheme, setTheme, watchSystemTheme } from '@/lib/theme'
import { cn } from '@/lib/utils'

/** Circular reveal from the point of the click (View Transitions API), the
 * new theme growing out of the button. Falls back to an instant switch. */
function reveal(e: React.MouseEvent<HTMLButtonElement>, apply: () => void): void {
  const doc = document as Document & { startViewTransition?: (cb: () => void) => { ready: Promise<void> } }
  if (!doc.startViewTransition || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    apply()
    return
  }
  const b = e.currentTarget.getBoundingClientRect()
  const x = e.clientX || b.left + b.width / 2
  const y = e.clientY || b.top + b.height / 2
  const radius = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y))
  const t = doc.startViewTransition(apply)
  t.ready
    .then(() => {
      document.documentElement.animate(
        { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
        { duration: 700, easing: 'cubic-bezier(.22,1,.36,1)', pseudoElement: '::view-transition-new(root)' },
      )
    })
    .catch(() => {})
}

/** One-tap light/dark switch for every header (D-14.25). The full
 * light/dark/auto control stays in the account menu; this is the fast path.
 * It shows where a tap takes you: a moon in light mode, a sun in dark. */
export function ThemeSwitch({ className, onDark = false }: { className?: string; onDark?: boolean }) {
  const [theme, setLocal] = useState<'light' | 'dark'>(() => resolveTheme(getStoredChoice()))

  useEffect(() => watchSystemTheme(), [])
  // Stay in sync when another control (the account menu, the landing page)
  // changes the theme.
  useEffect(() => {
    const el = document.documentElement
    const mo = new MutationObserver(() => setLocal(el.dataset.theme === 'dark' ? 'dark' : 'light'))
    mo.observe(el, { attributes: true, attributeFilter: ['data-theme'] })
    return () => mo.disconnect()
  }, [])

  const next = theme === 'dark' ? 'light' : 'dark'
  return (
    <button
      type="button"
      onClick={(e) => reveal(e, () => setTheme(next))}
      aria-label={`Switch to ${next} mode`}
      title={`Switch to ${next} mode`}
      className={cn(
        'cohab-press relative w-10 h-10 rounded-full grid place-items-center cursor-pointer transition-colors',
        onDark ? 'text-white/75 hover:text-white hover:bg-white/10' : 'text-cohab-muted hover:text-cohab-ink hover:bg-cohab-tint',
        className,
      )}
    >
      <Moon
        aria-hidden
        className={cn(
          'size-[18px] absolute transition-[opacity,transform] duration-300 ease-[cubic-bezier(.22,1,.36,1)]',
          theme === 'light' ? 'opacity-100 rotate-0 scale-100' : 'opacity-0 -rotate-90 scale-50',
        )}
      />
      <Sun
        aria-hidden
        className={cn(
          'size-[18px] absolute transition-[opacity,transform] duration-300 ease-[cubic-bezier(.22,1,.36,1)]',
          theme === 'dark' ? 'opacity-100 rotate-0 scale-100' : 'opacity-0 rotate-90 scale-50',
        )}
      />
    </button>
  )
}
