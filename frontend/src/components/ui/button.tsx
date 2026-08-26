import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

/** Modal's three button treatments (docs/DECISIONS.md D-13.2).
 *
 * `primary` is Modal's Accent Pill: the vivid lime as a *fill*, with dark text
 * on top. Modal rations this to one per viewport, which is why `secondary` —
 * not `primary` — is the right choice for any screen that needs two equally
 * weighted actions.
 *
 * The old `text-white` on every filled variant is gone: white on Lime Pulse
 * fails contrast badly, and Modal's own spec puts #181818 there instead. */
const buttonVariants = cva(
  'cohab-press inline-flex items-center justify-center gap-2 rounded-full cohab-desktop:rounded-xl font-medium transition-colors disabled:opacity-40 disabled:pointer-events-none cursor-pointer',
  {
    variants: {
      variant: {
        primary: 'bg-cohab-primary text-cohab-on-fill hover:bg-cohab-primary-dark',
        secondary:
          'bg-cohab-card text-cohab-ink border border-cohab-border hover:border-cohab-primary hover:text-cohab-primary',
        ghost: 'bg-transparent text-cohab-primary hover:underline',
        danger: 'bg-transparent text-cohab-accent hover:underline',
        destructive: 'bg-cohab-accent text-cohab-on-fill hover:brightness-110',
      },
      size: {
        default: 'h-[52px] px-6 text-[15px] cohab-desktop:h-11 cohab-desktop:px-5 cohab-desktop:text-[14px]',
        sm: 'h-9 px-4 text-sm',
      },
    },
    defaultVariants: { variant: 'primary', size: 'default' },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export function Button({ className, variant, size, ...props }: ButtonProps) {
  return <button className={cn(buttonVariants({ variant, size }), className)} {...props} />
}
