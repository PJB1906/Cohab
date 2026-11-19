import * as React from 'react'
import { cn } from '@/lib/utils'

export function Textarea({ className, ...props }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        'w-full box-border resize-y rounded-[14px] border-[1.5px] border-cohab-border bg-cohab-card px-4 py-3 text-[15px] text-cohab-ink focus:outline-none focus:border-cohab-primary focus:ring-4 focus:ring-cohab-primary/15',
        'focus:outline-none focus:ring-2 focus:ring-cohab-primary focus:border-cohab-primary',
        className,
      )}
      {...props}
    />
  )
}
