import { Loader2, Route, Sparkles } from 'lucide-react'

const MODES = [
  {
    id: 'guided',
    label: 'Quy trình hướng dẫn',
    shortLabel: 'Hướng dẫn',
    icon: Route,
  },
  {
    id: 'autopilot',
    label: 'Campaign Autopilot',
    shortLabel: 'Autopilot',
    icon: Sparkles,
  },
]

function statusLabel(summary) {
  if (!summary?.status) return null
  if (summary.status === 'waiting_review') return 'Cần duyệt'
  if (summary.status === 'running') return `${summary.progress || 0}%`
  if (summary.status === 'paused') return 'Tạm dừng'
  if (summary.status === 'completed') return 'Hoàn tất'
  return null
}

export default function ModeSwitcher({ value, onChange, busy = false, error = '', mobile = false, autopilotSummary }) {
  const runLabel = statusLabel(autopilotSummary)

  return (
    <div
      className={mobile
        ? 'border-t border-slate-200 bg-white/95 px-3 pb-[calc(0.5rem+env(safe-area-inset-bottom))] pt-2 shadow-[0_-8px_24px_rgba(15,23,42,0.08)] backdrop-blur-md'
        : 'border-b border-slate-200 bg-white/90 px-5 py-2 backdrop-blur-md'}
    >
      <div
        role="tablist"
        aria-label="Chọn chế độ làm việc"
        className={mobile
          ? 'mx-auto grid max-w-md grid-cols-2 gap-2'
          : 'mx-auto flex max-w-7xl items-center gap-2'}
      >
        {MODES.map(mode => {
          const Icon = mode.icon
          const selected = value === mode.id
          return (
            <button
              key={mode.id}
              type="button"
              role="tab"
              aria-selected={selected}
              aria-controls={`${mode.id}-canvas`}
              disabled={busy}
              onClick={() => onChange(mode.id)}
              className={`relative inline-flex min-h-10 items-center justify-center gap-2 rounded-xl px-3 text-xs font-bold transition-all focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-brand-200 disabled:cursor-wait disabled:opacity-60 ${
                selected
                  ? 'bg-brand-500 text-white shadow-sm'
                  : 'border border-slate-200 bg-white text-slate-600 hover:border-brand-200 hover:bg-brand-50 hover:text-brand-700'
              } ${mobile ? 'flex-col gap-0.5 py-1.5' : ''}`}
            >
              {busy && selected ? <Loader2 className="h-4 w-4 animate-spin" /> : <Icon className="h-4 w-4" />}
              <span>{mobile ? mode.shortLabel : mode.label}</span>
              {mode.id === 'autopilot' && runLabel && (
                <span className={`${mobile ? 'absolute right-1.5 top-1.5 h-2 w-2 overflow-hidden p-0 text-transparent' : 'ml-1 rounded-full px-2 py-0.5 text-[10px]'} ${
                  autopilotSummary?.status === 'waiting_review'
                    ? 'bg-amber-400 text-amber-950'
                    : selected ? 'bg-white/20 text-white' : 'bg-brand-50 text-brand-700'
                }`} aria-label={`Autopilot: ${runLabel}`}>
                  {runLabel}
                </span>
              )}
            </button>
          )
        })}
        {!mobile && (
          <p className="ml-2 text-[11px] text-slate-500">
            Chuyển chế độ không làm mất chat, workspace hoặc tiến độ đang chạy.
          </p>
        )}
      </div>
      {error && <p className="mx-auto mt-2 max-w-7xl text-xs font-medium text-red-600" role="alert">{error}</p>}
    </div>
  )
}
