import * as React from 'react'
import { cn } from '@/lib/utils'

export function Select({ className, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <div className={cn('relative', className)}>
      <select
        className={cn(
          // appearance-none drops the native arrow, which the browser plants
          // hard against the far edge with no way to reposition it — the
          // custom chevron below sits at a normal, consistent inset instead.
          'w-full box-border appearance-none rounded-[14px] border-2 border-cohab-border-soft bg-cohab-card pl-4 pr-10 py-3.5 text-[15px] leading-[1.2] text-cohab-ink font-medium',
          'focus:outline-none focus:border-cohab-ink',
          'disabled:bg-cohab-bg disabled:text-cohab-muted',
        )}
        {...props}
      />
      <svg
        className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-cohab-subtle"
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M6 9l6 6 6-6" />
      </svg>
    </div>
  )
}
