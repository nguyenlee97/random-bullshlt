import { forwardRef, lazy, Suspense, useImperativeHandle, useRef, useCallback, useState } from 'react'
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
import { AlertTriangle, LayoutDashboard } from 'lucide-react'

const ReportStep = lazy(() => import('@/steps/ReportStep'))
const EmailStep = lazy(() => import('@/steps/EmailStep'))

function StepLoading() {
  return (
    <div className="min-h-40 grid place-items-center text-sm text-muted-foreground" role="status">
      Đang tải công cụ bước này…
    </div>
  )
}

const STEP_DESCS = [
  'Điền brief khách hàng — agent chuẩn hóa về JSON schema và đề xuất KPI.',
  'Chọn attributes từ DMP. Size = min(tệp) × discount overlap 22%/tệp.',
  'Upload nhiều creative (ảnh / video) để lưu vào storage. Dùng ở bước Setup Camp.',
  'Chọn ad zones phù hợp, gắn creative vào từng zone và xác nhận tạo chiến dịch.',
  'Tổng kết campaigns vừa tạo. Xem chi tiết trước khi sang phân tích.',
  'Extract report · vẽ chart performance · LLM đánh giá · đề xuất hành động.',
  'Soạn email tổng kết · gửi cho Account team và Ad Opt team.',
]

const WorkspacePane = forwardRef(function WorkspacePane(
  { steps, currentStep, stepStatuses, formState, setFormState, onStepJump, onApprove, canApprove, busy, onPartialReset, recoFromChat, onSendChat, recomputePlan, workspaceRevision, creativeFormatPlan, onOpenRecompute, autopilotMode = false, onAutopilotSave, onReturnToAutopilot },
  ref
) {
  const bodyRef = useRef(null)
  const [autopilotSaveMessage, setAutopilotSaveMessage] = useState('')

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
  const isStale = stepStatuses[currentStep] === 'stale'
  const isReadOnly = isDone && !autopilotMode

  const updateFormSlice = useCallback((slice, val) => {
    setFormState(prev => ({
      ...prev,
      [slice]: typeof val === 'function' ? val(prev[slice]) : val,
    }))
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
      case 0: return <BriefStep data={formState.brief} onChange={v => updateFormSlice('brief', v)} isDone={isReadOnly} />
      case 1: return <AudienceStep data={formState.segment} onChange={v => updateFormSlice('segment', v)} isDone={isReadOnly} brief={formState.brief} recoFromChat={recoFromChat} />
      case 2: return <CreativeStep data={formState.creative} onChange={updateCreative} isDone={isReadOnly} brief={formState.brief} segment={formState.segment} formatPlan={creativeFormatPlan} autopilotMode={autopilotMode} />
      case 3: return (
        <SetupStep
          data={formState.setup}
          onChange={v => updateFormSlice('setup', v)}
          brief={formState.brief}
          creative={formState.creative}
          segment={formState.segment}
          isDone={isReadOnly}
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
          recoZones={formState.setup.recoZones || []}
          setup={{
            ...formState.setup,
            creativeFiles: formState.creative.files || [],
          }}
        />
      )
      case 5: return (
        <Suspense fallback={<StepLoading />}>
          <ReportStep data={formState.report} onChange={v => updateFormSlice('report', v)} isDone={isDone} formState={formState} onSendChat={onSendChat} />
        </Suspense>
      )
      case 6: return (
        <Suspense fallback={<StepLoading />}>
          <EmailStep
            brief={formState.brief}
            zones={formState.setup?.recoZones || []}
            selectedZoneIds={formState.setup?.selectedZoneIds || []}
            audiences={formState.segment}
            data={formState.email || {}}
            onChange={v => updateFormSlice('email', v)}
            isDone={isDone}
            formState={formState}
          />
        </Suspense>
      )
      default: return null
    }
  }

  const saveAutopilotEditor = async () => {
    setAutopilotSaveMessage('')
    const result = await onAutopilotSave?.()
    if (!result?.shouldAdvance) {
      setAutopilotSaveMessage(
        String(result?.response?.content || 'Chưa thể lưu thay đổi. Kiểm tra thông tin trong form rồi thử lại.')
          .replaceAll('**', '')
      )
    }
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Pane header */}
      <div className="flex items-center gap-2 px-3 sm:px-5 py-3 border-b border-border bg-white/80 flex-shrink-0">
        <LayoutDashboard className="w-4 h-4 text-violet-500" />
        <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider">{autopilotMode ? 'Campaign artifacts' : 'Workspace'}</span>
        <span className="ml-1 text-xs text-muted-foreground">{autopilotMode ? '· Dữ liệu để Agent thực thi' : '· Form & kết quả · bước hiện tại'}</span>
        {workspaceRevision != null && (
          <span className="ml-auto text-[10px] font-mono text-muted-foreground">rev {workspaceRevision}</span>
        )}
      </div>

      {/* Stepper */}
      {autopilotMode ? (
        <nav aria-label="Điều hướng campaign artifacts" className="flex gap-2 overflow-x-auto border-b border-border bg-slate-50/80 px-3 py-2 sm:px-5">
          {steps.slice(0, 4).map((item, index) => {
            const status = stepStatuses[index]
            const active = index === currentStep
            return (
              <button key={item.id || item.title} type="button" disabled={busy} onClick={() => onStepJump(index)}
                className={cn('inline-flex shrink-0 items-center gap-2 rounded-lg border px-3 py-1.5 text-xs font-bold transition-colors',
                  active ? 'border-brand-300 bg-brand-50 text-brand-700' : 'border-slate-200 bg-white text-slate-600 hover:border-brand-200',
                  busy && 'cursor-wait opacity-60')}>
                <span className={cn('h-2 w-2 rounded-full', status === 'done' ? 'bg-green-500' : status === 'stale' ? 'bg-amber-500' : 'bg-slate-300')} />
                {item.title}
              </button>
            )
          })}
        </nav>
      ) : (
        <Stepper
          steps={steps}
          currentStep={currentStep}
          stepStatuses={stepStatuses}
          onStepJump={onStepJump}
        />
      )}

      {recomputePlan?.has_changes && (
        <div className="mx-3 sm:mx-5 mt-3 rounded-xl border border-amber-300 bg-amber-50 px-3 py-2.5 flex items-start gap-2.5">
          <AlertTriangle className="w-4 h-4 text-amber-600 mt-0.5 flex-shrink-0" />
          <div className="min-w-0 flex-1">
            <p className="text-xs font-bold text-amber-900">
              Kế hoạch cần cập nhật {recomputePlan.recompute?.length || 0} phần
            </p>
            <p className="text-[10px] leading-relaxed text-amber-800 mt-0.5">
              Tái sử dụng {recomputePlan.reuse_count || 0} phần không bị ảnh hưởng · Thứ tự: {(recomputePlan.recompute_order || []).join(' → ')}
            </p>
          </div>
          <button
            type="button"
            onClick={onOpenRecompute}
            className="text-[10px] font-bold text-amber-900 border border-amber-300 bg-white hover:bg-amber-100 rounded-lg px-2.5 py-1.5 flex-shrink-0"
          >
            Xử lý
          </button>
        </div>
      )}

      {/* Step body */}
      <ScrollArea className="flex-1" ref={bodyRef}>
        <div data-demo="step-body" className="p-3 sm:p-5">
          {/* Step heading */}
          <div className={cn('flex items-center gap-3 mb-1', isDone && 'opacity-90')}>
            {!autopilotMode && <div className={cn(
              'w-8 h-8 rounded-full flex items-center justify-center text-sm font-black border-2 flex-shrink-0',
              isDone ? 'bg-brand-500 border-brand-500 text-white' : 'bg-brand-50 border-brand-300 text-brand-700'
            )}>
              {isDone ? '✓' : currentStep + 1}
            </div>}
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-black text-foreground tracking-tight">{step.title}</h2>
              {step.heroLabel && (
                <Badge variant="violet" className="text-[10px]">{step.heroLabel}</Badge>
              )}
              {isDone && !autopilotMode && <Badge variant="green" className="text-[10px]">Hoàn thành</Badge>}
              {isStale && <Badge variant="amber" className="text-[10px]">Cần xem lại</Badge>}
            </div>
          </div>
          <p className="text-xs text-muted-foreground mb-4 ml-11">{STEP_DESCS[currentStep]}</p>

          {/* Step content */}
          {renderStep()}

          {/* Re-edit banner for completed input steps (brief, creative, audience) */}
          {!autopilotMode && (isDone || isStale) && currentStep <= 3 && onPartialReset && (
            <div className="mt-4 flex items-center gap-3 p-3 rounded-xl border border-amber-200 bg-amber-50">
              <div className="flex-1">
                <p className="text-xs font-semibold text-amber-800">
                  {isStale ? 'Phần này cần được kiểm tra lại' : 'Muốn chỉnh sửa lại bước này?'}
                </p>
                <p className="text-[10px] text-amber-700 mt-0.5">
                  Dữ liệu hiện tại được giữ lại. Khi xác nhận thay đổi, chỉ phần phụ thuộc mới được đánh dấu cần cập nhật.
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
      {!autopilotMode && <WorkFoot
        step={step}
        stepIndex={currentStep}
        stepStatus={stepStatuses[currentStep]}
        totalSteps={steps.length}
        canApprove={canApprove}
        busy={busy}
        onApprove={onApprove}
        onBack={() => onStepJump(currentStep - 1)}
        onNext={() => onStepJump(currentStep + 1)}
      />}
      {autopilotMode && (
        <div className="flex-shrink-0 border-t border-brand-100 bg-white px-3 py-3 shadow-[0_-8px_24px_rgba(15,23,42,0.05)] sm:px-5">
          {autopilotSaveMessage && (
            <div role="alert" className="mb-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-800">
              {autopilotSaveMessage}
            </div>
          )}
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <p className="min-w-0 flex-1 text-[11px] leading-relaxed text-slate-600">
              {currentStep === 2
                ? 'Bạn có thể tải thêm creative. Khi đã đủ, Agent sẽ phân tích, lưu vào workspace và đưa bạn trở lại đúng điểm review của Autopilot.'
                : 'Lưu thay đổi để quay lại đúng điểm review hiện tại; run sẽ không bắt đầu lại từ đầu.'}
            </p>
            <div className="flex shrink-0 gap-2">
              <button type="button" onClick={onReturnToAutopilot} disabled={busy}
                className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-600 hover:bg-slate-50 disabled:opacity-50">
                Quay lại chưa lưu
              </button>
              <button type="button" onClick={saveAutopilotEditor} disabled={!canApprove || busy}
                className="rounded-lg bg-brand-500 px-3 py-2 text-xs font-bold text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-50">
                {busy
                  ? (currentStep === 2 ? 'Đang phân tích & lưu…' : 'Đang lưu…')
                  : (currentStep === 2 ? 'Phân tích, lưu & quay lại Autopilot' : 'Lưu & quay lại Autopilot')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
})

export default WorkspacePane
