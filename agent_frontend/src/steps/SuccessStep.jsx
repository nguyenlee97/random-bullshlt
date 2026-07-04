import { useState, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { fmt } from '@/lib/utils'
import {
  CheckCircle2, Users, DollarSign, LayoutGrid,
  BarChart2, Eye, MousePointerClick, ExternalLink, Film,
  Globe, Monitor, Camera, RefreshCw, X, ZoomIn, AlertCircle,
  Loader2, ChevronDown, ChevronUp,
} from 'lucide-react'
import { getSelectedZones, fmtVnd, fmtImp, estImpressions, checkMismatch } from './setup/setupUtils'
import { ALL_ZONES } from '@/data/zones'
import { AgentAPI } from '@/api/agentApi'

// ─── Check if campaign is currently live (start ≤ now ≤ end) ──────────────────
function isLive(brief) {
  if (!brief?.startDate) return false
  const now = new Date()
  const start = new Date(brief.startDate)
  const end   = brief.endDate ? new Date(brief.endDate) : null
  return start <= now && (!end || now <= end)
}

function KpiCard({ icon: Icon, label, value, sub, color, bg }) {
  return (
    <Card className={`border ${bg}`}>
      <CardContent className="py-3 flex items-center gap-3">
        <Icon className={`w-5 h-5 ${color} flex-shrink-0`} />
        <div className="min-w-0">
          <p className={`text-lg font-black ${color} leading-tight`}>{value}</p>
          <p className="text-xs text-muted-foreground leading-tight">{label}</p>
          {sub && <p className="text-[10px] text-muted-foreground">{sub}</p>}
        </div>
      </CardContent>
    </Card>
  )
}

// ─── Lightbox — works for both zone crops and full annotated page ─────────────
function Lightbox({ src, title, onClose }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/90 backdrop-blur-sm overflow-auto py-8 px-4"
      onClick={onClose}
    >
      <div className="relative max-w-6xl w-full" onClick={e => e.stopPropagation()}>
        <button
          onClick={onClose}
          className="absolute -top-10 right-0 flex items-center gap-1.5 text-white/70 hover:text-white text-xs transition-colors"
        >
          <X className="w-4 h-4" /> Đóng
        </button>
        <div className="rounded-xl overflow-hidden shadow-2xl border border-white/10">
          <div className="bg-black/60 px-4 py-2 flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            <span className="text-xs text-white/80 font-medium">{title}</span>
          </div>
          <img src={src} alt={title} className="w-full block" draggable={false} />
        </div>
      </div>
    </div>
  )
}

// ─── Individual zone crop card ────────────────────────────────────────────────
function ZoneCropCard({ zone, platform }) {
  const [lightbox, setLightbox] = useState(false)
  const src = `data:image/png;base64,${zone.crop_b64}`

  return (
    <div className="rounded-xl overflow-hidden border border-border shadow-sm">
      {/* Zone label bar — coloured with the zone's highlight colour */}
      <div
        className="flex items-center justify-between px-3 py-2"
        style={{ backgroundColor: zone.color + '18', borderBottom: `2px solid ${zone.color}` }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <div
            className="w-2.5 h-2.5 rounded-full flex-shrink-0"
            style={{ backgroundColor: zone.color }}
          />
          <span className="text-xs font-semibold text-foreground truncate">{zone.label}</span>
          <span className="text-[10px] text-muted-foreground truncate hidden sm:block">
            ({zone.id})
          </span>
        </div>
        <button
          onClick={() => setLightbox(true)}
          className="flex items-center gap-1 text-[10px] font-medium transition-colors flex-shrink-0 ml-2"
          style={{ color: zone.color }}
        >
          <ZoomIn className="w-3 h-3" /> Xem to
        </button>
      </div>

      {/* Crop image */}
      <div
        className="relative cursor-zoom-in group"
        onClick={() => setLightbox(true)}
      >
        <img
          src={src}
          alt={zone.label}
          className="w-full block"
          style={{ maxHeight: '320px', objectFit: 'cover', objectPosition: 'center top' }}
        />
        {/* Hover overlay */}
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center">
          <div className="opacity-0 group-hover:opacity-100 transition-opacity bg-black/50 rounded-lg px-3 py-2 flex items-center gap-2">
            <ZoomIn className="w-4 h-4 text-white" />
            <span className="text-white text-xs font-medium">Xem toàn màn hình</span>
          </div>
        </div>
      </div>

      {/* Bbox metadata */}
      <div className="px-3 py-1.5 bg-muted/30 border-t border-border">
        <p className="text-[10px] text-muted-foreground">
          Vị trí: ({Math.round(zone.bbox.x)}, {Math.round(zone.bbox.y)}) &nbsp;·&nbsp;
          Kích thước: {Math.round(zone.bbox.width)} × {Math.round(zone.bbox.height)}px
        </p>
      </div>

      {lightbox && (
        <Lightbox
          src={src}
          title={`${platform} — ${zone.label}`}
          onClose={() => setLightbox(false)}
        />
      )}
    </div>
  )
}

// ─── Per-platform screenshot block ────────────────────────────────────────────
function PlatformScreenshotRow({ zone }) {
  const [state, setState]           = useState('idle')  // idle | loading | done | error
  const [result, setResult]         = useState(null)    // full API response
  const [errMsg, setErrMsg]         = useState('')
  const [lightboxFull, setLightboxFull] = useState(false)
  const [showFull, setShowFull]     = useState(false)

  const capture = useCallback(async () => {
    setState('loading')
    setErrMsg('')
    try {
      const res = await AgentAPI.captureAdScreenshot(zone.siteUrl, zone.zoneIds || [])
      if (res?.ok) {
        setResult(res)
        setState('done')
      } else {
        setErrMsg(res?.error || 'Chụp ảnh thất bại')
        setState('error')
      }
    } catch (e) {
      setErrMsg(e.message || 'Lỗi kết nối')
      setState('error')
    }
  }, [zone.siteUrl])

  const fmtTime = iso => {
    if (!iso) return ''
    try { return new Date(iso).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) }
    catch { return '' }
  }

  return (
    <div className="space-y-3">
      {/* Header row: platform name + capture button */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-6 h-6 rounded-md bg-green-100 flex items-center justify-center flex-shrink-0">
            <Globe className="w-3.5 h-3.5 text-green-600" />
          </div>
          <div className="min-w-0">
            <p className="text-xs font-semibold text-foreground truncate">{zone.platform}</p>
            <p className="text-[10px] text-muted-foreground truncate">{zone.siteUrl}</p>
          </div>
        </div>

        <button
          onClick={capture}
          disabled={state === 'loading'}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex-shrink-0
            ${state === 'loading'
              ? 'bg-muted text-muted-foreground cursor-not-allowed'
              : state === 'done'
                ? 'bg-green-100 text-green-700 hover:bg-green-200 border border-green-200'
                : 'bg-brand-500 text-white hover:bg-brand-600 shadow-sm'
            }`}
        >
          {state === 'loading' ? (
            <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Đang chụp...</>
          ) : state === 'done' ? (
            <><RefreshCw className="w-3.5 h-3.5" /> Chụp lại</>
          ) : (
            <><Camera className="w-3.5 h-3.5" /> Chụp ảnh</>
          )}
        </button>
      </div>

      {/* Error */}
      {state === 'error' && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-red-50 border border-red-200">
          <AlertCircle className="w-3.5 h-3.5 text-red-500 flex-shrink-0" />
          <p className="text-[11px] text-red-600 flex-1">{errMsg}</p>
          <button onClick={capture} className="text-[10px] text-red-500 hover:text-red-700 font-medium underline flex-shrink-0">
            Thử lại
          </button>
        </div>
      )}

      {/* Results */}
      {state === 'done' && result && (
        <div className="space-y-3">
          {/* Capture metadata bar */}
          <div className="flex items-center justify-between text-[10px] text-muted-foreground px-1">
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
              <span>Chụp lúc {fmtTime(result.captured_at)} · {result.zone_count} zone tìm thấy</span>
            </div>
          </div>

          {/* Zone crop cards — one per detected ad zone */}
          {result.zones && result.zones.length > 0 ? (
            <div className="space-y-3">
              {result.zones.map(z => (
                <ZoneCropCard key={z.id} zone={z} platform={zone.platform} />
              ))}
            </div>
          ) : (
            <p className="text-[11px] text-muted-foreground text-center py-3">
              Không tìm thấy ad zone nào đang hiển thị trên trang.
            </p>
          )}

          {/* Full annotated page toggle */}
          <button
            onClick={() => setShowFull(v => !v)}
            className="w-full flex items-center justify-center gap-1.5 py-2 rounded-lg border border-dashed border-border text-[11px] text-muted-foreground hover:text-foreground hover:border-brand-300 hover:bg-brand-50/30 transition-colors"
          >
            {showFull ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            {showFull ? 'Ẩn' : 'Xem'} toàn trang có đánh dấu
          </button>

          {showFull && (
            <div className="rounded-xl overflow-hidden border border-border shadow-sm">
              <div className="flex items-center justify-between bg-muted/40 px-3 py-1.5 border-b border-border">
                <span className="text-[10px] text-muted-foreground font-medium">
                  Toàn trang — {result.width}×{result.height}px
                </span>
                <button
                  onClick={() => setLightboxFull(true)}
                  className="flex items-center gap-1 text-[10px] text-brand-600 hover:text-brand-800 font-medium"
                >
                  <ZoomIn className="w-3 h-3" /> Xem to
                </button>
              </div>
              <div
                className="relative cursor-zoom-in group"
                onClick={() => setLightboxFull(true)}
              >
                <img
                  src={`data:image/jpeg;base64,${result.full_b64}`}
                  alt="Annotated full page"
                  className="w-full block"
                  style={{ maxHeight: '400px', objectFit: 'cover', objectPosition: 'top' }}
                />
                <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center">
                  <div className="opacity-0 group-hover:opacity-100 transition-opacity bg-black/50 rounded-lg px-3 py-2 flex items-center gap-2">
                    <ZoomIn className="w-4 h-4 text-white" />
                    <span className="text-white text-xs font-medium">Xem toàn màn hình</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {lightboxFull && result.full_b64 && (
            <Lightbox
              src={`data:image/jpeg;base64,${result.full_b64}`}
              title={`${zone.platform} — Toàn trang (có đánh dấu zones)`}
              onClose={() => setLightboxFull(false)}
            />
          )}
        </div>
      )}
    </div>
  )
}


// ─── Main SuccessStep export ───────────────────────────────────────────────────
export default function SuccessStep({ brief, zones, selectedZoneIds, audienceSize, setup, allZones, recoZones }) {
  const ids = selectedZoneIds || []
  const dynamicPool = [...(recoZones || []), ...(allZones || [])]
  const selectedZones = ids.map(id => {
    const dynamic = dynamicPool.find(z => z.id === id)
    const staticZ  = ALL_ZONES.find(z => z.id === id)
    if (staticZ && dynamic) return { ...staticZ, ...dynamic }
    if (dynamic) return {
      ...dynamic,
      name:     dynamic.name     || dynamic.id.replace(/_/g, ' '),
      platform: dynamic.platform || dynamic.channel || dynamic.id.split('_')[0],
    }
    return staticZ
  }).filter(Boolean)

  const assignments = setup?.assignments || {}
  const files = setup?.creativeFiles || []
  const live = isLive(brief)

  const budgetPerZone = selectedZones.length > 0 ? (brief?.budget || 0) / selectedZones.length : 0
  const totalEstImps = selectedZones.reduce((sum, z) => sum + estImpressions(z, budgetPerZone), 0)
  const avgCTR = selectedZones.length > 0
    ? (selectedZones.reduce((s, z) => s + z.ctr, 0) / selectedZones.length).toFixed(2) : '—'
  const avgVI = selectedZones.length > 0
    ? Math.round(selectedZones.reduce((s, z) => s + z.vi, 0) / selectedZones.length) : '—'

  const dateRange = brief?.startDate && brief?.endDate
    ? `${brief.startDate} → ${brief.endDate}` : brief?.startDate || '—'

  const ADSPILOT_URL = 'https://adspilot.pawgrammers.io.vn'
  const ADSPILOT_ORDERS = `${ADSPILOT_URL}/#/orders`

  // Group selected zone IDs by platform siteUrl so each platform only captures
  // the zones the user actually selected (not all possible zones for that site).
  const uniquePlatforms = [...new Map(
    selectedZones.filter(z => z.siteUrl).map(z => [z.siteUrl, z])
  ).values()].map(platformZone => ({
    ...platformZone,
    // Collect all selected zone IDs that share this siteUrl
    zoneIds: selectedZones
      .filter(z => z.siteUrl === platformZone.siteUrl)
      .map(z => z.id),
  }))

  return (
    <div className="space-y-4">
      {/* Hero banner */}
      <div data-demo="result-hero" className="rounded-2xl bg-gradient-to-br from-brand-500 to-violet-600 p-5 text-white shadow-lg">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <CheckCircle2 className="w-7 h-7" />
              <h2 className="text-xl font-black">Chiến dịch đã được tạo!</h2>
            </div>
            <p className="text-sm text-white/80">{brief?.brand} · {brief?.objective} · {dateRange}</p>
          </div>
          {live && (
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-green-400/30 border border-green-300/50">
              <div className="w-2 h-2 rounded-full bg-green-300 animate-pulse" />
              <span className="text-xs font-bold text-green-100">LIVE</span>
            </div>
          )}
        </div>
      </div>

      {/* Quick links */}
      <Card data-demo="quick-links-card" className="border-brand-200">
        <CardHeader className="pb-2 pt-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <Monitor className="w-4 h-4 text-brand-500" />
            Liên kết nhanh
          </CardTitle>
        </CardHeader>
        <CardContent className="pb-3 pt-0 space-y-2">
          <a href={ADSPILOT_ORDERS} target="_blank" rel="noreferrer"
            className="flex items-center gap-2.5 p-2.5 rounded-lg border border-brand-200 bg-brand-50 hover:bg-brand-100 transition-colors group">
            <div className="w-8 h-8 rounded-lg bg-brand-500 flex items-center justify-center flex-shrink-0">
              <LayoutGrid className="w-4 h-4 text-white" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-bold text-brand-700">Xem trong AdsPilot</p>
              <p className="text-[10px] text-brand-500 truncate">{ADSPILOT_ORDERS}</p>
            </div>
            <ExternalLink className="w-3.5 h-3.5 text-brand-400 group-hover:text-brand-600 flex-shrink-0" />
          </a>

          {uniquePlatforms.map(zone => (
            <a key={zone.platform} href={zone.siteUrl} target="_blank" rel="noreferrer"
              className="flex items-center gap-2.5 p-2.5 rounded-lg border border-border hover:border-brand-300 hover:bg-brand-50/40 transition-colors group">
              <div className="w-8 h-8 rounded-lg bg-muted flex items-center justify-center flex-shrink-0">
                <Globe className="w-4 h-4 text-muted-foreground" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-bold text-foreground">{zone.platform} — Test Site</p>
                <p className="text-[10px] text-muted-foreground truncate">{zone.siteUrl}</p>
              </div>
              <ExternalLink className="w-3.5 h-3.5 text-muted-foreground group-hover:text-brand-500 flex-shrink-0" />
            </a>
          ))}
        </CardContent>
      </Card>

      {/* ── Screenshot capture card — only when LIVE ────────────────────────── */}
      {live && uniquePlatforms.length > 0 && (
        <Card data-demo="ad-live-card" className="border-green-200 bg-green-50/30">
          <CardHeader className="pb-2 pt-3">
            <CardTitle className="text-sm flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Camera className="w-4 h-4 text-green-600" />
                <span>Ảnh chụp Ad Live</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                <Badge className="bg-green-100 text-green-700 border-green-300 text-[10px]">
                  🔴 Đang live
                </Badge>
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent className="pb-4 pt-0 space-y-5">
            <p className="text-[11px] text-muted-foreground leading-relaxed">
              Bấm "Chụp ảnh" để xem từng ad zone hiển thị thực tế trên site — mỗi zone được cắt riêng, có đánh dấu màu và toàn cảnh xung quanh.
            </p>

            {uniquePlatforms.map((zone, idx) => (
              <div key={zone.platform}>
                {idx > 0 && <div className="border-t border-green-200/60 pt-5" />}
                <PlatformScreenshotRow zone={zone} />
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* KPI grid */}
      <div data-demo="kpi-grid" className="grid grid-cols-2 gap-2">
        <KpiCard icon={LayoutGrid} label="Ad zones" value={selectedZones.length} color="text-brand-600" bg="bg-brand-50 border-brand-200" />
        <KpiCard icon={Users} label="Audience" value={fmt(audienceSize || 0)} sub="người dùng" color="text-blue-600" bg="bg-blue-50 border-blue-200" />
        <KpiCard icon={DollarSign} label="Ngân sách" value={`${brief?.budget}M`} sub="VND" color="text-violet-600" bg="bg-violet-50 border-violet-200" />
        <KpiCard icon={Eye} label="Est. Impressions" value={fmtImp(totalEstImps)} color="text-green-600" bg="bg-green-50 border-green-200" />
        <KpiCard icon={MousePointerClick} label="Avg CTR" value={`${avgCTR}%`} color="text-amber-600" bg="bg-amber-50 border-amber-200" />
        <KpiCard icon={BarChart2} label="Avg Viewability" value={`${avgVI}%`} color="text-pink-600" bg="bg-pink-50 border-pink-200" />
      </div>

      {/* Zone breakdown */}
      <Card>
        <CardHeader className="pb-2 pt-3">
          <CardTitle className="text-sm flex items-center justify-between">
            <span>Chi tiết zones</span>
            <div className="flex items-center gap-2">
              {live && <Badge className="bg-green-100 text-green-700 border-green-300 text-[10px]">🔴 Đang live</Badge>}
              <Badge variant="green">{selectedZones.length} zones</Badge>
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent className="pb-3 pt-0 space-y-3">
          {selectedZones.map(zone => {
            const assignedFile = files.find(f => f.id === assignments[zone.id])
            const mismatch = assignedFile ? checkMismatch(zone, assignedFile) : null
            const imp = estImpressions(zone, budgetPerZone)
            return (
              <div key={zone.id} className={`p-3 rounded-xl border space-y-2 ${mismatch ? 'border-red-200 bg-red-50/20' : 'border-border'}`}>
                <div className="flex items-start gap-2.5">
                  <div className="w-14 h-10 rounded-md overflow-hidden bg-muted/40 flex-shrink-0 border border-border">
                    {assignedFile?.type?.startsWith('image/') ? (
                      <img src={assignedFile.dataUrl} alt="" className="w-full h-full object-cover" />
                    ) : assignedFile?.type?.startsWith('video/') ? (
                      <div className="w-full h-full flex items-center justify-center bg-violet-50">
                        <Film className="w-4 h-4 text-violet-400" />
                      </div>
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <span className="text-[8px] text-muted-foreground">—</span>
                      </div>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-semibold text-foreground">{zone.name}</p>
                    <div className="flex items-center gap-1 mt-0.5 flex-wrap">
                      <Badge variant="muted" className="text-[9px] h-3.5 px-1">{zone.platform}</Badge>
                      <Badge variant="muted" className="text-[9px] h-3.5 px-1">{zone.size}</Badge>
                      {mismatch && <Badge className="text-[9px] h-3.5 px-1 bg-red-100 text-red-600 border-red-200">⚠ Ratio</Badge>}
                      {live && <Badge className="text-[9px] h-3.5 px-1 bg-green-100 text-green-700 border-green-200">● Live</Badge>}
                    </div>
                    {assignedFile && (
                      <p className="text-[10px] text-muted-foreground mt-0.5 truncate">
                        🎨 {assignedFile.name}{assignedFile.width ? ` · ${assignedFile.width}×${assignedFile.height}px` : ''}
                      </p>
                    )}
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className="text-xs font-bold">{budgetPerZone.toFixed(1)}M</p>
                    <p className="text-[10px] text-muted-foreground">≈{fmtImp(imp)} imps</p>
                    <p className="text-[10px] text-amber-600">CPM {fmtVnd(zone.cpm)}đ</p>
                  </div>
                </div>
                <div className="flex items-center gap-2 pl-1 flex-wrap">
                  {zone.adspilotUrl && (
                    <a href={zone.adspilotUrl} target="_blank" rel="noreferrer"
                      className="flex items-center gap-1 text-[10px] text-brand-600 hover:underline font-medium">
                      <ExternalLink className="w-2.5 h-2.5" /> AdsPilot
                    </a>
                  )}
                  {zone.siteUrl && (
                    <a href={zone.siteUrl} target="_blank" rel="noreferrer"
                      className="flex items-center gap-1 text-[10px] text-blue-600 hover:underline font-medium">
                      <Globe className="w-2.5 h-2.5" /> Test site
                    </a>
                  )}
                </div>
              </div>
            )
          })}
        </CardContent>
      </Card>
    </div>
  )
}
