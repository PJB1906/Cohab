import * as React from 'react'
import { cn } from '@/lib/utils'

export function Textarea({ className, ...props }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        'w-full box-border resize-y rounded-[14px] border-2 border-cohab-border-soft bg-cohab-card px-4 py-3 text-[15px] text-cohab-ink focus:outline-none focus:border-cohab-ink',
        'focus:outline-none focus:ring-2 focus:ring-cohab-primary focus:border-cohab-primary',
        className,
      )}
      {...props}
    />
  )
}
