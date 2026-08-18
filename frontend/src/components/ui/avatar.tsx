import { cn } from '@/lib/utils'

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
  if (src) {
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
        'rounded-full flex-none flex items-center justify-center bg-cohab-tint border border-cohab-border text-cohab-primary font-semibold',
        className,
      )}
      style={{ width: size, height: size, fontSize: size * 0.4 }}
    >
      {initials(name) || '?'}
    </div>
  )
}
