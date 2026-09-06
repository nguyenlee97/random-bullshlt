import { useEffect, useRef, useState } from 'react'
import { Check, ChevronDown, Lock, MessageSquare, RefreshCw, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { isStepReachable } from '@/lib/nonLinearWorkflow'

const statusCopy = status => {
  if (status === 'done') return 'Hoàn tất'
  if (status === 'stale') return 'Cần xem lại'
  return 'Chưa tới'
}

function StepMarker({ index, status, current, reachable }) {
  if (status === 'done') return <Check className="h-3 w-3" />
  if (status === 'stale') return <RefreshCw className="h-3 w-3" />
  if (!reachable && !current) return <Lock className="h-3 w-3" />
  return index + 1
}

export default function Stepper({ steps, currentStep, stepStatuses, onStepJump, onOpenChat, chatOpen = true }) {
  const [sheetOpen, setSheetOpen] = useState(false)
  const closeButtonRef = useRef(null)
  const doneCount = stepStatuses.filter(status => status === 'done').length
  const progress = Math.round((doneCount / steps.length) * 100)
  const step = steps[currentStep]
  const currentStatus = stepStatuses[currentStep]
  const decisionCopy = currentStatus === 'done'
    ? 'ĐÃ HOÀN THÀNH'
    : currentStatus === 'stale'
      ? 'CẦN BẠN XEM LẠI'
      : 'CẦN BẠN QUYẾT ĐỊNH'

  const jump = index => {
    if (!isStepReachable(index, currentStep, stepStatuses)) return
    onStepJump(index)
    setSheetOpen(false)
  }

  useEffect(() => {
    if (!sheetOpen) return undefined
    const previouslyFocused = document.activeElement
    const closeOnEscape = event => {
      if (event.key === 'Escape') setSheetOpen(false)
    }
    closeButtonRef.current?.focus()
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('keydown', closeOnEscape)
      previouslyFocused?.focus?.()
    }
  }, [sheetOpen])

  return (
    <div data-demo="stepper" className="flex-shrink-0 bg-[#020817] text-slate-200">
      <div className="hidden min-h-[58px] items-center gap-2 px-3 lg:flex xl:px-4">
        {!chatOpen && (
          <button type="button" onClick={onOpenChat} aria-label="Mở chat với Agent" title="Mở chat với Agent"
            className="mr-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-slate-800 text-slate-400 hover:bg-slate-900 hover:text-white">
            <MessageSquare className="h-4 w-4" />
          </button>
        )}
        <nav aria-label="Tiến trình 7 bước" className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {steps.map((item, index) => {
            const status = stepStatuses[index]
            const current = index === currentStep
            const reachable = isStepReachable(index, currentStep, stepStatuses)
            return (
              <button key={item.id} type="button" onClick={() => jump(index)} disabled={!reachable}
                aria-current={current ? 'step' : undefined}
                title={`${item.title} · ${current ? decisionCopy.toLowerCase() : statusCopy(status)}`}
                className={cn(
                  'flex h-10 shrink-0 items-center gap-2 rounded-lg px-2.5 text-[11px] font-bold transition-colors',
                  current && 'bg-slate-800 text-white',
                  !current && reachable && 'text-slate-400 hover:bg-slate-900 hover:text-white',
                  !reachable && 'cursor-not-allowed text-slate-700',
                )}>
                <span className={cn(
                  'flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full border text-[10px] font-black',
                  status === 'done' && 'border-brand-500 bg-brand-500 text-white',
                  status === 'stale' && 'border-amber-400 bg-amber-400 text-slate-950',
                  current && status !== 'done' && status !== 'stale' && 'border-brand-400 bg-brand-500 text-white',
                  !current && !['done', 'stale'].includes(status) && 'border-slate-700 bg-slate-900 text-slate-500',
                )}>
                  <StepMarker index={index} status={status} current={current} reachable={reachable} />
                </span>
                <span className="hidden xl:inline">{item.title}</span>
              </button>
            )
          })}
        </nav>
        <div className="ml-auto flex shrink-0 items-center gap-2 border-l border-slate-800 pl-3 text-[10px] font-black tracking-[.08em] text-slate-400">
          <span className="text-white">{currentStep + 1}/{steps.length}</span>
          <span className={currentStatus === 'stale' ? 'text-amber-300' : 'text-cyan-300'}>{decisionCopy}</span>
        </div>
      </div>

      <button type="button" onClick={() => setSheetOpen(true)} aria-label="Mở danh sách 7 bước" aria-expanded={sheetOpen} aria-controls="copilot-step-sheet"
        className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left lg:hidden">
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-500 text-[10px] font-black text-white">{currentStep + 1}</span>
        <span className="min-w-0 flex-1">
          <strong className="block truncate text-xs">Bước {currentStep + 1}/{steps.length} · {step.title}</strong>
          <small className="mt-0.5 block truncate text-[10px] font-semibold tracking-wide text-slate-400">{decisionCopy}</small>
        </span>
        <span className="h-1 w-16 overflow-hidden rounded-full bg-slate-800"><span className="block h-full rounded-full bg-brand-500" style={{ width: `${Math.max(progress, ((currentStep + 1) / steps.length) * 100)}%` }} /></span>
        <ChevronDown className="h-4 w-4 text-slate-400" />
      </button>

      {sheetOpen && (
        <div className="fixed inset-0 z-[90] flex items-end bg-slate-950/55 backdrop-blur-[2px] lg:hidden" onMouseDown={() => setSheetOpen(false)}>
          <section id="copilot-step-sheet" role="dialog" aria-modal="true" aria-label="Tiến trình 7 bước" onMouseDown={event => event.stopPropagation()}
            className="max-h-[78dvh] w-full overflow-y-auto rounded-t-[22px] bg-[#020817] px-4 pb-[calc(20px+env(safe-area-inset-bottom))] pt-4 text-white shadow-2xl">
            <div className="mb-4 flex items-center justify-between">
              <div><p className="text-[10px] font-black tracking-[.16em] text-slate-500">COPILOT · 7 BƯỚC</p><h2 className="mt-1 text-base font-black">Tiến trình campaign</h2></div>
              <button ref={closeButtonRef} type="button" onClick={() => setSheetOpen(false)} aria-label="Đóng danh sách bước" className="flex h-11 w-11 items-center justify-center rounded-xl border border-slate-800"><X className="h-4 w-4" /></button>
            </div>
            <div className="space-y-2">
              {steps.map((item, index) => {
                const status = stepStatuses[index]
                const current = index === currentStep
                const reachable = isStepReachable(index, currentStep, stepStatuses)
                return (
                  <button key={item.id} type="button" disabled={!reachable} onClick={() => jump(index)}
                    className={cn('flex min-h-12 w-full items-center gap-3 rounded-xl border px-3 py-2 text-left', current ? 'border-brand-500 bg-brand-500/15' : 'border-slate-800 bg-slate-900/60', !reachable && 'opacity-45')}>
                    <span className={cn('flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[11px] font-black', status === 'done' ? 'bg-brand-500' : status === 'stale' ? 'bg-amber-400 text-slate-950' : 'bg-slate-800')}><StepMarker index={index} status={status} current={current} reachable={reachable} /></span>
                    <span className="min-w-0 flex-1"><strong className="block text-sm">{item.title}</strong><small className="text-[11px] text-slate-400">{current ? decisionCopy : statusCopy(status)}</small></span>
                  </button>
                )
              })}
            </div>
          </section>
        </div>
      )}
    </div>
  )
}
