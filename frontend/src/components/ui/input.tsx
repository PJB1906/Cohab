import * as React from 'react'
import { cn } from '@/lib/utils'

export function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        'w-full box-border rounded-xl border border-cohab-border bg-white px-3.5 py-3 text-sm text-cohab-ink',
        'focus:outline-none focus:ring-2 focus:ring-cohab-primary focus:border-cohab-primary',
        'disabled:bg-cohab-bg disabled:text-cohab-muted',
        className,
      )}
      {...props}
    />
  )
}
