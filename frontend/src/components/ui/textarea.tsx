import * as React from 'react'
import { cn } from '@/lib/utils'

export function Textarea({ className, ...props }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        'w-full box-border resize-y rounded-xl border border-cohab-border bg-white px-3.5 py-3 text-sm text-cohab-ink',
        'focus:outline-none focus:ring-2 focus:ring-cohab-primary focus:border-cohab-primary',
        className,
      )}
      {...props}
    />
  )
}
