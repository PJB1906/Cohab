import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 rounded-full font-semibold transition-colors disabled:opacity-50 disabled:pointer-events-none cursor-pointer',
  {
    variants: {
      variant: {
        primary: 'bg-cohab-primary text-white hover:bg-cohab-primary-dark',
        secondary: 'bg-white text-cohab-ink border border-cohab-border hover:border-cohab-primary',
        ghost: 'bg-transparent text-cohab-primary hover:underline',
        danger: 'bg-transparent text-cohab-accent hover:underline',
      },
      size: {
        default: 'h-12 px-6 text-[15px]',
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
