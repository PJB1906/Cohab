import * as React from 'react'
import { cn } from '@/lib/utils'

const VARIANTS = {
  agreement: 'border border-cohab-border bg-cohab-tint text-cohab-primary',
  divergence: 'border border-cohab-accent bg-white text-cohab-accent',
  verified: 'border border-cohab-border bg-cohab-tint text-cohab-primary',
  neutral: 'border border-cohab-border bg-white text-cohab-ink',
}

export function Badge({
  className,
  variant = 'neutral',
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { variant?: keyof typeof VARIANTS }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded px-2 py-1 text-xs font-medium leading-none',
        VARIANTS[variant],
        className,
      )}
      {...props}
    />
  )
}
