import * as React from 'react'
import { cn } from '@/lib/utils'

export function Select({ className, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        'w-full box-border rounded-xl border border-cohab-border bg-cohab-card px-3.5 py-3.5 text-[15px] leading-[1.2] text-cohab-ink cohab-desktop:py-3 cohab-desktop:text-sm',
        'focus:outline-none focus:ring-2 focus:ring-cohab-primary focus:border-cohab-primary',
        'disabled:bg-cohab-bg disabled:text-cohab-muted',
        className,
      )}
      {...props}
    />
  )
}
