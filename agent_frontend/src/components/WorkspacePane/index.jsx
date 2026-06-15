import { forwardRef, useImperativeHandle, useRef, useCallback } from 'react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import Stepper from './Stepper'
import WorkFoot from './WorkFoot'
import BriefStep from '@/steps/BriefStep'
import CreativeStep from '@/steps/CreativeStep'
import AudienceStep from '@/steps/AudienceStep'
import SetupStep from '@/steps/SetupStep'
import SuccessStep from '@/steps/SuccessStep'
import ReportStep from '@/steps/ReportStep'
import EmailStep from '@/steps/EmailStep'
import { LayoutDashboard } from 'lucide-react'

const STEP_DESCS = [
  'Điền brief khách hàng — agent chuẩn hóa về JSON schema và đề xuất KPI.',
  'Upload nhiều creative (ảnh / video) để lưu vào storage. Dùng ở bước Setup Camp.',
  'Chọn attributes từ DMP. Size = min(tệp) × discount overlap 22%/tệp.',
  '3 campaign draft theo zone tối ưu CPM. Tạo + pause/run từng campaign.',
  'Tổng kết campaigns vừa tạo. Xem chi tiết trước khi sang phân tích.',
  'Extract report · vẽ chart performance · LLM đánh giá · đề xuất hành động.',
  'Soạn email tổng kết · gửi cho Account team và Ad Opt team.',
]

const WorkspacePane = forwardRef(function WorkspacePane(
  { steps, currentStep, stepStatuses, formState, setFormState, onStepJump, onApprove, canApprove, busy, onPartialReset },
  ref
) {
  const bodyRef = useRef(null)

  useImperativeHandle(ref, () => ({
    flash() {
      const el = bodyRef.current
      if (!el) return
      el.classList.remove('animate-flash-border')
      void el.offsetWidth
      el.classList.add('animate-flash-border')
      setTimeout(() => el.classList.remove('animate-flash-border'), 1000)
    }
  }))

  const step = steps[currentStep]
  const isDone = stepStatuses[currentStep] === 'done'

  const updateFormSlice = useCallback((slice, val) => {
    setFormState(prev => ({ ...prev, [slice]: val }))
  }, [setFormState])

  // For CreativeStep: onChange may be a value OR a functional updater
  const updateCreative = useCallback((updater) => {
    if (typeof updater === 'function') {
      setFormState(prev => ({ ...prev, creative: updater(prev.creative) }))
    } else {
      setFormState(prev => ({ ...prev, creative: updater }))
    }
  }, [setFormState])

  const renderStep = () => {
    switch (currentStep) {
      case 0: return <BriefStep data={formState.brief} onChange={v => updateFormSlice('brief', v)} isDone={isDone} />
      case 1: return <CreativeStep data={formState.creative} onChange={updateCreative} isDone={isDone} />
      case 2: return <AudienceStep data={formState.segment} onChange={v => updateFormSlice('segment', v)} isDone={isDone} brief={formState.brief} />
      case 3: return (
        <SetupStep
          data={formState.setup}
          onChange={v => updateFormSlice('setup', v)}
          brief={formState.brief}
          creative={formState.creative}
          segment={formState.segment}
          isDone={isDone}
          onReRecommend={() => {}}
        />
      )
      case 4: return (
        <SuccessStep
          brief={formState.brief}
          zones={formState.setup.recoZones || []}
          selectedZoneIds={formState.setup.selectedZoneIds || []}
          audienceSize={formState.segment.size}
          allZones={formState.setup.allZones || []}
          setup={{
            ...formState.setup,
            creativeFiles: formState.creative.files || [],
          }}
        />
      )
      case 5: return <ReportStep data={formState.report} onChange={v => updateFormSlice('report', v)} isDone={isDone} />
      case 6: return (
        <EmailStep
          brief={formState.brief}
          zones={formState.setup.recoZones || []}
          selectedZoneIds={formState.setup.selectedZoneIds || []}
          audiences={formState.segment}
          data={formState.email}
          onChange={v => updateFormSlice('email', v)}
          isDone={isDone}
        />
      )
      default: return null
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Pane header */}
      <div className="flex items-center gap-2 px-5 py-3 border-b border-border bg-white/80 flex-shrink-0">
        <LayoutDashboard className="w-4 h-4 text-violet-500" />
        <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Workspace</span>
        <span className="ml-1 text-xs text-muted-foreground">· Form & kết quả · bước hiện tại</span>
      </div>

      {/* Stepper */}
      <Stepper
        steps={steps}
        currentStep={currentStep}
        stepStatuses={stepStatuses}
        onStepJump={onStepJump}
      />

      {/* Step body */}
      <ScrollArea className="flex-1" ref={bodyRef}>
        <div className="p-5">
          {/* Step heading */}
          <div className={cn('flex items-center gap-3 mb-1', isDone && 'opacity-90')}>
            <div className={cn(
              'w-8 h-8 rounded-full flex items-center justify-center text-sm font-black border-2 flex-shrink-0',
              isDone ? 'bg-brand-500 border-brand-500 text-white' : 'bg-brand-50 border-brand-300 text-brand-700'
            )}>
              {isDone ? '✓' : currentStep + 1}
            </div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-black text-foreground tracking-tight">{step.title}</h2>
              {step.heroLabel && (
                <Badge variant="violet" className="text-[10px]">{step.heroLabel}</Badge>
              )}
              {isDone && <Badge variant="green" className="text-[10px]">Hoàn thành</Badge>}
            </div>
          </div>
          <p className="text-xs text-muted-foreground mb-4 ml-11">{STEP_DESCS[currentStep]}</p>

          {/* Step content */}
          {renderStep()}

          {/* Re-edit banner for completed input steps (brief, creative, audience) */}
          {isDone && currentStep <= 2 && onPartialReset && (
            <div className="mt-4 flex items-center gap-3 p-3 rounded-xl border border-amber-200 bg-amber-50">
              <div className="flex-1">
                <p className="text-xs font-semibold text-amber-800">Muốn chỉnh sửa lại bước này?</p>
                <p className="text-[10px] text-amber-700 mt-0.5">
                  Các bước sau ({steps.slice(currentStep + 1).map(s => s.title).join(', ')}) sẽ được reset.
                </p>
              </div>
              <button
                onClick={() => onPartialReset(currentStep)}
                className="flex-shrink-0 px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-white text-xs font-bold transition-colors"
              >
                Chỉnh sửa lại
              </button>
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Footer */}
      <WorkFoot
        step={step}
        stepIndex={currentStep}
        stepStatus={stepStatuses[currentStep]}
        totalSteps={steps.length}
        canApprove={canApprove}
        busy={busy}
        onApprove={onApprove}
        onBack={() => onStepJump(currentStep - 1)}
        onNext={() => onStepJump(currentStep + 1)}
      />
    </div>
  )
})

export default WorkspacePane
