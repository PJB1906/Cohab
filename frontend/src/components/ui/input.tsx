import * as React from 'react'
import { cn } from '@/lib/utils'

export function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        // Modal inputs sit on the elevated surface, not the card surface, so a
        // field reads as inset against the panel it lives on.
        'w-full box-border rounded-[14px] border-2 border-cohab-border-soft bg-cohab-card px-4 py-3.5 text-[15px] leading-[1.2] text-cohab-ink font-medium',
        'hover:border-cohab-border focus:outline-none focus:border-cohab-ink',
        'disabled:bg-cohab-bg disabled:text-cohab-subtle',
        className,
      )}
      {...props}
    />
  )
}
