import { cn } from '@/lib/utils'

export function MobileStepHeader({
  step,
  totalSteps,
  minutesLeft,
  onBack,
  progressPercent,
  className,
}: {
  step: number
  totalSteps: number
  minutesLeft?: number
  onBack: () => void
  progressPercent: number
  className?: string
}) {
  return (
    <div className={cn('cohab-desktop:hidden flex-none', className)}>
      <div className="flex items-center justify-between px-4">
        <button
          type="button"
          onClick={onBack}
          className="cohab-press w-11 h-11 flex items-center justify-center text-cohab-ink text-[22px] cursor-pointer"
        >
          ←
        </button>
        <span className="text-[13px] font-medium text-cohab-subtle-mobile">
          Step {step} of {totalSteps}
        </span>
        {minutesLeft !== undefined ? (
          <span className="text-[12px] font-medium text-cohab-subtle-mobile">About {minutesLeft} minutes left</span>
        ) : (
          <span className="w-11" />
        )}
      </div>
      <div className="px-6 pb-3">
        <div className="h-[3px] bg-cohab-track rounded-full overflow-hidden">
          <div className="h-full bg-cohab-primary" style={{ width: `${Math.max(0, Math.min(100, progressPercent))}%` }} />
        </div>
      </div>
    </div>
  )
}
