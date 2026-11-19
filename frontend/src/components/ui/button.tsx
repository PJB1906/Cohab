import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

/** Poster buttons (D-14.23). `primary` is the black pill (white in dark
 * mode): the one loud action on a screen. `secondary` is outlined in ink, for
 * a second action of similar weight. Bold, slightly widened type so a button
 * reads as a button at a glance, not as a link. */
const buttonVariants = cva(
  'cohab-press inline-flex items-center justify-center gap-2 rounded-full font-bold [font-stretch:108%] tracking-[-0.005em] transition-colors disabled:opacity-35 disabled:pointer-events-none cursor-pointer',
  {
    variants: {
      variant: {
        primary:
          'bg-cohab-primary text-cohab-on-fill hover:bg-cohab-primary-dark shadow-[0_10px_22px_-10px_rgb(42_75_255/0.75)] hover:shadow-[0_14px_26px_-10px_rgb(42_75_255/0.85)]',
        secondary:
          'bg-cohab-card text-cohab-ink border border-cohab-border shadow-[0_1px_2px_rgb(11_16_51/0.05)] hover:border-cohab-primary hover:text-cohab-primary',
        ghost: 'bg-transparent text-cohab-ink underline-offset-4 hover:underline',
        danger: 'bg-transparent text-cohab-accent hover:underline',
        destructive: 'bg-cohab-accent text-cohab-on-fill hover:brightness-110',
      },
      size: {
        default: 'h-[52px] px-7 text-[15px] cohab-desktop:h-12 cohab-desktop:px-6 cohab-desktop:text-[14.5px]',
        sm: 'h-9 px-4 text-[13px]',
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
