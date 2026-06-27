// ─── DemoOverlay: Spotlight + Tooltip rendered via Portal ────────────────────
// Pure CSS spotlight (box-shadow trick) + positioned tooltip bubble.
// No external dependencies.

import { useEffect, useState, useRef, useCallback } from 'react'
import { createPortal } from 'react-dom'
import ReactMarkdown from 'react-markdown'
import { X, ChevronRight, SkipForward, Loader2, Play } from 'lucide-react'

// ─── Spotlight mask ──────────────────────────────────────────────────────────
function Spotlight({ rect }) {
  if (!rect) return null
  const padding = 8
  return (
    <div
      className="fixed inset-0 z-[9998] pointer-events-none transition-all duration-300"
      style={{
        boxShadow: `0 0 0 9999px rgba(0, 0, 0, 0.55)`,
        clipPath: `polygon(
          0% 0%, 0% 100%, 
          ${rect.left - padding}px 100%, 
          ${rect.left - padding}px ${rect.top - padding}px, 
          ${rect.right + padding}px ${rect.top - padding}px, 
          ${rect.right + padding}px ${rect.bottom + padding}px, 
          ${rect.left - padding}px ${rect.bottom + padding}px, 
          ${rect.left - padding}px 100%, 
          100% 100%, 100% 0%
        )`,
      }}
    />
  )
}

// ─── Calculate tooltip position ──────────────────────────────────────────────
function calcPosition(rect, position, tooltipSize) {
  const gap = 16
  const vw = window.innerWidth
  const vh = window.innerHeight

  let top, left

  switch (position) {
    case 'right':
      top = rect.top + rect.height / 2 - tooltipSize.height / 2
      left = rect.right + gap
      break
    case 'left':
      top = rect.top + rect.height / 2 - tooltipSize.height / 2
      left = rect.left - gap - tooltipSize.width
      break
    case 'top':
      top = rect.top - gap - tooltipSize.height
      left = rect.left + rect.width / 2 - tooltipSize.width / 2
      break
    case 'bottom':
    default:
      top = rect.bottom + gap
      left = rect.left + rect.width / 2 - tooltipSize.width / 2
      break
  }

  // Clamp to viewport
  top = Math.max(8, Math.min(top, vh - tooltipSize.height - 8))
  left = Math.max(8, Math.min(left, vw - tooltipSize.width - 8))

  return { top, left }
}

// ─── Tooltip Bubble ──────────────────────────────────────────────────────────
function TooltipBubble({
  title,
  text,
  position = 'bottom',
  targetRect,
  stepIdx,
  totalSteps,
  onNext,
  onSkip,
  isWaiting,
  showNext = true,
}) {
  const ref = useRef(null)
  const [tooltipSize, setTooltipSize] = useState({ width: 340, height: 200 })
  const [pos, setPos] = useState({ top: 0, left: 0 })

  useEffect(() => {
    if (ref.current) {
      const { width, height } = ref.current.getBoundingClientRect()
      setTooltipSize({ width, height })
    }
  }, [title, text])

  useEffect(() => {
    if (targetRect) {
      setPos(calcPosition(targetRect, position, tooltipSize))
    } else {
      // Center on screen
      setPos({
        top: window.innerHeight / 2 - tooltipSize.height / 2,
        left: window.innerWidth / 2 - tooltipSize.width / 2,
      })
    }
  }, [targetRect, position, tooltipSize])

  return (
    <div
      ref={ref}
      className="fixed z-[10000] w-[340px] animate-fade-in"
      style={{ top: pos.top, left: pos.left }}
    >
      <div className="bg-white rounded-2xl shadow-2xl border border-brand-200 overflow-hidden">
        {/* Header */}
        <div className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-brand-500 to-brand-600">
          <Play className="w-3.5 h-3.5 text-white/80" />
          <span className="text-xs font-bold text-white">Demo Guide</span>
          <span className="ml-auto text-[10px] font-semibold text-white/70">
            {stepIdx + 1}/{totalSteps}
          </span>
          <button
            onClick={onSkip}
            className="ml-1 p-0.5 rounded hover:bg-white/20 transition-colors"
            title="Thoát demo"
          >
            <X className="w-3.5 h-3.5 text-white/80" />
          </button>
        </div>

        {/* Body */}
        <div className="px-4 py-3">
          {title && (
            <h3 className="text-sm font-bold text-foreground mb-1.5">{title}</h3>
          )}
          <div className="text-xs text-muted-foreground leading-relaxed markdown-content [&_strong]:text-foreground [&_strong]:font-semibold">
            <ReactMarkdown>{text}</ReactMarkdown>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center gap-2 px-4 py-2.5 border-t border-border bg-slate-50/50">
          <button
            onClick={onSkip}
            className="text-[11px] font-semibold text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
          >
            <SkipForward className="w-3 h-3" />
            Bỏ qua
          </button>
          <div className="flex-1" />
          {/* Progress dots */}
          <div className="flex gap-0.5">
            {Array.from({ length: Math.min(totalSteps, 20) }).map((_, i) => (
              <div
                key={i}
                className={`w-1.5 h-1.5 rounded-full transition-all ${
                  i === stepIdx
                    ? 'bg-brand-500 scale-125'
                    : i < stepIdx
                      ? 'bg-brand-300'
                      : 'bg-slate-200'
                }`}
              />
            ))}
          </div>
          <div className="flex-1" />
          {showNext && (
            <button
              onClick={onNext}
              disabled={isWaiting}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-brand-500 hover:bg-brand-600 disabled:bg-brand-300 text-white text-xs font-bold transition-all active:scale-95"
            >
              {isWaiting ? (
                <>
                  <Loader2 className="w-3 h-3 animate-spin" />
                  Đang chờ...
                </>
              ) : (
                <>
                  Tiếp theo
                  <ChevronRight className="w-3 h-3" />
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Confirmation Popup ──────────────────────────────────────────────────────
// Supports a `buttons` array: [{ label, variant, action }]
// variant: 'primary' | 'outline' | 'ghost'
function DemoPopup({ title, text, buttons = [], onAction }) {
  return (
    <div className="fixed inset-0 z-[10001] flex items-center justify-center bg-black/50 animate-fade-in">
      <div className="bg-white rounded-2xl shadow-2xl border border-brand-200 w-[420px] max-w-[90vw] overflow-hidden">
        <div className="px-6 py-4 bg-gradient-to-r from-brand-500 to-brand-600">
          <h2 className="text-base font-bold text-white">{title}</h2>
        </div>
        <div className="px-6 py-4">
          <div className="text-sm text-muted-foreground leading-relaxed markdown-content [&_strong]:text-foreground [&_strong]:font-semibold">
            <ReactMarkdown>{text}</ReactMarkdown>
          </div>
        </div>
        <div className="flex flex-col gap-2 px-6 py-4 border-t border-border bg-slate-50/50">
          {buttons.map((btn, i) => (
            <button
              key={i}
              onClick={() => onAction(btn.action)}
              className={[
                'w-full px-4 py-2.5 rounded-xl text-sm font-semibold transition-all active:scale-95',
                btn.variant === 'primary'
                  ? 'bg-brand-500 hover:bg-brand-600 text-white'
                  : btn.variant === 'outline'
                    ? 'border border-brand-300 bg-white hover:bg-brand-50 text-brand-700'
                    : 'border border-border bg-white hover:bg-muted text-muted-foreground',
              ].join(' ')}
            >
              {btn.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}


// ─── Main DemoOverlay ────────────────────────────────────────────────────────
const SHOW_NEXT_TYPES = new Set(['TOOLTIP', 'HIGHLIGHT_MSG', 'HIGHLIGHT_EL', 'EDIT_FIELD'])
const SHOW_TOOLTIP_TYPES = new Set(['TOOLTIP', 'HIGHLIGHT_MSG', 'HIGHLIGHT_EL', 'WAIT_FOR_RESPONSE', 'WAIT_FOR_EVENT', 'WAIT_FOR_MSG', 'TYPE_AND_SEND', 'EDIT_FIELD', 'CLICK_EL'])

export default function DemoOverlay({
  isActive,
  currentStep,
  stepIdx,
  totalSteps,
  targetRect,
  onNext,
  onSkip,
  isWaiting,
  // For POPUP type
  popup,
  onPopupAction,
}) {
  if (!isActive) return null

  // Extract title/text/position from step (direct or nested under .tooltip)
  const stepTitle = currentStep?.title ?? currentStep?.tooltip?.title
  const stepText  = currentStep?.text  ?? currentStep?.tooltip?.text
  const stepPos   = currentStep?.position ?? currentStep?.tooltip?.position ?? 'bottom'
  const stepTarget = currentStep?.target ?? currentStep?.tooltip?.target

  const showTooltip = currentStep && !popup && SHOW_TOOLTIP_TYPES.has(currentStep.type)
  const showNext = currentStep && SHOW_NEXT_TYPES.has(currentStep.type)

  return createPortal(
    <>
      {/* Click-blocker — blocks interaction but forwards wheel scroll through */}
      {!popup && (
        <div
          className="fixed inset-0 z-[9997]"
          onClickCapture={(e) => { e.stopPropagation(); e.preventDefault() }}
          onMouseDownCapture={(e) => { e.stopPropagation(); e.preventDefault() }}
          onTouchStartCapture={(e) => e.stopPropagation()}
          onWheelCapture={(e) => {
            // Temporarily make overlay invisible to hit-testing so
            // elementFromPoint returns the real element underneath (e.g. chat ScrollArea)
            const overlay = e.currentTarget
            overlay.style.pointerEvents = 'none'
            const el = document.elementFromPoint(e.clientX, e.clientY)
            overlay.style.pointerEvents = ''

            let node = el
            while (node && node !== document.body) {
              const style = window.getComputedStyle(node)
              const overflow = style.overflow + style.overflowY
              if (/auto|scroll/.test(overflow) && node.scrollHeight > node.clientHeight) {
                node.scrollTop += e.deltaY
                break
              }
              node = node.parentElement
            }
          }}
        />
      )}

      {/* Spotlight */}
      {!popup && <Spotlight rect={targetRect} />}

      {/* Make the spotlighted area clickable above the blocker */}
      {targetRect && !popup && (
        <div
          className="fixed z-[9999]"
          style={{
            top: targetRect.top - 8,
            left: targetRect.left - 8,
            width: targetRect.width + 16,
            height: targetRect.height + 16,
          }}
        />
      )}

      {/* Tooltip — shown for most step types */}
      {showTooltip && stepText && (
        <TooltipBubble
          title={stepTitle}
          text={stepText}
          position={stepPos}
          targetRect={targetRect}
          stepIdx={stepIdx}
          totalSteps={totalSteps}
          onNext={onNext}
          onSkip={onSkip}
          isWaiting={isWaiting}
          showNext={showNext}
        />
      )}

      {/* Popup */}
      {popup && (
        <DemoPopup
          title={popup.title}
          text={popup.text}
          buttons={popup.buttons || []}
          onAction={onPopupAction}
        />
      )}
    </>,
    document.body
  )
}
