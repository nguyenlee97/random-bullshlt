import { useMemo, useState } from 'react'
import {
  BarChart3, CheckCircle2, ExternalLink, FileText, ImageIcon,
  LayoutDashboard, MapPin, ShieldCheck, Target, Users,
} from 'lucide-react'
import SuccessStep from '@/steps/SuccessStep'
import { buildCampaignOutcome, campaignDeliveryState } from '@/lib/campaignOutcome'

const ADSPILOT_URL = import.meta.env.VITE_ADSPILOT_URL || 'https://adspilot.pawgrammers.io.vn'

const fmt = value => new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 0 }).format(Number(value || 0))

const OBJECTIVE_LABELS = {
  awareness: 'Nhận biết',
  consideration: 'Cân nhắc',
  conversion: 'Chuyển đổi',
  retention: 'Giữ chân',
}

const STRATEGY_LABELS = {
  balanced: 'Cân bằng',
  reach_first: 'Ưu tiên độ phủ',
  quality_first: 'Ưu tiên chất lượng',
}

const RISK_LABELS = { low: 'Thấp', medium: 'Trung bình', high: 'Cao' }
const TARGETING_LABELS = {
  geo: 'Khu vực', age: 'Độ tuổi', gender: 'Giới tính', deviceOS: 'Hệ điều hành',
  deviceBrand: 'Thiết bị', marital: 'Hôn nhân', parental: 'Gia đình',
  education: 'Học vấn', income: 'Thu nhập', career: 'Nghề nghiệp',
  interest: 'Sở thích', weather: 'Thời tiết',
}

const TABS = [
  { id: 'result', label: 'Kết quả', icon: CheckCircle2 },
  { id: 'setup', label: 'Báo cáo setup', icon: FileText },
  { id: 'performance', label: 'Báo cáo hiệu suất', icon: BarChart3 },
]

function Metric({ label, value, note }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
      <p className="text-[10px] font-bold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-black text-slate-900">{value}</p>
      {note && <p className="mt-1 text-[10px] leading-4 text-slate-500">{note}</p>}
    </div>
  )
}

function Section({ icon: Icon, title, children }) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <h4 className="flex items-center gap-2 text-sm font-black text-slate-900">
        <Icon className="h-4 w-4 text-brand-600" /> {title}
      </h4>
      <div className="mt-3">{children}</div>
    </section>
  )
}

const audienceName = item => item.fullLabel || item.label || item.name || item.code || item._id || 'Segment'

const targetingRows = targeting => Object.entries(targeting || {}).filter(([, value]) => (
  value !== null && value !== undefined && value !== '' && (!Array.isArray(value) || value.length)
))

function SetupReport({ outcome }) {
  const delivery = campaignDeliveryState(outcome)
  const selectedStrategy = outcome.strategy.selected_option
    || outcome.strategy.selected
    || outcome.strategy.recommended_option
    || outcome.strategy.recommended
  const creativeById = Object.fromEntries(outcome.creative.files.map(file => [file.id, file]))

  return (
    <div className="space-y-4" data-testid="autopilot-setup-report">
      <div className="overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 to-brand-800 p-5 text-white shadow-lg">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-blue-200">Hồ sơ campaign</p>
            <h3 className="mt-1 text-xl font-black">{outcome.brief.brand || 'Campaign'} · Báo cáo setup</h3>
            <p className="mt-2 text-xs text-white/70">
              {OBJECTIVE_LABELS[outcome.brief.objective] || outcome.brief.objective || 'Chưa rõ mục tiêu'} · {outcome.brief.startDate || '—'} → {outcome.brief.endDate || '—'}
            </p>
          </div>
          <div className="rounded-xl border border-white/20 bg-white/10 px-3 py-2 text-right">
            <p className="text-[10px] text-white/60">Order</p>
            <p className="text-xs font-black">{outcome.orderId || 'Chưa tạo'}</p>
            <p className="mt-0.5 text-[10px] font-bold text-blue-100">{delivery.label}</p>
          </div>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="Ngân sách" value={`${fmt(Number(outcome.brief.budget) * 1_000_000)} ₫`} />
        <Metric label="Audience" value={`${outcome.audience.attrs?.length || 0} segment`} note={`${fmt(outcome.audienceSize)} người dự kiến`} />
        <Metric label="Placements" value={`${outcome.selectedZoneIds.length} vị trí`} note={`${outcome.creative.files.length} creative`} />
        <Metric label="Forecast" value={`${fmt(outcome.forecast.estimated_reach)} người`} note={`${fmt(outcome.forecast.estimated_impressions)} lượt hiển thị`} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Section icon={Target} title="Brief & chiến lược">
          <dl className="grid gap-2 text-xs sm:grid-cols-2">
            <div><dt className="text-slate-500">Thương hiệu</dt><dd className="font-bold text-slate-900">{outcome.brief.brand || '—'}</dd></div>
            <div><dt className="text-slate-500">Mục tiêu</dt><dd className="font-bold text-slate-900">{OBJECTIVE_LABELS[outcome.brief.objective] || outcome.brief.objective || '—'}</dd></div>
            <div><dt className="text-slate-500">Phương án</dt><dd className="font-bold text-slate-900">{STRATEGY_LABELS[selectedStrategy] || selectedStrategy || 'Agent đề xuất'}</dd></div>
            <div><dt className="text-slate-500">KPI</dt><dd className="font-bold text-slate-900">{outcome.brief.kpi || 'Theo forecast của Agent'}</dd></div>
          </dl>
        </Section>

        <Section icon={ShieldCheck} title="Dự báo & an toàn">
          <dl className="grid gap-2 text-xs sm:grid-cols-2">
            <div><dt className="text-slate-500">CPM trung bình</dt><dd className="font-bold text-slate-900">{fmt(outcome.forecast.average_cpm)} ₫</dd></div>
            <div><dt className="text-slate-500">Mức rủi ro</dt><dd className="font-bold text-slate-900">{RISK_LABELS[outcome.forecast.risk] || outcome.forecast.risk || '—'}</dd></div>
            <div><dt className="text-slate-500">Order guard</dt><dd className={`font-bold ${outcome.guard.passed ? 'text-green-700' : 'text-amber-700'}`}>{outcome.guard.passed ? 'PASS' : 'Chưa có kết quả'}</dd></div>
            <div><dt className="text-slate-500">Trạng thái giao quảng cáo</dt><dd className="font-bold text-slate-900">{delivery.label}</dd></div>
          </dl>
        </Section>

        <Section icon={Users} title="Audience đã chọn">
          {outcome.audience.attrs?.length ? (
            <ul className="space-y-2">
              {outcome.audience.attrs.map((item, index) => (
                <li key={item._id || item.code || index} className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
                  <p className="text-xs font-bold text-slate-900">{audienceName(item)}</p>
                  {(item.reason || item.description) && <p className="mt-0.5 text-[10px] leading-4 text-slate-500">{item.reason || item.description}</p>}
                </li>
              ))}
            </ul>
          ) : <p className="text-xs text-slate-500">Chưa có segment audience.</p>}
        </Section>

        <Section icon={MapPin} title="Targeting đã áp dụng">
          {targetingRows(outcome.targeting).length ? (
            <dl className="space-y-2">
              {targetingRows(outcome.targeting).map(([key, value]) => (
                <div key={key} className="flex items-start justify-between gap-3 rounded-xl bg-slate-50 px-3 py-2 text-xs">
                  <dt className="font-semibold text-slate-500">{TARGETING_LABELS[key] || key}</dt>
                  <dd className="text-right font-bold text-slate-900">{Array.isArray(value) ? value.join(', ') : String(value)}</dd>
                </div>
              ))}
            </dl>
          ) : <p className="text-xs text-slate-500">Chưa có targeting.</p>}
        </Section>
      </div>

      <Section icon={ImageIcon} title="Placement & creative mapping">
        <div className="grid gap-3 md:grid-cols-2">
          {outcome.zones.map(zone => {
            const file = creativeById[outcome.setup.assignments[zone.id]]
            return (
              <article key={zone.id} className="flex gap-3 rounded-xl border border-slate-200 p-3">
                <div className="flex h-14 w-20 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-slate-100">
                  {file?.dataUrl ? <img src={file.dataUrl} alt="" className="h-full w-full object-cover" /> : <ImageIcon className="h-5 w-5 text-slate-300" />}
                </div>
                <div className="min-w-0">
                  <p className="truncate text-xs font-bold text-slate-900">{zone.name || zone.id}</p>
                  <p className="mt-0.5 text-[10px] text-slate-500">{zone.channel || zone.platform || 'Placement'} · {zone.size || `${zone.width || '—'}×${zone.height || '—'}`}</p>
                  <p className="mt-1 truncate text-[10px] font-semibold text-brand-700">{file?.name || 'Chưa gán creative'}</p>
                </div>
              </article>
            )
          })}
        </div>
      </Section>

      {(outcome.order.warnings?.length > 0 || outcome.assignments.warnings?.length > 0) && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-900">
          <p className="font-black">Cảnh báo cần theo dõi</p>
          <ul className="mt-2 list-disc space-y-1 pl-4">
            {[...(outcome.order.warnings || []), ...(outcome.assignments.warnings || [])].map((warning, index) => <li key={`${warning}:${index}`}>{warning}</li>)}
          </ul>
        </div>
      )}
    </div>
  )
}

function PerformanceReportState({ outcome }) {
  const delivery = campaignDeliveryState(outcome)
  const active = delivery.live

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-sm" data-testid="autopilot-performance-report">
      <div className={`mx-auto flex h-14 w-14 items-center justify-center rounded-2xl ${active ? 'bg-blue-50 text-brand-600' : 'bg-amber-50 text-amber-700'}`}>
        <BarChart3 className="h-7 w-7" />
      </div>
      <h3 className="mt-4 text-lg font-black text-slate-900">
        {active ? 'Chưa có dữ liệu hiệu suất' : 'Campaign chưa giao quảng cáo'}
      </h3>
      <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-600">
        {active
          ? 'Order đã active nhưng hệ thống chưa nhận đủ impression, click hoặc conversion để tạo báo cáo đáng tin cậy.'
          : `Order ${outcome.orderId || ''} đang ở trạng thái “${delivery.label}”. Hãy kích hoạt order trước; báo cáo chỉ xuất hiện sau khi có dữ liệu phân phối thực.`}
      </p>
      <div className="mx-auto mt-5 max-w-xl rounded-xl border border-blue-100 bg-blue-50/60 px-4 py-3 text-left text-xs leading-5 text-blue-900">
        Advertising Agent không tự tạo số liệu giả trong màn hình này. Báo cáo setup ở tab bên cạnh vẫn dùng toàn bộ artifact thật của Autopilot run.
      </div>
      <a href={`${ADSPILOT_URL}/#/orders`} target="_blank" rel="noreferrer" className="mt-5 inline-flex items-center gap-2 rounded-xl bg-brand-500 px-4 py-2.5 text-xs font-bold text-white hover:bg-brand-600">
        Mở trình quản lý quảng cáo <ExternalLink className="h-3.5 w-3.5" />
      </a>
    </div>
  )
}

export default function AutopilotOutcome({ workspace, taskByKey, fallbackBrief }) {
  const [activeTab, setActiveTab] = useState('result')
  const outcome = useMemo(() => buildCampaignOutcome({ workspace, taskByKey, fallbackBrief }), [workspace, taskByKey, fallbackBrief])

  if (!outcome.orderId) return null

  return (
    <section className="rounded-3xl border border-brand-100 bg-white p-3 shadow-sm sm:p-5" aria-labelledby="autopilot-outcome-title">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-brand-600">Sau khi Autopilot hoàn tất</p>
          <h2 id="autopilot-outcome-title" className="mt-1 text-lg font-black text-slate-900">Kết quả & báo cáo campaign</h2>
        </div>
        <span className="rounded-full bg-green-50 px-3 py-1 text-[10px] font-bold text-green-700">Đã lưu vào workspace</span>
      </div>

      <div className="mb-4 grid grid-cols-3 gap-1 rounded-xl bg-slate-100 p-1" role="tablist" aria-label="Kết quả và báo cáo Autopilot">
        {TABS.map(tab => {
          const Icon = tab.icon
          const selected = activeTab === tab.id
          return (
            <button key={tab.id} type="button" role="tab" aria-selected={selected} onClick={() => setActiveTab(tab.id)}
              className={`flex min-h-10 items-center justify-center gap-1.5 rounded-lg px-2 text-[11px] font-bold transition ${selected ? 'bg-white text-brand-700 shadow-sm' : 'text-slate-500 hover:text-slate-800'}`}>
              <Icon className="h-3.5 w-3.5" /> <span>{tab.label}</span>
            </button>
          )
        })}
      </div>

      <div role="tabpanel">
        {activeTab === 'result' && (
          <SuccessStep
            brief={outcome.brief}
            selectedZoneIds={outcome.selectedZoneIds}
            audienceSize={outcome.audienceSize}
            setup={outcome.setup}
            allZones={outcome.zones}
            recoZones={outcome.zones}
            order={outcome.order}
            forecast={outcome.forecast}
          />
        )}
        {activeTab === 'setup' && <SetupReport outcome={outcome} />}
        {activeTab === 'performance' && <PerformanceReportState outcome={outcome} />}
      </div>
    </section>
  )
}
