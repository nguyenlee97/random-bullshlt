import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { Check, FileText, PenLine } from 'lucide-react'

const OBJECTIVES = [
  { value: 'awareness',     label: 'Awareness — Tăng nhận biết' },
  { value: 'consideration', label: 'Consideration — Tăng quan tâm' },
  { value: 'conversion',    label: 'Conversion — Chuyển đổi' },
  { value: 'retention',     label: 'Retention — Giữ chân' },
]

const VALID_OBJECTIVES = OBJECTIVES.map(o => o.value)

// Predefined KPI chips (quick-select)
const KPI_CHIPS = ['Reach', 'VTR', 'CTR', 'Impressions', 'CPM', 'CPA', 'ROAS', 'VI%', 'Engagement', 'CVR', 'Frequency', 'Return Visit']

function KpiChips({ value, onChange }) {
  // Check if current value contains custom text (not just comma-joined chips)
  const selected = value ? value.split(',').map(s => s.trim()).filter(Boolean) : []
  const knownSelected = selected.filter(k => KPI_CHIPS.includes(k))
  const customText = selected.filter(k => !KPI_CHIPS.includes(k)).join(', ')
  const hasCustom = selected.some(k => !KPI_CHIPS.includes(k))

  // The raw string may be a free-text from agent (e.g. "Reach ~5M, VTR > 25%, CTR > 1.2%")
  // If none of the selected tokens match KPI_CHIPS, treat the whole value as custom text
  const isFullyCustom = value && knownSelected.length === 0

  const toggle = (kpi) => {
    if (isFullyCustom) {
      // Replace custom text with chip selection
      onChange(kpi)
      return
    }
    const next = selected.includes(kpi) ? selected.filter(k => k !== kpi) : [...selected, kpi]
    onChange(next.join(', '))
  }

  const handleCustomChange = (e) => {
    const custom = e.target.value
    if (!custom.trim()) {
      onChange(knownSelected.join(', '))
    } else {
      // Merge chips + custom
      const merged = [...knownSelected, custom].join(', ')
      onChange(merged)
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        {KPI_CHIPS.map(k => {
          const sel = !isFullyCustom && selected.includes(k)
          return (
            <button key={k} type="button" onClick={() => toggle(k)}
              className={cn('flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold border transition-all',
                sel ? 'bg-brand-500 border-brand-500 text-white' : 'bg-white border-border text-muted-foreground hover:border-brand-400 hover:bg-brand-50')}>
              {sel && <Check className="w-3 h-3" strokeWidth={3} />}{k}
            </button>
          )
        })}
      </div>

      {/* Custom / free-text KPI from agent */}
      <div className="relative">
        <PenLine className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-muted-foreground" />
        <Input
          id="brief-kpi-custom"
          className="pl-7 text-sm"
          placeholder="Hoặc nhập KPI cụ thể... (VD: Reach ~5M, VTR > 25%)"
          value={isFullyCustom ? value : customText}
          onChange={handleCustomChange}
        />
        {isFullyCustom && (
          <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] bg-brand-100 text-brand-700 font-semibold px-1.5 py-0.5 rounded">
            Cụ thể
          </span>
        )}
      </div>

      {!value && <p className="text-xs text-amber-600">Chọn ít nhất 1 KPI hoặc nhập KPI cụ thể</p>}
      {value && !isFullyCustom && <p className="text-xs text-brand-600 font-medium">Đã chọn: {selected.join(' · ')}</p>}
    </div>
  )
}

export default function BriefStep({ data, onChange, isDone }) {
  const update = (key, val) => onChange(prev => ({ ...prev, [key]: val }))

  // Auto-compute duration from dates
  const computeDuration = (start, end) => {
    if (!start || !end) return ''
    const diff = (new Date(end) - new Date(start)) / (1000 * 60 * 60 * 24 * 7)
    return diff > 0 ? `${Math.round(diff)} tuần` : ''
  }

  // Objective may be non-standard (e.g. agent saved a compound string)
  const objectiveLabel = OBJECTIVES.find(o => o.value === data.objective)?.label
  const isCustomObjective = data.objective && !VALID_OBJECTIVES.includes(data.objective)

  if (isDone) {
    return (
      <Card className="border-brand-200 bg-brand-50">
        <CardContent className="py-4">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-5 h-5 rounded-full bg-brand-500 flex items-center justify-center">
              <Check className="w-3 h-3 text-white" />
            </div>
            <h4 className="text-sm font-semibold text-brand-700">Brief đã được xác nhận</h4>
          </div>
          <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs">
            {[
              ['Thương hiệu', data.brand],
              ['Mục tiêu', objectiveLabel || data.objective],
              ['KPI', data.kpi],
              ['Ngân sách', `${data.budget} triệu`],
              ['Thời gian', data.startDate && data.endDate ? `${data.startDate} → ${data.endDate}` : data.startDate || '—'],
              ['Ghi chú', data.notes],
            ].map(([k, v]) => (
              <div key={k}><span className="text-muted-foreground">{k}: </span><span className="font-semibold">{v || '—'}</span></div>
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      <div>
        <Label className="mb-1.5 block">Thương hiệu</Label>
        <Input id="brief-brand" value={data.brand} onChange={e => update('brand', e.target.value)} placeholder="Tên thương hiệu..." />
      </div>

      <div>
        <Label className="mb-1.5 block">Mục tiêu chiến dịch</Label>
        <Select value={VALID_OBJECTIVES.includes(data.objective) ? data.objective : ''} onValueChange={val => update('objective', val)}>
          <SelectTrigger id="brief-objective"><SelectValue placeholder="Chọn mục tiêu..." /></SelectTrigger>
          <SelectContent>
            {OBJECTIVES.map(o => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
          </SelectContent>
        </Select>
        {isCustomObjective && (
          <p className="mt-1 text-xs text-brand-600 flex items-center gap-1">
            <span className="bg-brand-100 text-brand-700 font-semibold px-1.5 py-0.5 rounded text-[10px]">Cụ thể</span>
            {data.objective}
          </p>
        )}
      </div>

      <div>
        <Label className="mb-2 block">KPI mong muốn</Label>
        <KpiChips value={data.kpi} onChange={val => update('kpi', val)} />
      </div>

      <div>
        <Label className="mb-1.5 block">Ngân sách (triệu đồng)</Label>
        <Input id="brief-budget" type="number" value={data.budget} onChange={e => update('budget', +e.target.value || 0)} min={0} />
      </div>

      {/* Date range replaces "duration weeks" */}
      <div>
        <Label className="mb-1.5 block">
          Thời gian chạy chiến dịch
          {data.startDate && data.endDate && (
            <span className="ml-2 text-brand-600 font-semibold text-xs">
              ({computeDuration(data.startDate, data.endDate)})
            </span>
          )}
        </Label>
        <p className="text-xs text-muted-foreground mb-2">
          Vui lòng cho biết thời gian chạy cụ thể — bắt đầu từ ngày nào đến ngày nào?
        </p>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label className="mb-1 block text-xs text-muted-foreground">Từ ngày</Label>
            <Input id="brief-start-date" type="date" value={data.startDate || ''} onChange={e => update('startDate', e.target.value)} />
          </div>
          <div>
            <Label className="mb-1 block text-xs text-muted-foreground">Đến ngày</Label>
            <Input id="brief-end-date" type="date" value={data.endDate || ''} onChange={e => update('endDate', e.target.value)}
              min={data.startDate || ''} />
          </div>
        </div>
      </div>

      <div>
        <Label className="mb-1.5 block">Yêu cầu / Brief khách hàng</Label>
        <p className="text-xs text-muted-foreground mb-1.5">
          Mô tả đối tượng mục tiêu, khu vực, sở thích, hành vi — agent dùng để đề xuất DMP segments.
        </p>
        <Textarea id="brief-notes" value={data.notes} onChange={e => update('notes', e.target.value)}
          placeholder="VD: Audience: Nam 18-28, gamer&#10;Geo: 65% HCM, HN, Đà Nẵng&#10;Interest: esports, energy drinks" rows={4} />
      </div>

      <Card className="border-blue-100 bg-blue-50">
        <CardContent className="py-3 flex items-start gap-2">
          <FileText className="w-4 h-4 text-blue-500 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-blue-700">
            Điền đầy đủ brief — agent dùng thông tin này để đề xuất audience và ad zones phù hợp.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
