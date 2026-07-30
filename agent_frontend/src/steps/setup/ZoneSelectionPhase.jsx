import { useMemo, useState } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { matchesCatalogSearch } from '@/lib/catalogSearch'
import { ALL_ZONES, getRecommendedZones, calcImpressions } from '@/data/zones'
import { Sparkles, ChevronDown, ChevronUp, Check, RefreshCw, ArrowRight, Eye, BarChart2, MousePointerClick, DollarSign, AlertTriangle, ExternalLink, Search } from 'lucide-react'
import { fmtVnd, fmtImp } from './setupUtils'

function Stat({ icon: Icon, value, color }) {
  return (
    <span className="flex items-center gap-0.5">
      <Icon className={cn('w-3 h-3', color)} />
      <span className={cn('text-[10px] font-bold', color)}>{value}</span>
    </span>
  )
}

function ZoneCard({ zone, selected, onToggle, isReco, isRelated = false, budgetPerZoneM }) {
  const estImp = budgetPerZoneM > 0 ? calcImpressions(zone, budgetPerZoneM) : null
  const conflict = zone.conflict || null
  const contextEvidence = [
    ...(zone.topic_relevance?.matched_keywords || []),
    ...(zone.topic_relevance?.matched_segments || []),
    ...(zone.topic_relevance?.matched_subcategories || []),
    ...(zone.topic_relevance?.matched_categories || []),
  ].filter((value, index, values) => value && values.indexOf(value) === index).slice(0, 3)
  const isContextRecommendation = (
    zone.recommendation_basis?.mode === 'audience_context'
    && zone.recommendation_basis?.context_match
  )
  const isSemanticRecommendation = (
    isContextRecommendation
    && zone.recommendation_basis?.semantic_match
  )
  const recommendationScore = (
    zone.recommendation_relevance
    ?? zone.topic_relevance?.score
    ?? 0
  )

  return (
    <button
      onClick={() => onToggle(zone.id)}
      className={cn(
        'w-full flex flex-col gap-2 p-3 rounded-xl border text-left transition-all duration-150',
        conflict && selected && 'border-red-400 bg-red-50 shadow-sm',
        conflict && !selected && 'border-red-200 bg-red-50/60 hover:border-red-300',
        !conflict && selected && 'border-brand-400 bg-brand-50 shadow-sm',
        !conflict && !selected && isReco && 'border-amber-300 bg-gradient-to-br from-amber-50 to-orange-50 hover:border-amber-400',
        !conflict && !selected && isRelated && 'border-sky-300 bg-sky-50/60 hover:border-sky-400',
        !conflict && !selected && !isReco && !isRelated && 'border-border bg-white hover:border-brand-300 hover:bg-slate-50',
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
            <span className="text-xs font-bold">
              {zone.name || zone.id.replace(/_/g, ' ')}
            </span>
            {isReco && !conflict && (
              <Badge className="text-[9px] h-4 px-1 bg-amber-100 text-amber-700 border-amber-300">⭐ Gợi ý</Badge>
            )}
            {isRelated && !conflict && (
              <Badge className="text-[9px] h-4 px-1 bg-sky-100 text-sky-700 border-sky-300">↗ Liên quan</Badge>
            )}
            {conflict && (
              <Badge className="text-[9px] h-4 px-1 bg-red-100 text-red-700 border-red-300 gap-0.5">
                <AlertTriangle className="w-2.5 h-2.5" />
                Đã đặt trước
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-1 mt-0.5 flex-wrap">
            {[zone.publisher || zone.platform || zone.channel || zone.id.split('_')[0], zone.placementFamily || zone.format, zone.size].filter(Boolean).map(t => (
              <Badge key={t} variant="muted" className="text-[10px] h-4 px-1.5">{t}</Badge>
            ))}
            {zone.topicId && <Badge className="text-[9px] h-4 px-1.5 bg-sky-50 text-sky-700 border-sky-200">{TOPIC_LABELS[zone.topicId] || zone.topicId.replaceAll('_', ' ')}</Badge>}
            {zone.comparisonGroupId && <Badge className="text-[9px] h-4 px-1.5 bg-violet-50 text-violet-700 border-violet-200">So sánh publisher</Badge>}
          </div>
        </div>
      </div>

      <div className="flex flex-wrap gap-x-3 gap-y-1 pl-6">
        <Stat icon={Eye} value={fmtImp(zone.reach || 0)} color="text-blue-600" />
        <Stat icon={BarChart2} value={`VI ${zone.vi}%`} color="text-violet-600" />
        <Stat icon={MousePointerClick} value={`CTR ${zone.ctr}%`} color="text-green-600" />
        <Stat icon={DollarSign} value={`CPM ${fmtVnd(zone.cpm)}đ`} color="text-amber-600" />
      </div>

      {/* Conflict warning */}
      {conflict && (
        <div className="pl-6 flex items-start gap-1.5">
          <AlertTriangle className="w-3 h-3 text-red-500 flex-shrink-0 mt-0.5" />
          <p className="text-[10px] text-red-600 leading-tight">
            Zone này đã được đặt bởi một chiến dịch khác trong khoảng thời gian{' '}
            {conflict.startDate} → {conflict.endDate}.
            Chọn zone này có thể gây xung đột khi tạo chiến dịch.
          </p>
        </div>
      )}

      {(isReco || isRelated) && !conflict && zone.reason && (
        <p className={cn('text-[10px] italic pl-6 leading-tight', isRelated ? 'text-sky-700' : 'text-amber-700')}>{zone.reason}</p>
      )}
      {(isReco || isRelated) && !conflict && (
        <div className={cn(
          'ml-6 rounded-md px-2 py-1.5 text-[10px] leading-tight',
          isContextRecommendation
            ? 'bg-sky-100/80 text-sky-800'
            : 'bg-slate-100 text-slate-600',
        )}>
          <span className="font-bold">
            {isSemanticRecommendation
              ? 'RAG semantic khớp brief/audience'
              : isContextRecommendation
                ? 'Khớp nội dung brief/audience'
                : 'Xếp hạng theo hiệu suất dự phòng'}
          </span>
          {isContextRecommendation && (
            <>
              {' · '}{TOPIC_LABELS[zone.topicId] || zone.topicId?.replaceAll('_', ' ')}
              {' · '}{Math.round(recommendationScore * 100)}%
              {isSemanticRecommendation && (zone.recommendation_basis?.topic_rerank_rank || zone.recommendation_basis?.retrieval_rank)
                ? ` · RAG #${zone.recommendation_basis.topic_rerank_rank || zone.recommendation_basis.retrieval_rank}`
                : ''}
              {contextEvidence.length ? ` · ${contextEvidence.join(', ')}` : ''}
            </>
          )}
        </div>
      )}
      {estImp && selected && (
        <p className="text-[10px] font-semibold text-brand-600 pl-6">≈ {fmtImp(estImp)} hiển thị ước tính</p>
      )}
      {zone.siteUrl && (
        <span
          role="link"
          tabIndex={0}
          onClick={(event) => {
            event.stopPropagation()
            window.open(zone.siteUrl, '_blank', 'noopener,noreferrer')
          }}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.stopPropagation()
              window.open(zone.siteUrl, '_blank', 'noopener,noreferrer')
            }
          }}
          className="ml-6 inline-flex w-fit items-center gap-1 text-[10px] font-bold text-brand-600 hover:text-brand-800"
        >
          <ExternalLink className="w-3 h-3" /> Xem ad placement
        </span>
      )}
    </button>
  )
}

const TOPIC_LABELS = {
  general: 'Tổng hợp (Trang chủ)',
  business_finance: 'Kinh doanh & Tài chính',
  health_wellness: 'Sức khỏe & Wellness',
  sports_outdoors: 'Thể thao & Ngoài trời',
  technology_science: 'Công nghệ & Khoa học',
  entertainment_culture: 'Giải trí & Văn hóa',
  lifestyle_food_shopping: 'Lifestyle, Ẩm thực & Mua sắm',
  family_parenting: 'Gia đình & Nuôi dạy con',
  education_careers: 'Giáo dục & Nghề nghiệp',
  travel_hospitality: 'Du lịch & Lưu trú',
  automotive_mobility: 'Ô tô, Xe máy & Di chuyển',
  home_property_architecture: 'Nhà ở, BĐS & Kiến trúc',
  society_news_law: 'Xã hội, Thời sự & Pháp luật',
  marketing_digital_business: 'Marketing & Kinh doanh số',
  fitness_active_living: 'Fitness & Sống khỏe',
  soccer_fandom: 'Bóng đá & Người hâm mộ',
  gaming_esports: 'Game & Esports',
  movies_tv_streaming: 'Phim, Truyền hình & Streaming',
  music_live_events: 'Âm nhạc & Sự kiện',
  books_reading: 'Sách & Văn hóa đọc',
  arts_crafts_photography: 'Nghệ thuật, Sáng tạo & Nhiếp ảnh',
  food_dining: 'Ẩm thực, Nấu ăn & Nhà hàng',
  fashion_beauty: 'Thời trang & Làm đẹp',
  shopping_ecommerce: 'Mua sắm & Thương mại điện tử',
  home_garden_diy: 'Nhà, Vườn & DIY',
  pets_animals: 'Thú cưng & Động vật',
  legacy_other: 'Trang chủ & inventory hiện có',
}

export default function ZoneSelectionPhase({ data, onChange, brief, allZones }) {
  const [expanded, setExpanded] = useState(false)
  const [query, setQuery] = useState('')
  const [publisher, setPublisher] = useState('all')
  const [topicFilter, setTopicFilter] = useState('all')
  const [expandedTopics, setExpandedTopics] = useState(() => new Set())

  const selectedIds = data.selectedZoneIds || []
  const recoZones = data.recoZones || []
  const relatedZones = data.relatedZones || []
  const totalBudget = brief?.budget || 0
  const budgetPerZone = selectedIds.length > 0 ? totalBudget / selectedIds.length : 0

  const recoIds = new Set(recoZones.map(z => z.id))
  const relatedIds = new Set(relatedZones.map(z => z.id))
  // Use real API zones for the full list; fall back to static ALL_ZONES
  const catalog = allZones?.length ? allZones : ALL_ZONES
  const publisherOptions = useMemo(() => (
    [...new Set(catalog
      .map((zone) => zone.publisher || zone.platform || zone.siteId)
      .filter(Boolean))]
      .sort((left, right) => left.localeCompare(right, 'vi'))
  ), [catalog])
  const topicOptions = useMemo(() => (
    [...new Set(catalog.map(zone => zone.topicId || 'legacy_other'))]
      .sort((left, right) => (
        (TOPIC_LABELS[left] || left).localeCompare(TOPIC_LABELS[right] || right, 'vi')
      ))
  ), [catalog])
  const otherZones = catalog.filter(z => !recoIds.has(z.id) && !relatedIds.has(z.id))
  const groupedZones = useMemo(() => {
    const filtered = otherZones.filter((zone) => {
      if (publisher !== 'all' && (zone.publisher || zone.platform || zone.siteId) !== publisher) return false
      if (topicFilter !== 'all' && (zone.topicId || 'legacy_other') !== topicFilter) return false
      return matchesCatalogSearch([
        zone.id, zone.name, zone.topicId, TOPIC_LABELS[zone.topicId],
        zone.placementFamily, zone.publisher, zone.platform, zone.channel,
        zone.size, zone.format, zone.placement, zone.pageType,
        zone.audienceContext, zone.audience_context,
      ], query)
    })
    return Object.entries(filtered.reduce((groups, zone) => {
      const key = zone.topicId || 'legacy_other'
      groups[key] ||= []
      groups[key].push(zone)
      return groups
    }, {})).sort(([left], [right]) => {
      if (left === 'legacy_other') return 1
      if (right === 'legacy_other') return -1
      return (TOPIC_LABELS[left] || left).localeCompare(TOPIC_LABELS[right] || right, 'vi')
    })
  }, [otherZones, publisher, query, topicFilter])

  const toggleTopic = (topicId) => {
    setExpandedTopics(current => {
      const next = new Set(current)
      if (next.has(topicId)) next.delete(topicId)
      else next.add(topicId)
      return next
    })
  }

  const toggleZone = (id) => {
    const next = selectedIds.includes(id)
      ? selectedIds.filter(x => x !== id)
      : [...selectedIds, id]
    onChange({ ...data, selectedZoneIds: next, created: false })
  }

  const handleReRecommend = () => {
    // Reset initialized so SetupStep re-fetches from backend
    onChange({ ...data, initialized: false, recoZones: [], relatedZones: [], allZones: [], selectedZoneIds: [], created: false })
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
      <div data-demo="reco-zones-section" className="rounded-xl border border-amber-200 bg-gradient-to-br from-amber-50/80 to-orange-50/60 overflow-hidden">
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

      {relatedZones.length > 0 && (
        <div data-demo="related-zones-section" className="rounded-xl border border-sky-200 bg-sky-50/60 overflow-hidden">
          <div className="flex items-center justify-between gap-2 px-3 py-2 border-b border-sky-200 bg-sky-100/60">
            <div>
              <p className="text-xs font-bold text-sky-800">Ad zones liên quan để mở rộng</p>
              <p className="text-[10px] text-sky-700">Lựa chọn gần với brief, chưa được chọn</p>
            </div>
            <Badge className="bg-sky-100 text-sky-700 border-sky-300">{relatedZones.length} zones</Badge>
          </div>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-2 p-2">
            {relatedZones.map(zone => (
              <ZoneCard
                key={zone.id}
                zone={zone}
                selected={selectedIds.includes(zone.id)}
                onToggle={toggleZone}
                isReco={false}
                isRelated
                budgetPerZoneM={budgetPerZone}
              />
            ))}
          </div>
        </div>
      )}

      {/* Expand full list */}
      <Button data-demo="expand-zones-btn" variant="outline" size="sm" onClick={() => setExpanded(e => !e)} className="w-full gap-2 text-xs h-9">
        {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        {expanded ? 'Thu gọn' : `Xem thêm ${otherZones.length} zones khác`}
      </Button>

      {expanded && (
        <div className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-[1fr_170px_190px] gap-2">
            <label className="relative">
              <Search className="absolute left-3 top-2.5 w-3.5 h-3.5 text-muted-foreground" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Tìm topic, publisher hoặc format..."
                className="h-9 w-full rounded-lg border border-border bg-white pl-9 pr-3 text-xs outline-none focus:border-brand-400"
              />
            </label>
            <select
              value={publisher}
              onChange={(event) => setPublisher(event.target.value)}
              className="h-9 rounded-lg border border-border bg-white px-3 text-xs outline-none focus:border-brand-400"
            >
              <option value="all">Tất cả publisher</option>
              {publisherOptions.map((publisherName) => (
                <option key={publisherName} value={publisherName}>{publisherName}</option>
              ))}
            </select>
            <select
              value={topicFilter}
              onChange={(event) => setTopicFilter(event.target.value)}
              className="h-9 rounded-lg border border-border bg-white px-3 text-xs outline-none focus:border-brand-400"
              aria-label="Lọc ad zone theo topic"
            >
              <option value="all">Tất cả topics</option>
              {topicOptions.map(topicId => (
                <option key={topicId} value={topicId}>{TOPIC_LABELS[topicId] || topicId.replaceAll('_', ' ')}</option>
              ))}
            </select>
          </div>
          {groupedZones.map(([topicId, zones]) => {
            const topicExpanded = Boolean(query.trim()) || topicFilter !== 'all' || expandedTopics.has(topicId)
            return (
            <section key={topicId} className="rounded-xl border border-border bg-slate-50/70 overflow-hidden">
              <button
                type="button"
                onClick={() => toggleTopic(topicId)}
                className="flex w-full items-center justify-between px-3 py-2 bg-white text-left hover:bg-slate-50"
                aria-expanded={topicExpanded}
              >
                <div>
                  <p className="text-xs font-bold text-slate-800">{TOPIC_LABELS[topicId] || topicId.replaceAll('_', ' ')}</p>
                  <p className="text-[10px] text-muted-foreground">
                    {zones.length} placements
                    {topicId !== 'legacy_other' ? ' · ZNews và BaoMoi có thể so sánh cùng topic/format' : ''}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="muted" className="text-[10px]">{topicId}</Badge>
                  {topicExpanded ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
                </div>
              </button>
              {topicExpanded && (
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-2 p-2 border-t border-border">
                {[...zones]
                  .sort((left, right) => (
                    `${left.placementFamily || ''}:${left.publisher || ''}:${left.id}`
                      .localeCompare(`${right.placementFamily || ''}:${right.publisher || ''}:${right.id}`)
                  ))
                  .map(zone => (
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
            </section>
          )})}
          {!groupedZones.length && (
            <p className="py-8 text-center text-xs text-muted-foreground">Không có placement phù hợp bộ lọc.</p>
          )}
        </div>
      )}

      {selectedIds.length > 0 && (
        <div className="sticky bottom-0 z-20 -mx-1 rounded-xl border border-brand-200 bg-white/95 p-2 shadow-[0_-8px_24px_rgba(15,23,42,0.12)] backdrop-blur">
          <Button
            onClick={() => onChange({ ...data, phase: 'assign' })}
            className="w-full gap-2"
            id="confirm-zones-btn"
          >
            <ArrowRight className="w-4 h-4" />
            Tiếp tục gắn creative vào {selectedIds.length} zones
          </Button>
        </div>
      )}
    </div>
  )
}
