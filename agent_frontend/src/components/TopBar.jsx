import { useEffect, useRef, useState } from 'react'
import { ArrowUpFromLine, Bot, Check, RotateCcw, Play, History } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useDemo } from '@/demo/DemoEngine'
import AccountMenu from '@/components/AccountMenu'

const MOBILE_BOTTOM_CLEARANCE_KEY = 'advertising-agent:mobile-bottom-clearance'
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
  const controlRef = useRef(null)

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
      if (!controlRef.current?.contains(event.target)) setOpen(false)
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

  return (
    <div ref={controlRef} className="mobile-bottom-helper relative">
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => setOpen(value => !value)}
        className="relative h-8 shrink-0 px-2 text-xs"
        aria-label={`Nâng đáy giao diện: ${activeLabel}`}
        aria-expanded={open}
        aria-haspopup="dialog"
        title="Nâng giao diện khỏi thanh điều hướng điện thoại"
        id="mobile-bottom-clearance-btn"
      >
        <ArrowUpFromLine className="h-3.5 w-3.5" />
        {clearance > 0 && (
          <span className="absolute -right-1 -top-1 min-w-4 rounded-full bg-brand-600 px-1 text-[9px] font-bold leading-4 text-white">
            {clearance}
          </span>
        )}
      </Button>

      {open && (
        <div
          role="dialog"
          aria-label="Điều chỉnh khoảng trống đáy màn hình"
          className="absolute right-0 top-10 z-[80] w-[min(18rem,calc(100vw-1rem))] rounded-2xl border border-slate-200 bg-white p-3 shadow-2xl"
        >
          <p className="text-sm font-bold text-slate-900">Nâng đáy giao diện</p>
          <p className="mt-1 text-xs leading-5 text-slate-600">
            Dùng khi thanh điều hướng điện thoại che ô chat hoặc nút thao tác.
          </p>
          <div className="mt-3 grid grid-cols-2 gap-2">
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
        </div>
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
            className="flex h-8 shrink-0 gap-1.5 border-amber-300 bg-amber-50 px-2 text-xs text-amber-700 hover:border-amber-400 hover:bg-amber-100 hover:animate-none sm:px-3 sm:animate-pulse"
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
        <Button variant="outline" size="sm" onClick={onReset} className="h-8 shrink-0 gap-1.5 px-2 text-xs sm:px-3" data-demo="reset-btn" aria-label="Đặt lại workspace">
          <RotateCcw className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Đặt lại</span>
        </Button>

        <MobileBottomClearanceControl />

        <AccountMenu identity={identity} busy={identityBusy} onLogin={onLogin} onLogout={onLogout}
          onLoadSessions={onLoadSessions} onRevokeSession={onRevokeSession}
          onLinkZalo={onLinkZalo} onOpenZaloOA={onOpenZaloOA} onUnlinkZaloOA={onUnlinkZaloOA} compact />
      </div>
    </header>
  )
}
