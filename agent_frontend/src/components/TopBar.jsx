import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { ArrowUpFromLine, Bot, Check, RotateCcw, Play, History } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useDemo } from '@/demo/DemoEngine'
import AccountMenu from '@/components/AccountMenu'

const MOBILE_BOTTOM_CLEARANCE_KEY = 'advertising-agent:mobile-bottom-clearance'
const MOBILE_BOTTOM_HELP_SEEN_KEY = 'advertising-agent:mobile-bottom-help-seen'
const MOBILE_BOTTOM_CLEARANCE_OPTIONS = [
  { value: 0, label: 'Mặc định', hint: 'Không thêm khoảng trống' },
  { value: 24, label: 'Nhỏ', hint: 'Nâng 24 px' },
  { value: 48, label: 'Vừa', hint: 'Nâng 48 px' },
  { value: 72, label: 'Lớn', hint: 'Nâng 72 px' },
]

function initialMobileBottomClearance() {
  if (typeof window === 'undefined') return 0
  try {
    const stored = Number.parseInt(window.localStorage.getItem(MOBILE_BOTTOM_CLEARANCE_KEY) || '0', 10)
    return MOBILE_BOTTOM_CLEARANCE_OPTIONS.some(option => option.value === stored) ? stored : 0
  } catch {
    return 0
  }
}

function MobileBottomClearanceControl() {
  const [open, setOpen] = useState(false)
  const [clearance, setClearance] = useState(initialMobileBottomClearance)
  const [hasSeenHelp, setHasSeenHelp] = useState(() => {
    if (typeof window === 'undefined') return false
    try {
      return window.localStorage.getItem(MOBILE_BOTTOM_HELP_SEEN_KEY) === 'true'
    } catch {
      return false
    }
  })
  const controlRef = useRef(null)
  const dialogRef = useRef(null)

  useEffect(() => {
    document.documentElement.style.setProperty('--mobile-bottom-clearance', `${clearance}px`)
    try {
      window.localStorage.setItem(MOBILE_BOTTOM_CLEARANCE_KEY, String(clearance))
    } catch {
      // The control still works for this page when storage is unavailable.
    }
  }, [clearance])

  useEffect(() => {
    if (!open) return undefined
    const closeOutside = event => {
      if (
        !controlRef.current?.contains(event.target)
        && !dialogRef.current?.contains(event.target)
      ) {
        setOpen(false)
      }
    }
    const closeOnEscape = event => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('pointerdown', closeOutside)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('pointerdown', closeOutside)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [open])

  const activeLabel = MOBILE_BOTTOM_CLEARANCE_OPTIONS.find(option => option.value === clearance)?.label || 'Mặc định'
  const toggleHelp = () => {
    setOpen(value => !value)
    if (!hasSeenHelp) {
      setHasSeenHelp(true)
      try {
        window.localStorage.setItem(MOBILE_BOTTOM_HELP_SEEN_KEY, 'true')
      } catch {
        // Discovery animation can stop for this page even without storage.
      }
    }
  }

  return (
    <div ref={controlRef} className="mobile-bottom-helper relative">
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={toggleHelp}
        className={`relative h-8 shrink-0 border-violet-400 bg-violet-50 px-2 text-xs text-violet-800 shadow-sm hover:border-violet-500 hover:bg-violet-100 ${
          hasSeenHelp ? '' : 'mobile-bottom-attention-button'
        }`}
        aria-label={`Nâng đáy giao diện: ${activeLabel}`}
        aria-expanded={open}
        aria-haspopup="dialog"
        title="Nâng giao diện khỏi thanh điều hướng điện thoại"
        id="mobile-bottom-clearance-btn"
      >
        <ArrowUpFromLine className="h-3.5 w-3.5" />
        {(!hasSeenHelp || clearance > 0) && (
          <span className="absolute -right-1 -top-1 min-w-4 rounded-full bg-violet-600 px-1 text-[9px] font-bold leading-4 text-white">
            {clearance > 0 ? clearance : '!'}
          </span>
        )}
      </Button>

      {open && typeof document !== 'undefined' && createPortal(
        <div
          ref={dialogRef}
          role="dialog"
          aria-label="Điều chỉnh khoảng trống đáy màn hình"
          className="fixed inset-x-2 top-[calc(env(safe-area-inset-top,0px)+3.5rem)] z-[80] max-h-[calc(var(--visual-viewport-height,100dvh)-4.5rem)] w-auto overflow-y-auto overscroll-contain rounded-2xl border border-violet-200 bg-white p-3 shadow-2xl"
        >
          <p className="text-sm font-bold text-slate-900">Nâng đáy giao diện</p>
          <p className="mt-1 text-xs leading-5 text-slate-600">
            Nếu ô Chat hoặc nút gửi bị che ở cuối màn hình, hãy dùng tính năng này để nâng toàn bộ phần đáy giao diện lên cho đến khi thao tác lại thoải mái.
          </p>
          <p className="mt-2 rounded-lg bg-violet-50 px-2.5 py-2 text-[11px] leading-4 text-violet-800">
            Chọn mức thấp nhất đủ để thấy trọn ô Chat. Thiết lập được ghi nhớ trên thiết bị này và có thể đưa về Mặc định bất cứ lúc nào.
          </p>
          <div className="mt-3 grid grid-cols-1 gap-2 min-[360px]:grid-cols-2">
            {MOBILE_BOTTOM_CLEARANCE_OPTIONS.map(option => (
              <button
                key={option.value}
                type="button"
                onClick={() => {
                  setClearance(option.value)
                  setOpen(false)
                }}
                aria-pressed={clearance === option.value}
                className={`flex min-h-14 items-center justify-between rounded-xl border px-3 py-2 text-left transition-colors ${
                  clearance === option.value
                    ? 'border-brand-500 bg-brand-50 text-brand-800'
                    : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                }`}
              >
                <span>
                  <span className="block text-xs font-bold">{option.label}</span>
                  <span className="mt-0.5 block text-[10px] text-slate-500">{option.hint}</span>
                </span>
                {clearance === option.value && <Check className="h-4 w-4 text-brand-600" />}
              </button>
            ))}
          </div>
        </div>,
        document.body,
      )}
    </div>
  )
}

export default function TopBar({
  onReset, onManage, onOpenHistory, showDemo, experienceMode,
  identity, identityBusy, onLogin, onLogout, onLoadSessions, onRevokeSession,
  onLinkZalo, onOpenZaloOA, onUnlinkZaloOA,
}) {
  const demo = useDemo()
  const [resetConfirmOpen, setResetConfirmOpen] = useState(false)

  return (
    <header className="h-14 flex items-center gap-2 px-2 sm:gap-3 sm:px-5 border-b border-border bg-white/95 backdrop-blur-md shadow-sm flex-shrink-0 z-10">
      {/* Logo */}
      <button
        type="button"
        onClick={onManage}
        className="flex shrink-0 items-center gap-2.5 rounded-xl text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2"
        aria-label="Về trang quản lý campaign"
        title="Về trang quản lý campaign"
      >
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-brand-600 flex items-center justify-center shadow-sm">
          <Bot className="w-4.5 h-4.5 text-white" strokeWidth={2.5} />
        </div>
        <div className="hidden sm:flex items-baseline gap-1.5">
          <span className="font-black text-base text-slate-900 tracking-tight">Advertising</span>
          <span className="font-black text-base text-brand-600 tracking-tight">Agent</span>
        </div>
      </button>

      <div className="ml-auto flex min-w-0 items-center gap-1 sm:gap-2">

        {/* Guided tour stays discoverable after workspace entry. */}
        {showDemo && demo && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => demo.startDemo(experienceMode === 'autopilot' ? 'autopilot' : 'copilot')}
            className="tour-attention-button flex h-8 shrink-0 gap-1.5 border-amber-500 bg-amber-400 px-2 text-xs font-black text-amber-950 shadow-md shadow-amber-200/70 hover:border-amber-600 hover:bg-amber-300 sm:px-3"
            id="demo-btn"
            aria-label="Bắt đầu guided tour"
          >
            <Play className="w-3.5 h-3.5" />
            <span className="hidden min-[400px]:inline">Tour</span>
          </Button>
        )}

        <Button
          variant="outline"
          size="sm"
          onClick={onOpenHistory}
          className="h-8 shrink-0 gap-1.5 px-2 text-xs sm:px-3"
          title="Lịch sử chiến dịch"
          aria-label="Mở lịch sử chiến dịch"
          id="conversation-history-btn"
        >
          <History className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Lịch sử</span>
        </Button>

        {/* Đặt lại — workspace reset only */}
        <Button variant="outline" size="sm" onClick={() => setResetConfirmOpen(true)} className="h-8 shrink-0 gap-1.5 px-2 text-xs sm:px-3" data-demo="reset-btn" aria-label="Đặt lại workspace">
          <RotateCcw className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Đặt lại</span>
        </Button>

        <MobileBottomClearanceControl />

        <AccountMenu identity={identity} busy={identityBusy} onLogin={onLogin} onLogout={onLogout}
          onLoadSessions={onLoadSessions} onRevokeSession={onRevokeSession}
          onLinkZalo={onLinkZalo} onOpenZaloOA={onOpenZaloOA} onUnlinkZaloOA={onUnlinkZaloOA} compact />
      </div>

      {resetConfirmOpen && typeof document !== 'undefined' && createPortal(
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/55 p-3"
          role="presentation"
          onMouseDown={event => {
            if (event.target === event.currentTarget) setResetConfirmOpen(false)
          }}
        >
          <div
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="reset-workspace-title"
            aria-describedby="reset-workspace-description"
            className="flex max-h-[calc(100dvh-24px)] w-full max-w-sm flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl"
          >
            <div className="min-h-0 overflow-y-auto p-4 sm:p-5">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-100 text-amber-700">
                <RotateCcw className="h-5 w-5" />
              </div>
              <h2 id="reset-workspace-title" className="mt-3 text-base font-black text-slate-900">
                Đặt lại workspace?
              </h2>
              <p id="reset-workspace-description" className="mt-1.5 text-sm leading-6 text-slate-600">
                Trang sẽ chuyển sang một campaign mới. Campaign và lịch sử hiện tại vẫn được lưu để bạn mở lại từ mục Lịch sử.
              </p>
            </div>
            <div className="flex flex-col-reverse gap-2 border-t border-slate-200 bg-slate-50 p-3 min-[360px]:flex-row min-[360px]:justify-end sm:p-4">
              <Button type="button" variant="outline" onClick={() => setResetConfirmOpen(false)}>
                Giữ nguyên
              </Button>
              <Button
                type="button"
                onClick={() => {
                  setResetConfirmOpen(false)
                  onReset?.()
                }}
                className="bg-amber-600 text-white hover:bg-amber-700"
              >
                Đặt lại
              </Button>
            </div>
          </div>
        </div>,
        document.body,
      )}
    </header>
  )
}
