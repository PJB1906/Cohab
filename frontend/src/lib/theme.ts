/** Theme selection (docs/DECISIONS.md D-13.12).
 *
 * Three states, not two. "System" is the default and is genuinely distinct
 * from an explicit choice: it follows the OS and keeps following it when the
 * OS flips, whereas an explicit choice must win over the OS in *both*
 * directions. That is why the resolved theme is written to
 * `document.documentElement[data-theme]` rather than toggling a single class
 * — the light overrides in index.css key off `[data-theme='light']`, and the
 * dark values are the `@theme` defaults, so "no stamp" is not a valid
 * resting state once a user has chosen.
 *
 * Applied before React mounts (see index.html) so there is no flash of the
 * wrong theme on load.
 */

export type ThemeChoice = 'light' | 'dark' | 'system'

const STORAGE_KEY = 'cohab-theme'

export function getStoredChoice(): ThemeChoice {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw === 'light' || raw === 'dark' || raw === 'system') return raw
  } catch {
    // Private mode / blocked storage — fall through to the system default.
  }
  return 'system'
}

export function systemPrefersDark(): boolean {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? true
}

/** The theme actually painted, with `system` resolved against the OS. */
export function resolveTheme(choice: ThemeChoice): 'light' | 'dark' {
  if (choice === 'system') return systemPrefersDark() ? 'dark' : 'light'
  return choice
}

/** Point the tab icon at the palette actually being painted.
 *
 * A single SVG favicon carrying its own `prefers-color-scheme` block looks
 * like the tidier solution, and was the first attempt — but a favicon's
 * internal CSS can only see the *OS* setting. It cannot see
 * `document.documentElement[data-theme]`, so choosing Light in-app while the
 * OS was dark left a dark icon above a light UI. Two files swapped from here
 * is the only way the icon can follow the app's own choice
 * (docs/DECISIONS.md D-13.17).
 *
 * The `?v=` cache-bust matters: browsers cache favicons hard enough that a
 * changed `href` alone is often ignored within a session.
 */
function applyFavicon(theme: 'light' | 'dark'): void {
  const link = document.querySelector<HTMLLinkElement>('link[rel="icon"]')
  if (!link) return
  const next = `/favicon-${theme}.svg`
  // Compare against the path only — `link.href` is absolute and carries the
  // query string, so a raw equality check would never match and would
  // rewrite (and re-fetch) the icon on every single theme application.
  if (new URL(link.href, location.origin).pathname === next) return
  link.href = `${next}?v=${theme}`
}

export function applyTheme(choice: ThemeChoice): void {
  const theme = resolveTheme(choice)
  document.documentElement.dataset.theme = theme
  applyFavicon(theme)
}

export function setTheme(choice: ThemeChoice): void {
  try {
    localStorage.setItem(STORAGE_KEY, choice)
  } catch {
    // Not fatal — the choice simply will not survive a reload.
  }
  applyTheme(choice)
}

/** Re-resolve when the OS flips, but only while the user is on `system`. */
export function watchSystemTheme(): () => void {
  const media = window.matchMedia?.('(prefers-color-scheme: dark)')
  if (!media) return () => {}
  const onChange = () => {
    if (getStoredChoice() === 'system') applyTheme('system')
  }
  media.addEventListener('change', onChange)
  return () => media.removeEventListener('change', onChange)
}
