import { cn } from '@/lib/utils'
import { Check } from 'lucide-react'
import { Progress } from '@/components/ui/progress'

export default function Stepper({ steps, currentStep, stepStatuses, onStepJump }) {
  const doneCount = stepStatuses.filter(s => s === 'done').length
  const progress = Math.round((doneCount / steps.length) * 100)

  return (
    <div className="px-5 py-3 border-b border-border bg-white flex-shrink-0">
      {/* Step pills */}
      <div className="flex items-center gap-1.5 flex-wrap mb-2.5">
        {steps.map((step, i) => {
          const isDone = stepStatuses[i] === 'done'
          const isCurrent = i === currentStep
          const isReachable = isDone || i <= currentStep
          return (
            <button
              key={step.id}
              onClick={() => isReachable && onStepJump(i)}
              disabled={!isReachable}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold transition-all duration-200 border',
                isDone && 'bg-brand-50 border-brand-200 text-brand-700 hover:bg-brand-100',
                isCurrent && !isDone && 'bg-brand-500 border-brand-500 text-white shadow-sm',
                !isDone && !isCurrent && isReachable && 'bg-white border-border text-muted-foreground hover:bg-muted/50',
                !isReachable && 'bg-white border-border text-muted-foreground/40 cursor-not-allowed opacity-60',
              )}
            >
              <span className={cn(
                'w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-bold flex-shrink-0',
                isDone && 'bg-brand-500 text-white',
                isCurrent && !isDone && 'bg-white text-brand-600',
                !isDone && !isCurrent && 'bg-muted text-muted-foreground',
              )}>
                {isDone ? <Check className="w-2.5 h-2.5" /> : i + 1}
              </span>
              {step.title}
              {step.heroLabel && (
                <span className="text-[9px] font-bold bg-violet-100 text-violet-600 px-1.5 py-0.5 rounded-full">
                  {step.heroLabel}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* Progress bar */}
      <div className="flex items-center gap-2">
        <Progress value={progress} className="flex-1 h-1.5" />
        <span className="text-[11px] font-semibold text-muted-foreground w-8 text-right">{progress}%</span>
      </div>
    </div>
  )
}
