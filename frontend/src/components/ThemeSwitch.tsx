import { useEffect, useState } from 'react'
import { Moon, Sun } from 'lucide-react'
import { getStoredChoice, resolveTheme, setTheme, watchSystemTheme } from '@/lib/theme'
import { cn } from '@/lib/utils'

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
      onClick={() => setTheme(next)}
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
