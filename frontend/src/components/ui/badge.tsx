import * as React from 'react'
import { cn } from '@/lib/utils'

const VARIANTS = {
  agreement: 'bg-cohab-tint text-cohab-ink',
  divergence: 'border border-cohab-accent text-cohab-accent bg-transparent',
  verified: 'bg-cohab-ink text-cohab-card',
  neutral: 'border border-cohab-border bg-cohab-card text-cohab-ink',
}

export function Badge({
  className,
  variant = 'neutral',
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { variant?: keyof typeof VARIANTS }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-1 text-[12px] font-semibold leading-none',
        VARIANTS[variant],
        className,
      )}
      {...props}
    />
  )
}
