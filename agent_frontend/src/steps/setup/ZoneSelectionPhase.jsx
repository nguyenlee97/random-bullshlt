import { useState } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { ALL_ZONES, getRecommendedZones, calcImpressions } from '@/data/zones'
import { Sparkles, ChevronDown, ChevronUp, Check, RefreshCw, ArrowRight, Eye, BarChart2, MousePointerClick, DollarSign, AlertTriangle } from 'lucide-react'
import { fmtVnd, fmtImp } from './setupUtils'

function Stat({ icon: Icon, value, color }) {
  return (
    <span className="flex items-center gap-0.5">
      <Icon className={cn('w-3 h-3', color)} />
      <span className={cn('text-[10px] font-bold', color)}>{value}</span>
    </span>
  )
}

function ZoneCard({ zone, selected, onToggle, isReco, budgetPerZoneM }) {
  const estImp = budgetPerZoneM > 0 ? calcImpressions(zone, budgetPerZoneM) : null
  const conflict = zone.conflict || null

  return (
    <button
      onClick={() => onToggle(zone.id)}
      className={cn(
        'w-full flex flex-col gap-2 p-3 rounded-xl border text-left transition-all duration-150',
        conflict && selected && 'border-red-400 bg-red-50 shadow-sm',
        conflict && !selected && 'border-red-200 bg-red-50/60 hover:border-red-300',
        !conflict && selected && 'border-brand-400 bg-brand-50 shadow-sm',
        !conflict && !selected && isReco && 'border-amber-300 bg-gradient-to-br from-amber-50 to-orange-50 hover:border-amber-400',
        !conflict && !selected && !isReco && 'border-border bg-white hover:border-brand-300 hover:bg-slate-50',
      )}
      id={`zone-${zone.id}`}
    >
      <div className="flex items-start gap-2">
        <div className={cn(
          'w-4 h-4 rounded flex items-center justify-center flex-shrink-0 mt-0.5 border transition-all',
          conflict && selected ? 'bg-red-500 border-red-500' : '',
          !conflict && selected ? 'bg-brand-500 border-brand-500' : '',
          !selected ? 'border-muted-foreground/40' : '',
        )}>
          {selected && <Check className="w-2.5 h-2.5 text-white" strokeWidth={3} />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-xs font-bold">{zone.name}</span>
            {isReco && !conflict && (
              <Badge className="text-[9px] h-4 px-1 bg-amber-100 text-amber-700 border-amber-300">⭐ Gợi ý</Badge>
            )}
            {conflict && (
              <Badge className="text-[9px] h-4 px-1 bg-red-100 text-red-700 border-red-300 gap-0.5">
                <AlertTriangle className="w-2.5 h-2.5" />
                Đã đặt trước
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-1 mt-0.5 flex-wrap">
            {[zone.platform, zone.format, zone.size].map(t => (
              <Badge key={t} variant="muted" className="text-[10px] h-4 px-1.5">{t}</Badge>
            ))}
          </div>
        </div>
      </div>

      <div className="flex flex-wrap gap-x-3 gap-y-1 pl-6">
        <Stat icon={Eye} value={`${zone.reach}M`} color="text-blue-600" />
        <Stat icon={BarChart2} value={`VI ${zone.vi}%`} color="text-violet-600" />
        <Stat icon={MousePointerClick} value={`CTR ${zone.ctr}%`} color="text-green-600" />
        <Stat icon={DollarSign} value={`CPM ${fmtVnd(zone.cpm)}đ`} color="text-amber-600" />
      </div>

      {/* Conflict warning */}
      {conflict && (
        <div className="pl-6 flex items-start gap-1.5">
          <AlertTriangle className="w-3 h-3 text-red-500 flex-shrink-0 mt-0.5" />
          <p className="text-[10px] text-red-600 leading-tight">
            Zone này đã được đặt bởi chiến dịch{' '}
            <span className="font-bold">&ldquo;{conflict.campaignName}&rdquo;</span>{' '}
            trong khoảng thời gian {conflict.startDate} → {conflict.endDate}.
            Chọn zone này có thể gây xung đột khi tạo chiến dịch.
          </p>
        </div>
      )}

      {isReco && !conflict && zone.reason && (
        <p className="text-[10px] text-amber-700 italic pl-6 leading-tight">{zone.reason}</p>
      )}
      {estImp && selected && (
        <p className="text-[10px] font-semibold text-brand-600 pl-6">≈ {fmtImp(estImp)} hiển thị ước tính</p>
      )}
    </button>
  )
}

export default function ZoneSelectionPhase({ data, onChange, brief, allZones }) {
  const [expanded, setExpanded] = useState(false)

  const selectedIds = data.selectedZoneIds || []
  const recoZones = data.recoZones || []
  const totalBudget = brief?.budget || 0
  const budgetPerZone = selectedIds.length > 0 ? totalBudget / selectedIds.length : 0

  const recoIds = new Set(recoZones.map(z => z.id))
  // Use real API zones for the full list; fall back to static ALL_ZONES
  const catalog = allZones?.length ? allZones : ALL_ZONES
  const otherZones = catalog.filter(z => !recoIds.has(z.id))

  const toggleZone = (id) => {
    const next = selectedIds.includes(id)
      ? selectedIds.filter(x => x !== id)
      : [...selectedIds, id]
    onChange({ ...data, selectedZoneIds: next, created: false })
  }

  const handleReRecommend = () => {
    // Reset initialized so SetupStep re-fetches from backend
    onChange({ ...data, initialized: false, recoZones: [], allZones: [], selectedZoneIds: [], created: false })
  }

  return (
    <div className="space-y-3">
      {/* Budget summary */}
      <Card className="border-brand-200 bg-brand-50">
        <CardContent className="py-3 flex items-center gap-4">
          <div className="flex-1">
            <p className="text-xs text-muted-foreground">Tổng ngân sách</p>
            <p className="text-xl font-black text-brand-700">{totalBudget}M VND</p>
          </div>
          <div className="text-center px-4 border-x border-brand-200">
            <p className="text-xs text-muted-foreground">Zones chọn</p>
            <p className="text-xl font-black text-brand-700">{selectedIds.length}</p>
          </div>
          <div className="text-right">
            <p className="text-xs text-muted-foreground">Mỗi zone</p>
            <p className="text-xl font-black text-brand-700">{budgetPerZone.toFixed(1)}M</p>
          </div>
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          AI gợi ý {recoZones.length} zones phù hợp
        </p>
        <Button variant="outline" size="sm" onClick={handleReRecommend} className="gap-1.5 text-xs h-8">
          <RefreshCw className="w-3 h-3" /> Tư vấn lại
        </Button>
      </div>

      {/* Recommended zones */}
      <div className="rounded-xl border border-amber-200 bg-gradient-to-br from-amber-50/80 to-orange-50/60 overflow-hidden">
        <div className="flex items-center gap-2 px-3 py-2 border-b border-amber-200 bg-amber-100/60">
          <Sparkles className="w-4 h-4 text-amber-600" />
          <span className="text-xs font-bold text-amber-700">Gợi ý theo brief · {brief?.objective}</span>
        </div>
        <div className="flex flex-col gap-2 p-2">
          {recoZones.map(zone => (
            <ZoneCard
              key={zone.id}
              zone={zone}
              selected={selectedIds.includes(zone.id)}
              onToggle={toggleZone}
              isReco
              budgetPerZoneM={budgetPerZone}
            />
          ))}
        </div>
      </div>

      {/* Expand full list */}
      <Button variant="outline" size="sm" onClick={() => setExpanded(e => !e)} className="w-full gap-2 text-xs h-9">
        {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        {expanded ? 'Thu gọn' : `Xem thêm ${otherZones.length} zones khác`}
      </Button>

      {expanded && (
        <div className="flex flex-col gap-2">
          {otherZones.map(zone => (
            <ZoneCard
              key={zone.id}
              zone={zone}
              selected={selectedIds.includes(zone.id)}
              onToggle={toggleZone}
              isReco={false}
              budgetPerZoneM={budgetPerZone}
            />
          ))}
        </div>
      )}

      {selectedIds.length > 0 && (
        <Button
          onClick={() => onChange({ ...data, phase: 'assign' })}
          className="w-full gap-2"
          id="confirm-zones-btn"
        >
          <ArrowRight className="w-4 h-4" />
          Tiếp tục gắn creative vào {selectedIds.length} zones
        </Button>
      )}
    </div>
  )
}
