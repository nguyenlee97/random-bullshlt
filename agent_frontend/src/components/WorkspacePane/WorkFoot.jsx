import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { ChevronRight, ChevronLeft, Check, Loader2, Wrench } from 'lucide-react'

export default function WorkFoot({ step, stepIndex, stepStatus, totalSteps, canApprove, busy, onApprove, onBack, onNext, approveLabel = '' }) {
  const isDone = stepStatus === 'done'
  const isLast = stepIndex === totalSteps - 1
  // No model toggle needed — single backend model

  return (
    <div className="min-w-0 border-t border-border bg-white px-3 py-3 flex-shrink-0 flex items-center gap-2 sm:px-5 sm:gap-3">
      {/* Current workflow tool */}
      <div className="hidden items-center gap-1.5 flex-1 min-w-0 sm:flex">
        <Badge variant="muted" className="gap-1 text-[10px] h-5">
          <Wrench className="w-2.5 h-2.5" />
          <span className="truncate max-w-[140px]">{step.tool}</span>
        </Badge>
      </div>

      {/* Navigation buttons */}
      <div className="flex min-w-0 flex-1 items-center justify-end gap-2 sm:flex-none">
        {stepIndex > 0 && (
          <Button
            variant="outline"
            size="sm"
            onClick={onBack}
            disabled={busy}
            className="h-9 gap-1.5"
          >
            <ChevronLeft className="w-3.5 h-3.5" />
            Quay lại
          </Button>
        )}

        {isDone ? (
          isLast ? (
            <Button size="sm" variant="brand-outline" className="h-9 gap-1.5">
              <Check className="w-3.5 h-3.5" />
              Đã hoàn tất
            </Button>
          ) : (
            <Button size="sm" onClick={onNext} disabled={busy} className="h-9 gap-1.5">
              Bước tiếp theo
              <ChevronRight className="w-3.5 h-3.5" />
            </Button>
          )
        ) : (
          <Button
            size="sm"
            onClick={onApprove}
            disabled={!canApprove || busy}
            className={cn('h-9 gap-1.5', canApprove && !busy && 'shadow-glow-green')}
            data-demo="approve-btn"
          >
            {busy ? (
              <><Loader2 className="w-3.5 h-3.5 animate-spin" />Đang xử lý...</>
            ) : (
              <><Check className="w-3.5 h-3.5" />{approveLabel || (isLast ? 'Đồng ý & Hoàn tất' : 'Đồng ý & Tiếp tục')}</>
            )}
          </Button>
        )}
      </div>
    </div>
  )
}
