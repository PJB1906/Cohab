import { cn } from '@/lib/utils'

export function Eyebrow({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <p
      className={cn(
        'font-medium text-[10px] leading-none uppercase tracking-[.08em] text-cohab-subtle',
        'font-mono',
        className,
      )}
    >
      {children}
    </p>
  )
}
