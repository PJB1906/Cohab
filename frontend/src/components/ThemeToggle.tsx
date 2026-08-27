import { useEffect, useState } from 'react'
import { getStoredChoice, setTheme, watchSystemTheme, type ThemeChoice } from '@/lib/theme'
import { cn } from '@/lib/utils'

const OPTIONS: { value: ThemeChoice; label: string; icon: JSX.Element }[] = [
  {
    value: 'light',
    label: 'Light',
    icon: (
      <>
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
      </>
    ),
  },
  {
    value: 'dark',
    label: 'Dark',
    icon: <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />,
  },
  {
    value: 'system',
    label: 'Auto',
    icon: (
      <>
        <rect x="2" y="4" width="20" height="13" rx="2" />
        <path d="M8 21h8M12 17v4" />
      </>
    ),
  },
]

/** Segmented light / dark / auto control (docs/DECISIONS.md D-13.12).
 *
 * Three options rather than a two-state switch because "auto" is a real,
 * distinct preference: it tracks the OS and keeps tracking it. Collapsing it
 * into a binary toggle would silently freeze the user on whichever theme
 * their OS happened to be using the first time they touched the control.
 */
export function ThemeToggle({
  className,
  iconOnly = false,
}: {
  className?: string
  /** Icons with no visible label — for tight spots like the login/signup
   * panel, where the full labelled control reads as too heavy. The button
   * still needs an accessible name with the label gone, so `aria-label`
   * carries it instead of the (now icon-only) button's text content. */
  iconOnly?: boolean
}) {
  const [choice, setChoice] = useState<ThemeChoice>(() => getStoredChoice())

  // While on "auto", follow the OS if it flips mid-session.
  useEffect(() => watchSystemTheme(), [])

  function pick(next: ThemeChoice) {
    setChoice(next)
    setTheme(next)
  }

  return (
    <div
      role="radiogroup"
      aria-label="Colour theme"
      className={cn(
        'grid grid-cols-3 gap-1 rounded-lg',
        iconOnly ? 'p-0.5' : 'border border-cohab-border bg-cohab-bg p-1',
        className,
      )}
    >
      {OPTIONS.map((opt) => {
        const selected = choice === opt.value
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={selected}
            aria-label={iconOnly ? opt.label : undefined}
            onClick={() => pick(opt.value)}
            className={cn(
              'flex items-center justify-center rounded-md cursor-pointer',
              iconOnly ? 'p-1.5' : 'flex-col gap-1 py-1.5 text-[11px] font-medium',
              'transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-cohab-primary',
              selected
                ? 'bg-cohab-tint text-cohab-primary'
                : 'text-cohab-subtle hover:text-cohab-ink hover:bg-cohab-tint/60',
            )}
          >
            <svg
              width="15"
              height="15"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              {opt.icon}
            </svg>
            {!iconOnly && opt.label}
          </button>
        )
      })}
    </div>
  )
}
