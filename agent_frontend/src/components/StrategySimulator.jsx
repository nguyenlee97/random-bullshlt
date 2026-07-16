import { Check, Gauge, ShieldAlert, Users, WalletCards } from 'lucide-react'

const scaled = (value, unit) => {
  const amount = Number(value || 0)
  const format = number => new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 1 }).format(number)
  if (amount >= 1_000_000) return `${format(amount / 1_000_000)} triệu ${unit}`
  if (amount >= 1_000) return `${format(amount / 1_000)} nghìn ${unit}`
  return `${format(amount)} ${unit}`
}
const money = value => `${new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 0 }).format(Number(value || 0))} ₫`

const RISK = {
  low: { label: 'Rủi ro thấp', className: 'bg-green-50 text-green-700' },
  medium: { label: 'Rủi ro vừa', className: 'bg-amber-50 text-amber-800' },
  high: { label: 'Rủi ro cao', className: 'bg-red-50 text-red-700' },
}

export default function StrategySimulator({ value, busy, canSelect = true, selectionHint = '', onSelect }) {
  const options = Array.isArray(value?.options) ? value.options : []
  if (!options.length) return null

  return (
    <section className="mt-3 rounded-2xl border border-brand-200 bg-gradient-to-br from-white to-brand-50/60 p-3 sm:p-4" aria-labelledby="strategy-simulator-title">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-brand-600">Tính năng nổi bật</p>
          <h3 id="strategy-simulator-title" className="mt-1 text-sm font-extrabold text-slate-900">Mô phỏng chiến lược campaign</h3>
          <p className="mt-1 max-w-3xl text-xs leading-5 text-slate-600">
            So sánh 3 cách phân bổ ngân sách trước khi Agent chọn audience và placement. Số liệu là dự báo định hướng; forecast cuối dùng inventory thật.
          </p>
        </div>
        <span className="inline-flex w-fit items-center gap-1 rounded-full bg-white px-2 py-1 text-[10px] font-semibold text-slate-600 shadow-sm">
          <Gauge className="h-3 w-3 text-brand-500" /> Tính toán xác định
        </span>
      </div>

      <div className="mt-3 grid gap-2 lg:grid-cols-3">
        {options.map(option => {
          const selected = option.id === value.selected
          const metrics = option.metrics || {}
          const risk = RISK[metrics.risk] || RISK.medium
          return (
            <article key={option.id} className={`rounded-xl border bg-white p-3 transition-colors ${selected ? 'border-brand-400 ring-2 ring-brand-100' : 'border-slate-200'}`}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-bold text-slate-900">{option.label}</p>
                  <span className={`mt-1 inline-flex rounded-full px-2 py-0.5 text-[10px] font-bold ${risk.className}`}>{risk.label}</span>
                </div>
                {selected && <span className="inline-flex items-center gap-1 rounded-full bg-brand-500 px-2 py-1 text-[10px] font-bold text-white"><Check className="h-3 w-3" /> Đang chọn</span>}
              </div>

              <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
                <div className="rounded-lg bg-slate-50 p-2">
                  <dt className="flex items-center gap-1 text-[10px] text-slate-500"><Users className="h-3 w-3" /> Độ phủ dự kiến</dt>
                  <dd className="mt-0.5 font-bold text-slate-900">{scaled(metrics.estimated_reach, 'người')}</dd>
                </div>
                <div className="rounded-lg bg-slate-50 p-2">
                  <dt className="flex items-center gap-1 text-[10px] text-slate-500"><WalletCards className="h-3 w-3" /> CPM giả định</dt>
                  <dd className="mt-0.5 font-bold text-slate-900">{money(metrics.average_cpm)}</dd>
                </div>
              </dl>

              <p className="mt-3 min-h-10 text-xs leading-5 text-slate-600">{option.rationale}</p>
              <p className="mt-2 text-[10px] text-slate-500">Tần suất {metrics.frequency || '—'} · {scaled(metrics.estimated_impressions, 'lượt hiển thị')}</p>

              {!selected && canSelect && (
                <button type="button" disabled={busy} onClick={() => onSelect?.(option.id)}
                  aria-label={`Chọn chiến lược ${option.label}`}
                  className="mt-3 w-full rounded-lg border border-brand-300 px-3 py-2 text-xs font-bold text-brand-700 hover:bg-brand-50 disabled:cursor-wait disabled:opacity-60">
                  Chọn phương án này
                </button>
              )}
            </article>
          )
        })}
      </div>

      <div className="mt-3 flex items-start gap-2 rounded-xl bg-white/80 px-3 py-2 text-xs text-slate-600">
        <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" />
        <div>
          <p><span className="font-bold text-slate-800">Vì sao chọn:</span> {value.selected_reason || 'Phù hợp nhất với objective và ngân sách hiện tại.'}</p>
          {selectionHint && <p className="mt-1 font-medium text-brand-700">{selectionHint}</p>}
        </div>
      </div>
    </section>
  )
}
