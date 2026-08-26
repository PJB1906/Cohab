import * as React from 'react'
import { cn } from '@/lib/utils'

export function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        // Modal inputs sit on the elevated surface, not the card surface, so a
        // field reads as inset against the panel it lives on.
        'w-full box-border rounded-lg border border-cohab-border bg-cohab-tint px-3.5 py-3.5 text-[15px] leading-[1.2] text-cohab-ink cohab-desktop:py-3 cohab-desktop:text-sm',
        'focus:outline-none focus:ring-1 focus:ring-cohab-primary focus:border-cohab-primary',
        'disabled:bg-cohab-bg disabled:text-cohab-subtle',
        className,
      )}
      {...props}
    />
  )
}
