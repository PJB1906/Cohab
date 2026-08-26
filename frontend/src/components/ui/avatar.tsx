import { cn } from '@/lib/utils'

/** True for the seed's generated initials avatars (`seed_avatars.py` writes
 * `/media/avatar-<uuid>.png`; genuine uploads are `/media/seed-*` or a
 * hashed upload name). Callers that render a photo into a non-square frame
 * use this to fall back to the circular treatment instead of stretching a
 * 256px square of type — see MatchCard (docs/DECISIONS.md D-13.11). */
export function isGeneratedAvatar(src: string | null | undefined): boolean {
  return !!src && src.includes('/avatar-')
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/)
  const first = parts[0]?.[0] ?? ''
  const last = parts.length > 1 ? parts[parts.length - 1][0] : ''
  return (first + last).toUpperCase()
}

export function Avatar({
  name,
  src,
  size = 40,
  className,
}: {
  name: string
  src?: string | null
  size?: number
  className?: string
}) {
  // A generated avatar is initials on a flat ground — exactly what the
  // fallback below draws, except the PNG has a *dark* ground baked in by
  // `seed_avatars.py` and so stays dark-on-dark under the light theme
  // (D-13.15). Rendering the fallback instead of the file keeps the same
  // picture while letting it follow the theme tokens. Genuine uploads are
  // photographs and are always shown as-is.
  if (src && !isGeneratedAvatar(src)) {
    return (
      <img
        src={src}
        alt={name}
        width={size}
        height={size}
        className={cn('rounded-full object-cover flex-none', className)}
        style={{ width: size, height: size }}
      />
    )
  }
  return (
    <div
      className={cn(
        'rounded-full flex-none flex items-center justify-center bg-cohab-avatar-bg text-cohab-avatar-ink font-semibold select-none',
        className,
      )}
      style={{ width: size, height: size, fontSize: size * 0.4 }}
    >
      {initials(name) || '?'}
    </div>
  )
}
