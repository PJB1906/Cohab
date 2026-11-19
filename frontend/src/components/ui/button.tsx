import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { ArrowRight, LoaderCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

/** Buttons (D-14.25). Tactile rather than flat: raised variants carry a top
 * highlight, a hairline shade at the bottom and a glow in their own colour,
 * lift a pixel on hover and press in on click (`.btn-raised`, index.css).
 *
 * - primary: cobalt, the one main action on a screen
 * - sun: match moments only (confirm move-in, say yes)
 * - light: white, for actions on photo or navy bands
 * - secondary: quiet white with a hairline, a second action of similar weight
 * - ghost / danger: text-weight actions
 * - destructive: coral, irreversible actions after a confirm
 *
 * `arrow` adds a trailing arrow that slides on hover (forward motion);
 * `loading` swaps in a spinner and disables the button. */
export const buttonVariants = cva(
  'group/btn cohab-press relative inline-flex items-center justify-center gap-2 rounded-full font-bold [font-stretch:106%] tracking-[-0.005em] whitespace-nowrap select-none cursor-pointer transition-[transform,box-shadow,background-color,border-color,color,filter] duration-200 ease-[cubic-bezier(.22,1,.36,1)] disabled:opacity-40 disabled:pointer-events-none',
  {
    variants: {
      variant: {
        primary: 'btn-raised bg-cohab-primary text-cohab-on-fill',
        sun: 'btn-raised btn-sun bg-cohab-sun text-cohab-on-sun',
        light: 'btn-raised btn-light bg-white text-[#0b1033]',
        secondary: 'btn-quiet bg-cohab-card text-cohab-ink border border-cohab-border hover:border-cohab-primary/55 hover:text-cohab-primary',
        ghost: 'text-cohab-ink hover:bg-cohab-tint',
        danger: 'text-cohab-accent hover:bg-cohab-accent-tint',
        destructive: 'btn-raised btn-coral bg-cohab-accent text-cohab-on-fill',
      },
      size: {
        lg: 'h-14 px-8 text-[16px]',
        default: 'h-[52px] px-7 text-[15px] cohab-desktop:h-12 cohab-desktop:px-6 cohab-desktop:text-[14.5px]',
        sm: 'h-9 px-4 text-[13px]',
        icon: 'h-10 w-10 p-0',
      },
    },
    defaultVariants: { variant: 'primary', size: 'default' },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  arrow?: boolean
  loading?: boolean
  icon?: React.ReactNode
}

export function Button({ className, variant, size, arrow, loading, icon, children, disabled, ...props }: ButtonProps) {
  return (
    <button
      className={cn(buttonVariants({ variant, size }), className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading ? <LoaderCircle className="size-4 animate-spin" aria-hidden /> : icon}
      {children}
      {arrow && !loading && (
        <ArrowRight className="size-4 -mr-1 transition-transform duration-200 group-hover/btn:translate-x-1" aria-hidden />
      )}
    </button>
  )
}
