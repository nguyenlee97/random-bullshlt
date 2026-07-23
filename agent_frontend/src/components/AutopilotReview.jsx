import { AlertTriangle, CheckCircle2, FileImage, MapPin, Target, Users } from 'lucide-react'
import { matchPlannedFormat } from '@/lib/creativeCompatibility'
import { placementIdsFromValue } from '@/lib/campaignOutcome'

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

function PlacementReview({ value, final = false, selectedIds, onSelectionChange }) {
  const zones = value.candidates || value.zones || []
  const editable = !final && typeof onSelectionChange === 'function'
  const activeIds = new Set(selectedIds || value.candidate_zone_ids || zones.map(zone => zone.id))
  const toggle = zoneId => {
    if (!editable || !zoneId) return
    const next = activeIds.has(zoneId)
      ? [...activeIds].filter(id => id !== zoneId)
      : [...activeIds, zoneId]
    if (next.length) onSelectionChange(next)
  }
  return zones.length ? (
    <div className="space-y-3">
      <p className="text-[11px] leading-5 text-slate-500">
        {final
          ? 'Các placement dưới đây đã qua kiểm tra inventory, conflict và độ tương thích với creative.'
          : editable
            ? 'Agent chọn sẵn 6 placement xếp hạng cao nhất trong shortlist 12 vị trí. Bạn có thể chọn thêm hoặc bỏ bớt trực tiếp bên dưới; cần giữ lại ít nhất một placement.'
            : 'Đây là shortlist inventory trước khi có creative. Kích thước creative sẽ được dùng để lọc lại ở bước Xếp hạng placements.'}
      </p>
      {editable && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-brand-200 bg-brand-50 px-3 py-2">
          <p className="text-[11px] font-bold text-brand-800">Đã chọn {activeIds.size}/{zones.length} placement · mặc định top 6</p>
          <p className="text-[10px] text-brand-700">Thay đổi chỉ được lưu khi bấm “Duyệt & tiếp tục”.</p>
        </div>
      )}
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {zones.map((zone, index) => (
          <button
            type="button"
            key={zone.id || index}
            data-demo="autopilot-placement-option"
            disabled={!editable}
            aria-pressed={activeIds.has(zone.id)}
            onClick={() => toggle(zone.id)}
            className={`rounded-xl border px-3 py-2.5 text-left transition ${activeIds.has(zone.id)
              ? 'border-brand-300 bg-brand-50/60 ring-1 ring-brand-100'
              : 'border-slate-200 bg-white opacity-55'} ${editable ? 'cursor-pointer hover:border-brand-400' : 'cursor-default disabled:opacity-100'}`}
          >
            <div className="flex items-start gap-2">
              {editable && (
                <span className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border text-[10px] font-black ${activeIds.has(zone.id) ? 'border-brand-500 bg-brand-500 text-white' : 'border-slate-300 bg-white text-transparent'}`}>✓</span>
              )}
              <div className="min-w-0">
                <p className="text-xs font-bold text-slate-900">{zoneName(zone)}</p>
                <p className="mt-1 text-[10px] text-slate-500">{zone.id || '—'} · {zone.channel || zone.siteId || zone.format || zone.size || 'inventory'}</p>
                <p className="mt-1 text-[10px] font-semibold text-brand-700">CPM {number(zone.cpm)} ₫ · reach {number(zone.reach)}</p>
              </div>
            </div>
          </button>
        ))}
      </div>
      {zones.some(zone => zone.metricSource === 'synthetic_inventory_v2') && (
        <p className="rounded-xl bg-slate-50 px-3 py-2 text-[10px] leading-4 text-slate-500">
          CPM và reach là dữ liệu mô phỏng có phân tầng theo lượng truy cập channel, loại trang và độ nổi bật của vị trí; không phải số delivery thực tế.
        </p>
      )}
    </div>
  ) : <Empty>Chưa có placement để review.</Empty>
}

function PlacementRecoveryReview({ value }) {
  const recovery = value.recovery || {}
  const formats = recovery.target_formats || []
  const inventoryBlocked = recovery.kind === 'inventory_unavailable'
  return (
    <div className="space-y-3">
      <div className={`rounded-xl border px-3 py-3 ${inventoryBlocked ? 'border-amber-200 bg-amber-50' : 'border-brand-200 bg-brand-50'}`}>
        <p className="text-xs font-black text-slate-900">
          {inventoryBlocked
            ? 'Shortlist placement cần được cập nhật'
            : 'Có thể xử lý ngay mà không phải hủy run'}
        </p>
        <p className="mt-1 text-[11px] leading-5 text-slate-700">
          {inventoryBlocked
            ? 'Creative không phải blocker chính: inventory trong shortlist không còn trống. Hãy cập nhật placement hoặc thời gian chạy rồi kiểm tra lại.'
            : `Creative hiện có chưa đúng tỷ lệ của placement đang trống. Hệ thống tìm thấy ${recovery.existing_image_count || 0} ảnh có thể dùng làm nguồn crop/scale, hoặc có thể chuẩn bị asset mới đúng format.`}
        </p>
      </div>
      {!inventoryBlocked && formats.length > 0 && (
        <div>
          <p className="mb-2 text-[10px] font-black uppercase tracking-[0.14em] text-slate-500">
            Format cần bổ sung
          </p>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {formats.map((item, index) => (
              <article key={item.format_id || index} className="rounded-xl border border-amber-200 bg-white px-3 py-2.5">
                <p className="text-sm font-black text-slate-900">{item.width} × {item.height}px</p>
                <p className="mt-1 truncate text-[10px] text-slate-500">{item.format_id || 'Format'}</p>
                <p className="mt-1 text-[10px] font-bold text-amber-800">
                  Phủ {(item.zone_ids || []).length || 1} placement
                </p>
              </article>
            ))}
          </div>
          <p className="mt-2 text-[10px] leading-4 text-slate-500">
            Crop giữ đúng tỷ lệ và cho phép chọn vùng ảnh. Scale giữ toàn bộ ảnh nhưng có thể làm biến dạng nội dung; luôn xem lại kết quả phân tích trước khi tiếp tục.
          </p>
        </div>
      )}
    </div>
  )
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
  const covered = formats.filter(format => files.some(file => matchPlannedFormat(file, format).matched))
  return (
    <div className="space-y-3">
      <div className="grid gap-2 sm:grid-cols-3">
        <Stat label="Creative đã tải" value={`${files.length} file`} />
        <Stat label="Format yêu cầu" value={`${formats.length} format`} />
        <Stat label="Format tương thích" value={`${covered.length}/${formats.length || 0}`} note="Ưu tiên đúng pixel; chấp nhận cùng tỷ lệ với độ lệch dưới 15%. Skin cần được gắn đúng loại." />
      </div>
      {formats.length > 0 && (
        <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {formats.map(item => {
            const matchedFile = files.find(file => matchPlannedFormat(file, item).matched)
            const match = matchedFile ? matchPlannedFormat(matchedFile, item) : null
            return (
              <li key={item.format_id} className={`rounded-xl border px-3 py-2.5 ${match ? 'border-green-200 bg-green-50' : 'border-amber-200 bg-amber-50'}`}>
                <p className="text-xs font-bold text-slate-900">{item.width} × {item.height}px</p>
                <p className={`mt-1 text-[10px] font-bold ${match ? 'text-green-700' : 'text-amber-800'}`}>{match ? `Đã có: ${matchedFile.name} · ${match.label}` : 'Cần tải file đúng tỷ lệ/format'}</p>
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
    const placements = placementIdsFromValue(value)
    return <Empty>Bản setup cuối gồm {placements.length} placement. Kiểm tra audience, targeting, creative, forecast và guard ở các thẻ phía trên trước khi duyệt launch.</Empty>
  }
  return <Empty>{value.message || 'Đầu ra của bước này đã sẵn sàng để duyệt.'}</Empty>
}

export default function AutopilotReview({ task, label, brief, formatPlan, selectedPlacementIds, onPlacementSelectionChange }) {
  if (!task) return null
  const value = taskValue(task)
  let content
  let icon = <Target className="h-4 w-4" />

  if (task.key === 'validate_brief') content = <BriefReview brief={brief} value={value} />
  else if (task.key === 'generate_strategy') content = <StrategyReview value={value} />
  else if (task.key === 'retrieve_audience') { content = <AudienceReview value={value} />; icon = <Users className="h-4 w-4" /> }
  else if (task.key === 'derive_targeting') content = <TargetingReview value={value} />
  else if (task.key === 'plan_placement_intent') {
    content = <PlacementReview value={value} selectedIds={selectedPlacementIds} onSelectionChange={onPlacementSelectionChange} />
    icon = <MapPin className="h-4 w-4" />
  }
  else if (task.key === 'plan_creative_formats') { content = <FormatReview value={value} />; icon = <FileImage className="h-4 w-4" /> }
  else if (task.key === 'prepare_creatives') { content = <CreativeReview value={value} formatPlan={formatPlan} />; icon = <FileImage className="h-4 w-4" /> }
  else if (task.key === 'rank_placements') {
    content = value.recovery
      ? <PlacementRecoveryReview value={value} />
      : <PlacementReview value={value} final />
    icon = <MapPin className="h-4 w-4" />
  }
  else content = <GenericReview task={task} value={value} />

  return (
    <section
      id="autopilot-review-artifact"
      data-demo="autopilot-review-artifact"
      data-autopilot-task={task.key}
      className="scroll-mt-24 rounded-2xl border-2 border-amber-300 bg-white p-4 shadow-sm"
      aria-labelledby="autopilot-review-title"
    >
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
