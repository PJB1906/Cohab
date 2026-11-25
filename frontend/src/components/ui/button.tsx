import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { ArrowRight, LoaderCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

/** Buttons (D-14.27). The filled variants are "art buttons" (`.btn-ink`,
 * index.css): an ink pill (white in dark mode) with a line drawing of
 * rooftops inside that drifts on hover, while a fill grows out of the arrow
 * badge and flips the label colour. They also lean toward the pointer
 * (lib/magnetic.ts). Roles:
 *
 * - primary: the one main action on a screen (ink, sun fill)
 * - sun: match moments only (confirm move-in)
 * - light: actions on photographs or ink panels
 * - destructive: coral, irreversible actions after a confirm
 * - secondary: quiet white with a hairline, a second action
 * - ghost / danger: text-weight actions
 *
 * `arrow` adds the badge with an arrow (forward motion); `loading` swaps in a
 * spinner and disables the button. */
export const buttonVariants = cva(
  'group/btn cohab-press relative inline-flex items-center justify-center gap-2 rounded-full font-bold [font-stretch:106%] tracking-[-0.005em] whitespace-nowrap select-none cursor-pointer disabled:opacity-40 disabled:pointer-events-none',
  {
    variants: {
      variant: {
        primary: 'btn-ink',
        sun: 'btn-ink btn-ink--sun',
        light: 'btn-ink btn-ink--light',
        destructive: 'btn-ink btn-ink--coral',
        secondary:
          'btn-quiet bg-cohab-card text-cohab-ink border border-cohab-border transition-[border-color,background-color,color] duration-200 hover:border-cohab-ink/40 hover:bg-cohab-row-tint',
        ghost: 'text-cohab-ink transition-colors hover:bg-cohab-tint',
        danger: 'text-cohab-accent transition-colors hover:bg-cohab-accent-tint',
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

/** The arrow badge for art buttons; usable inside links styled with
 * `buttonVariants` too. */
export function ButtonArrow() {
  return (
    <span className="btn-badge" aria-hidden>
      <ArrowRight className="size-4" strokeWidth={2.4} />
    </span>
  )
}

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
      {arrow && !loading && <ButtonArrow />}
    </button>
  )
}
