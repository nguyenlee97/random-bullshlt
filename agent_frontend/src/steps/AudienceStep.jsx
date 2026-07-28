import { useState, useEffect, useMemo } from 'react'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn, fmt } from '@/lib/utils'
import { AgentAPI, fetchDmpAttributes } from '@/api/agentApi'
import { dedupeDmpAttrs, enrichAudienceSelection, normalizeDmpAttr } from '@/lib/audience'
import { Users, Check, Search, Loader2, Sparkles, ChevronDown, ChevronUp, BrainCircuit, X } from 'lucide-react'
import TargetingPanel from '@/components/TargetingPanel'

function getUid(a) { return a._uid || a.code || a.name || '' }

function AttrCard({ attr, selected, onToggle, reason, isReco, tier = 'recommended' }) {
  const sel = selected
  const adjacent = isReco && tier === 'adjacent'
  return (
    <button onClick={() => onToggle(attr)}
      data-demo="autopilot-audience-option"
      aria-pressed={selected}
      className={cn('flex items-start gap-2.5 p-3 rounded-xl border text-left transition-all duration-150 w-full',
        sel && 'border-brand-400 bg-brand-50 shadow-sm',
        !sel && isReco && !adjacent && 'border-amber-300 bg-amber-50/60 hover:border-amber-400',
        !sel && adjacent && 'border-sky-300 bg-sky-50/60 hover:border-sky-400',
        !sel && !isReco && 'border-border bg-white hover:border-brand-300 hover:bg-brand-50/50',
      )} id={`attr-${getUid(attr)}`}>
      <div className={cn('w-4 h-4 rounded flex items-center justify-center flex-shrink-0 mt-0.5 border transition-all',
        sel ? 'bg-brand-500 border-brand-500' : 'border-muted-foreground/40')}>
        {sel && <Check className="w-2.5 h-2.5 text-white" strokeWidth={3} />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 flex-wrap">
          <p className="text-xs font-semibold text-foreground leading-tight">{attr.name}</p>
          {isReco && !adjacent && <Badge className="text-[9px] h-4 px-1 bg-amber-100 text-amber-700 border-amber-300">⭐ Đề xuất</Badge>}
          {adjacent && <Badge className="text-[9px] h-4 px-1 bg-sky-100 text-sky-700 border-sky-300">↗ Liên quan</Badge>}
        </div>
        {isReco && reason && <p className={cn('text-[10px] mt-0.5 leading-tight italic', adjacent ? 'text-sky-700' : 'text-amber-700')}>{reason}</p>}
        <div className="flex items-center gap-1.5 mt-1 flex-wrap">
          {attr.code && <Badge variant="muted" className="text-[10px] h-4 px-1.5">{attr.code}</Badge>}
          {attr.category && <Badge variant="muted" className="text-[10px] h-4 px-1.5">{attr.category}</Badge>}
          <span className="text-[10px] text-muted-foreground">
            {Number(attr.est_size) > 0 ? fmt(attr.est_size) : 'Chưa có size'}
          </span>
          {attr.sizeSource === 'modeled_estimate' && (
            <Badge className="text-[9px] h-4 px-1 bg-sky-50 text-sky-700 border-sky-200">
              Ước lượng
            </Badge>
          )}
        </div>
      </div>
    </button>
  )
}

export default function AudienceStep({
  data, onChange, isDone, brief, recoFromChat, expandTargeting = false,
  openaiCampaignFlow = false,
}) {

  const [allAttrs, setAllAttrs] = useState([])
  const [loading, setLoading] = useState(true)
  const [recoAttrs, setRecoAttrs] = useState([])
  const [recoLoading, setRecoLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [expanded, setExpanded] = useState(false)
  const [reachLoading, setReachLoading] = useState(false)

  const objective = brief?.objective || 'awareness'
  const hasAudienceEstimate = Number(data.size || 0) > 0
  const usesModeledEstimate = (data.attrs || []).some(attr => attr.sizeSource === 'modeled_estimate')

  // Load all DMP segments (cached)
  useEffect(() => {
    fetchDmpAttributes().then(normalized => {
      setAllAttrs(normalized)
      setLoading(false)
    })
  }, [])

  // Older Autopilot artifacts contain the selected IDs and reasons but not
  // always the catalog size fields. Join them back to the current catalog so
  // the cards remain selected and the estimate is meaningful.
  useEffect(() => {
    if (!allAttrs.length || !data.attrs.length) return
    const enriched = enrichAudienceSelection(data, allAttrs)
    const changed = enriched.size !== data.size || enriched.attrs.some(
      (attr, index) => attr.est_size !== Number(data.attrs[index]?.est_size || 0),
    )
    if (changed) onChange(enriched)
  }, [allAttrs, data, onChange])

  const selectedKey = (data.attrs || []).map(getUid).filter(Boolean).sort().join('|')
  useEffect(() => {
    let cancelled = false
    if (!selectedKey) {
      if (data.size || data.sizeKnown || data.reach) {
        onChange({ ...data, size: 0, sizeKnown: false, reach: null })
      }
      return () => { cancelled = true }
    }
    setReachLoading(true)
    AgentAPI.getAudienceReach(data.attrs).then(reach => {
      if (cancelled) return
      setReachLoading(false)
      if (!reach) {
        onChange({ ...data, size: 0, sizeKnown: false, reach: { status: 'unavailable' } })
        return
      }
      onChange({
        ...data,
        size: Number(reach.unique_reach || 0),
        sizeKnown: reach.unique_reach != null,
        reach,
      })
    })
    return () => { cancelled = true }
    // The stable segment identity is the only trigger; reach metadata updates
    // must not recursively request the same estimate.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedKey])

  // Use audience-entry recommendation from chat — no fallback to dmp-recommend.
  // Per design: audience-entry is the single source of truth for recommendations.
  // If recoFromChat is null (still loading), show spinner until it arrives.
  useEffect(() => {
    if (recoFromChat && recoFromChat.length > 0) {
      setRecoAttrs(dedupeDmpAttrs(recoFromChat))
      setRecoLoading(false)
    } else if (data.attrs.length > 0) {
      // Editing an existing Autopilot artifact does not trigger audience-entry.
      // Reuse the current selection instead of leaving this card loading forever.
      setRecoAttrs(dedupeDmpAttrs(data.attrs))
      setRecoLoading(false)
    } else {
      // A new/resumed conversation can reuse this mounted component. Clear the
      // previous campaign's recommendation DOM before the next request arrives.
      setRecoAttrs([])
      setRecoLoading(true)
    }
  }, [data.attrs, recoFromChat])

  const recoUids = useMemo(() => new Set(recoAttrs.map(a => a._uid)), [recoAttrs])
  const directReco = useMemo(
    () => recoAttrs.filter(attr => attr.tier !== 'adjacent' && attr.match_tier !== 'adjacent'),
    [recoAttrs],
  )
  const adjacentReco = useMemo(
    () => recoAttrs.filter(attr => attr.tier === 'adjacent' || attr.match_tier === 'adjacent'),
    [recoAttrs],
  )

  const isSelected = (attr) => {
    const uid = getUid(attr)
    return uid !== '' && data.attrs.some(a => getUid(a) === uid)
  }

  const toggleAttr = (attr) => {
    const uid = getUid(attr)
    if (!uid) return
    const already = data.attrs.some(a => getUid(a) === uid)
    const newAttrs = already ? data.attrs.filter(a => getUid(a) !== uid) : [...data.attrs, attr]
    onChange({ ...data, attrs: newAttrs, size: 0, sizeKnown: false, reach: null })
  }

  // Full list excludes segments already shown in AI reco section
  const filtered = allAttrs
    .filter(a => !recoUids.has(a._uid))
    .filter(a =>
      !search || a.name?.toLowerCase().includes(search.toLowerCase()) || a.code?.toLowerCase().includes(search.toLowerCase())
    )


  if (isDone) {
    return (
      <div className="space-y-3">
        <Card className="border-brand-200 bg-brand-50">
          <CardContent className="py-4">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-5 h-5 rounded-full bg-brand-500 flex items-center justify-center">
                <Check className="w-3 h-3 text-white" />
              </div>
              <h4 className="text-sm font-semibold text-brand-700">Audience đã xác nhận</h4>
              <Badge variant="green" className="ml-auto">
                {hasAudienceEstimate ? `${fmt(data.size)} người dùng` : 'Chưa có size'}
              </Badge>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {data.attrs.map(a => <Badge key={getUid(a)} variant="muted">{a.name}</Badge>)}
            </div>
            {usesModeledEstimate && (
              <p className="mt-2 text-[10px] text-sky-700">
                Một số segment dùng quy mô ước lượng theo mô hình catalog Việt Nam.
              </p>
            )}
          </CardContent>
        </Card>
        {Object.keys(data.targeting || {}).length > 0 && (
          <TargetingPanel targeting={data.targeting} onChange={() => { }} />
        )}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* Size meter */}
      <Card className={cn('border-2 transition-all', data.attrs.length > 0 ? 'border-brand-300 bg-brand-50' : 'border-border')}>
        <CardContent className="py-3 flex items-center gap-4">
          <div className={cn('w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0', data.attrs.length > 0 ? 'bg-brand-500' : 'bg-muted')}>
            <Users className={cn('w-5 h-5', data.attrs.length > 0 ? 'text-white' : 'text-muted-foreground')} />
          </div>
          <div className="flex-1">
            <p className={cn('text-2xl font-black', data.attrs.length > 0 ? 'text-brand-700' : 'text-muted-foreground')}>
              {reachLoading ? '…' : (data.attrs.length > 0 && hasAudienceEstimate ? fmt(data.size) : '—')}
            </p>
            <p className="text-xs text-muted-foreground">
              {data.attrs.length > 0
                ? (reachLoading
                    ? `Đang tính unique reach từ ${data.attrs.length} segments`
                    : (hasAudienceEstimate
                        ? `Unique reach ước lượng · ${data.attrs.length} segments · ${data.reach?.method || 'server'}`
                        : `${data.attrs.length} segments · chưa thể tính reach`))
                : 'Chọn ít nhất 1 segment để tính size'}
            </p>
          </div>
          {data.attrs.length > 0 && <Badge variant="green">{data.attrs.length} đã chọn</Badge>}
        </CardContent>
      </Card>

      {openaiCampaignFlow && data.attrs.length > 0 && (
        <div
          className="rounded-xl border border-brand-200 bg-brand-50/70 px-3 py-2.5"
          data-demo="selected-audience-shelf"
        >
          <div className="mb-2 flex items-center gap-2">
            <Check className="h-3.5 w-3.5 text-brand-600" />
            <span className="text-xs font-bold text-brand-700">Segment đã chọn</span>
            <Badge variant="green" className="ml-auto">{data.attrs.length}</Badge>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {data.attrs.map(attr => (
              <button
                key={getUid(attr)}
                type="button"
                onClick={() => toggleAttr(attr)}
                title={`Bỏ chọn ${attr.name}`}
                aria-label={`Bỏ chọn ${attr.name}`}
                className="inline-flex max-w-full items-center gap-1 rounded-full border border-brand-200 bg-white px-2 py-1 text-[11px] font-semibold text-brand-700 shadow-sm transition-colors hover:border-red-200 hover:bg-red-50 hover:text-red-700"
              >
                <span className="truncate">{attr.name}</span>
                <X className="h-3 w-3 flex-shrink-0" />
              </button>
            ))}
          </div>
          <p className="mt-1.5 text-[10px] text-brand-600">
            Luôn hiển thị tại đây, kể cả khi segment nằm sâu trong danh sách đầy đủ.
          </p>
        </div>
      )}

      {/* Targeting Parameters from AI */}
      <TargetingPanel
        targeting={data.targeting || {}}
        onChange={tp => onChange({ ...data, targeting: tp })}
        autoExpand={expandTargeting}
      />

      {/* AI Recommended — fetched from backend LLM based on real DMP + brief */}
      <div data-demo="ai-reco-section" className="rounded-xl border border-amber-200 bg-gradient-to-br from-amber-50 to-orange-50 overflow-hidden">
        <div className="flex items-center gap-2 px-3 py-2 border-b border-amber-200 bg-amber-100/60">
          <BrainCircuit className="w-4 h-4 text-amber-600" />
          <span className="text-xs font-bold text-amber-700">
            AI Gợi ý · {brief?.brand ? `Dựa theo brief "${brief.brand}"` : `Objective: ${objective}`}
          </span>
          <Badge className="ml-auto text-[10px] bg-amber-200 text-amber-800 border-amber-300">
            {recoLoading ? '⏳ Đang phân tích...' : `${recoAttrs.length} segments`}
          </Badge>
        </div>
        {recoLoading ? (
          <div className="flex items-center justify-center gap-2 py-6">
            <Loader2 className="w-4 h-4 animate-spin text-amber-500" />
            <span className="text-xs text-amber-700">AI đang phân tích brief và chọn segment phù hợp...</span>
          </div>
        ) : recoAttrs.length === 0 ? (
          <div className="px-3 py-4 text-center text-xs text-amber-700">
            Không tìm thấy segment phù hợp — thử xem thêm bên dưới.
          </div>
        ) : (
          <div className="space-y-3 p-2">
            {directReco.length > 0 ? (
              <div>
                <p className="mb-2 px-1 text-[10px] font-black uppercase tracking-wide text-amber-800">Đề xuất trực tiếp · chọn sẵn</p>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {directReco.map(attr => (
                    <AttrCard key={attr._uid} attr={attr} selected={isSelected(attr)} onToggle={toggleAttr} reason={attr.reason} isReco tier="recommended" />
                  ))}
                </div>
              </div>
            ) : (
              <p className="rounded-lg bg-white/70 px-3 py-2 text-xs text-amber-800">
                Catalog chưa có segment khớp trực tiếp; Agent không tự chọn một kết quả yếu.
              </p>
            )}
            {adjacentReco.length > 0 && (
              <div>
                <div className="mb-2 flex items-center justify-between gap-2 px-1">
                  <p className="text-[10px] font-black uppercase tracking-wide text-sky-800">Liên quan để mở rộng · chưa chọn</p>
                  <span className="text-[10px] text-sky-700">Chỉ chọn khi phù hợp với chiến lược</span>
                </div>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {adjacentReco.map(attr => (
                    <AttrCard key={attr._uid} attr={attr} selected={isSelected(attr)} onToggle={toggleAttr} reason={attr.reason} isReco tier="adjacent" />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Expand full list */}
      <Button variant="outline" size="sm" onClick={() => setExpanded(e => !e)} className="w-full gap-2 text-xs h-9" data-demo="expand-segments-btn">
        {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        {expanded ? 'Thu gọn danh sách' : `Xem thêm ${loading ? '…đang tải' : `${filtered.length} segments khác`}`}
      </Button>

      {expanded && (
        <div className="space-y-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Tìm theo tên, mã, danh mục..." className="pl-9 h-9" id="audience-search" />
          </div>
          {loading ? (
            <div className="flex items-center justify-center py-6">
              <Loader2 className="w-5 h-5 animate-spin text-brand-500" />
              <span className="ml-2 text-sm text-muted-foreground">Đang tải...</span>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-[280px] overflow-y-auto pr-1">
              {filtered.map(attr => (
                <AttrCard key={getUid(attr)} attr={attr} selected={isSelected(attr)} onToggle={toggleAttr} isReco={false} />
              ))}
              {filtered.length === 0 && <div className="col-span-2 text-center py-6 text-sm text-muted-foreground">Không tìm thấy segment phù hợp</div>}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
