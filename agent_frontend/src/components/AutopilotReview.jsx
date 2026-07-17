import { AlertTriangle, CheckCircle2, FileImage, MapPin, Target, Users } from 'lucide-react'

const number = value => new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 0 }).format(Number(value || 0))
const audienceName = item => item?.fullLabel || item?.label || item?.name || item?.code || item?._id || 'Segment'
const zoneName = zone => zone?.name || zone?.label || zone?.id || 'Placement'

const taskValue = task => task?.pending_artifact?.value ?? task?.result ?? {}

function Empty({ children }) {
  return <p className="rounded-xl bg-slate-50 px-3 py-3 text-xs leading-5 text-slate-600">{children}</p>
}

function Stat({ label, value, note }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5">
      <dt className="text-[10px] font-bold uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-1 text-sm font-black text-slate-900">{value}</dd>
      {note && <p className="mt-1 text-[10px] leading-4 text-slate-500">{note}</p>}
    </div>
  )
}

function BriefReview({ brief, value }) {
  const errors = value?.errors || []
  return (
    <div className="space-y-3">
      <p className="text-xs leading-5 text-slate-600">
        Brief đã được xác nhận trước khi chạy. Điểm này chỉ xuất hiện khi bộ kiểm tra phát hiện dữ liệu không hợp lệ hoặc đã hết hạn.
      </p>
      <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Thương hiệu" value={brief?.brand || '—'} />
        <Stat label="Mục tiêu" value={brief?.objective || '—'} />
        <Stat label="Ngân sách" value={`${number(brief?.budget)} triệu đồng`} />
        <Stat label="Thời gian" value={brief?.startDate && brief?.endDate ? `${brief.startDate} → ${brief.endDate}` : '—'} />
      </dl>
      {errors.length > 0 && (
        <ul className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-800">
          {errors.map(error => <li key={error}>• {error}</li>)}
        </ul>
      )}
    </div>
  )
}

function StrategyReview({ value }) {
  const selected = (value.options || []).find(option => option.id === value.selected)
  return (
    <div className="space-y-2">
      <p className="text-xs leading-5 text-slate-600">
        So sánh ba phương án trong bảng <strong>Kịch bản phân bổ theo brief</strong> phía trên. Ở điểm review này, nút chọn phương án được mở khóa.
      </p>
      {selected && (
        <div className="rounded-xl border border-brand-200 bg-brand-50 px-3 py-2.5">
          <p className="text-xs font-black text-brand-800">Đang đề xuất: {selected.label}</p>
          <p className="mt-1 text-[11px] leading-5 text-brand-700">{selected.rationale}</p>
        </div>
      )}
    </div>
  )
}

function AudienceReview({ value }) {
  const attrs = value.attrs || []
  const retrieval = value.retrieval || {}
  const catalog = retrieval.catalog_segments || retrieval.catalog_count || retrieval.total_segments || 0
  const candidates = retrieval.candidates || retrieval.candidate_count || retrieval.retrieval_candidates || 0
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-[11px] font-bold">
        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-700">{catalog ? `${number(catalog)} trong catalog` : 'Toàn bộ catalog hiện hành'}</span>
        <span className="text-slate-400">→</span>
        <span className="rounded-full bg-brand-50 px-2.5 py-1 text-brand-700">{number(candidates)} ứng viên RAG</span>
        <span className="text-slate-400">→</span>
        <span className="rounded-full bg-green-50 px-2.5 py-1 text-green-700">{attrs.length} segment đã chọn</span>
      </div>
      <p className="text-[11px] leading-5 text-slate-500">
        Catalog không bị cắt còn {candidates}. Đây là tập ứng viên liên quan được truy xuất cho riêng brief này sau query rewrite, gộp trùng và bộ lọc an toàn.
      </p>
      {attrs.length ? (
        <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {attrs.map((item, index) => (
            <li key={item._id || item.segmentId || index} className="rounded-xl border border-slate-200 bg-white px-3 py-2.5">
              <p className="text-xs font-bold text-slate-900">{audienceName(item)}</p>
              {(item.reason || item.description) && <p className="mt-1 text-[10px] leading-4 text-slate-500">{item.reason || item.description}</p>}
            </li>
          ))}
        </ul>
      ) : <Empty>Chưa có segment để review.</Empty>}
    </div>
  )
}

function TargetingReview({ value }) {
  const rows = Object.entries(value || {}).filter(([, values]) => Array.isArray(values) ? values.length : values != null)
  return rows.length ? (
    <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
      {rows.map(([dimension, values]) => (
        <div key={dimension} className="rounded-xl border border-slate-200 bg-white px-3 py-2.5">
          <dt className="text-[10px] font-black uppercase tracking-wide text-slate-500">{dimension}</dt>
          <dd className="mt-2 flex flex-wrap gap-1.5">
            {(Array.isArray(values) ? values : [values]).map(item => (
              <span key={String(item)} className="rounded-full bg-brand-50 px-2 py-1 text-[10px] font-bold text-brand-700">{String(item)}</span>
            ))}
          </dd>
        </div>
      ))}
    </dl>
  ) : <Empty>Chưa có targeting catalog để review.</Empty>
}

function PlacementReview({ value, final = false }) {
  const zones = value.candidates || value.zones || []
  return zones.length ? (
    <div className="space-y-3">
      <p className="text-[11px] leading-5 text-slate-500">
        {final
          ? 'Các placement dưới đây đã qua kiểm tra inventory, conflict và độ tương thích với creative.'
          : 'Đây là shortlist inventory trước khi có creative. Kích thước creative sẽ được dùng để lọc lại ở bước Xếp hạng placements.'}
      </p>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {zones.map((zone, index) => (
          <article key={zone.id || index} className="rounded-xl border border-slate-200 bg-white px-3 py-2.5">
            <p className="text-xs font-bold text-slate-900">{zoneName(zone)}</p>
            <p className="mt-1 text-[10px] text-slate-500">{zone.id || '—'} · {zone.channel || zone.siteId || zone.format || zone.size || 'inventory'}</p>
            <p className="mt-1 text-[10px] font-semibold text-brand-700">CPM {number(zone.cpm)} ₫ · reach {number(zone.reach)}</p>
          </article>
        ))}
      </div>
    </div>
  ) : <Empty>Chưa có placement để review.</Empty>
}

function FormatReview({ value }) {
  const formats = value.formats || []
  return formats.length ? (
    <div className="space-y-3">
      <p className="text-[11px] leading-5 text-slate-500">
        Mỗi asset bên dưới có thể phủ nhiều placement cùng kích thước. Sau khi duyệt, Autopilot sẽ mở bước upload hoặc tự tạo đúng các format này.
      </p>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {formats.map((item, index) => (
          <article key={item.format_id || index} className="rounded-xl border border-slate-200 bg-white px-3 py-2.5">
            <p className="text-sm font-black text-slate-900">{item.width} × {item.height}px</p>
            <p className="mt-1 text-[10px] text-slate-500">{item.format_id || 'Format'}</p>
            <p className="mt-1 text-[10px] font-bold text-brand-700">Phủ {(item.zone_ids || []).length} placement</p>
          </article>
        ))}
      </div>
      {(value.unsupported_zone_ids?.length > 0 || value.omitted_by_cost_cap_zone_ids?.length > 0) && (
        <p className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] leading-5 text-amber-800">
          {value.unsupported_zone_ids?.length || 0} placement chưa có format hỗ trợ; {value.omitted_by_cost_cap_zone_ids?.length || 0} placement nằm ngoài giới hạn số asset/chi phí.
        </p>
      )}
    </div>
  ) : <Empty>Chưa có format creative được hỗ trợ.</Empty>
}

function CreativeReview({ value, formatPlan }) {
  const files = value.files || []
  const formats = formatPlan?.formats || []
  const covered = formats.filter(format => files.some(file => (
    Number(file.width) === Number(format.width) && Number(file.height) === Number(format.height)
  )))
  return (
    <div className="space-y-3">
      <div className="grid gap-2 sm:grid-cols-3">
        <Stat label="Creative đã tải" value={`${files.length} file`} />
        <Stat label="Format yêu cầu" value={`${formats.length} format`} />
        <Stat label="Khớp kích thước" value={`${covered.length}/${formats.length || 0}`} note="Backend chỉ tự launch khi pixel khớp chính xác hoặc là skin đã duyệt." />
      </div>
      {formats.length > 0 && (
        <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {formats.map(item => {
            const match = files.find(file => Number(file.width) === Number(item.width) && Number(file.height) === Number(item.height))
            return (
              <li key={item.format_id} className={`rounded-xl border px-3 py-2.5 ${match ? 'border-green-200 bg-green-50' : 'border-amber-200 bg-amber-50'}`}>
                <p className="text-xs font-bold text-slate-900">{item.width} × {item.height}px</p>
                <p className={`mt-1 text-[10px] font-bold ${match ? 'text-green-700' : 'text-amber-800'}`}>{match ? `Đã có: ${match.name}` : 'Cần tải file phù hợp'}</p>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

function GenericReview({ task, value }) {
  if (task.key === 'forecast') {
    return <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
      <Stat label="Reach dự kiến" value={number(value.estimated_reach)} />
      <Stat label="Impression" value={number(value.estimated_impressions)} />
      <Stat label="CPM catalog" value={`${number(value.average_cpm)} ₫`} />
      <Stat label="Tần suất" value={value.frequency || '—'} />
    </dl>
  }
  if (task.key === 'run_order_guard') {
    return <div className={`flex items-start gap-2 rounded-xl border px-3 py-3 text-xs ${value.passed ? 'border-green-200 bg-green-50 text-green-800' : 'border-red-200 bg-red-50 text-red-800'}`}>
      {value.passed ? <CheckCircle2 className="h-4 w-4 shrink-0" /> : <AlertTriangle className="h-4 w-4 shrink-0" />}
      <span>{value.passed ? 'Order draft đã vượt qua toàn bộ kiểm tra an toàn.' : (value.message || 'Order draft chưa vượt qua kiểm tra an toàn.')}</span>
    </div>
  }
  if (task.key === 'assign_creatives') {
    const assignments = value.assignments || {}
    return <Empty>{Object.keys(assignments).length} placement đã được gán creative. Mở “Kế hoạch creative theo placement” để đối chiếu asset và format.</Empty>
  }
  if (task.key === 'analyze_creatives') {
    const files = value.files || []
    return files.length ? <ul className="grid gap-2 sm:grid-cols-2">{files.map((file, index) => (
      <li key={file.analysis_id || file.analysisId || index} className="rounded-xl border border-slate-200 px-3 py-2.5">
        <p className="text-xs font-bold text-slate-900">{file.name || file.url || `Creative ${index + 1}`}</p>
        <p className="mt-1 text-[10px] font-semibold text-brand-700">{file.effective_status || file.status || 'Đã phân tích'}</p>
      </li>
    ))}</ul> : <Empty>{value.message || 'Creative chưa có verdict để review.'}</Empty>
  }
  if (task.key === 'launch_approval' || task.key === 'build_order_draft') {
    const placements = value.selectedZoneIds || value.zoneIds || value.placements || []
    return <Empty>Bản setup cuối gồm {Array.isArray(placements) ? placements.length : Object.keys(placements || {}).length} placement. Kiểm tra audience, targeting, creative, forecast và guard ở các thẻ phía trên trước khi duyệt launch.</Empty>
  }
  return <Empty>{value.message || 'Đầu ra của bước này đã sẵn sàng để duyệt.'}</Empty>
}

export default function AutopilotReview({ task, label, brief, formatPlan }) {
  if (!task) return null
  const value = taskValue(task)
  let content
  let icon = <Target className="h-4 w-4" />

  if (task.key === 'validate_brief') content = <BriefReview brief={brief} value={value} />
  else if (task.key === 'generate_strategy') content = <StrategyReview value={value} />
  else if (task.key === 'retrieve_audience') { content = <AudienceReview value={value} />; icon = <Users className="h-4 w-4" /> }
  else if (task.key === 'derive_targeting') content = <TargetingReview value={value} />
  else if (task.key === 'plan_placement_intent') { content = <PlacementReview value={value} />; icon = <MapPin className="h-4 w-4" /> }
  else if (task.key === 'plan_creative_formats') { content = <FormatReview value={value} />; icon = <FileImage className="h-4 w-4" /> }
  else if (task.key === 'prepare_creatives') { content = <CreativeReview value={value} formatPlan={formatPlan} />; icon = <FileImage className="h-4 w-4" /> }
  else if (task.key === 'rank_placements') { content = <PlacementReview value={value} final />; icon = <MapPin className="h-4 w-4" /> }
  else content = <GenericReview task={task} value={value} />

  return (
    <section id="autopilot-review-artifact" className="scroll-mt-24 rounded-2xl border-2 border-amber-300 bg-white p-4 shadow-sm" aria-labelledby="autopilot-review-title">
      <div className="mb-3 flex items-start gap-2">
        <span className="mt-0.5 rounded-lg bg-amber-100 p-1.5 text-amber-800">{icon}</span>
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.16em] text-amber-700">Nội dung cần review</p>
          <h3 id="autopilot-review-title" className="mt-0.5 text-sm font-black text-slate-900">{label || task.key}</h3>
          <p className="mt-1 text-[11px] leading-5 text-slate-500">Duyệt dữ liệu thực tế bên dưới. “Chỉnh dữ liệu” sẽ giữ nguyên run và chỉ tính lại các bước phụ thuộc.</p>
        </div>
      </div>
      {content}
    </section>
  )
}
