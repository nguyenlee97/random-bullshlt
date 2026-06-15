import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { fmt } from '@/lib/utils'
import {
  CheckCircle2, TrendingUp, Users, DollarSign, LayoutGrid,
  BarChart2, Eye, MousePointerClick, ExternalLink, Film,
  Camera, Loader2, Globe, Monitor,
} from 'lucide-react'
import { getSelectedZones, fmtVnd, fmtImp, estImpressions, checkMismatch } from './setup/setupUtils'
import { ALL_ZONES } from '@/data/zones'

// ─── Check if campaign is already live (start date ≤ today) ───────────────────
function isLive(brief) {
  if (!brief?.startDate) return false
  return new Date(brief.startDate) <= new Date()
}

// ─── Mock screenshot capture (simulate agent puppeteer call) ──────────────────
function ScreenshotCapture({ zone, brief }) {
  const [state, setState] = useState('idle') // idle | loading | done
  const [mockImg, setMockImg] = useState(null)

  const capture = async () => {
    setState('loading')
    await new Promise(r => setTimeout(r, 2500))
    // Use a placeholder image from picsum with zone-specific seed
    const seed = zone.id.split('.').join('')
    setMockImg(`https://picsum.photos/seed/${seed}/400/200`)
    setState('done')
  }

  if (!zone.siteUrl) return (
    <div className="text-[10px] text-muted-foreground italic">Platform không có test site URL</div>
  )

  return (
    <div className="space-y-1.5">
      {state === 'idle' && (
        <button onClick={capture}
          className="flex items-center gap-1.5 text-[10px] font-semibold text-violet-600 hover:text-violet-700 hover:underline">
          <Camera className="w-3 h-3" />
          Chụp screenshot quảng cáo đang live
        </button>
      )}
      {state === 'loading' && (
        <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
          <Loader2 className="w-3 h-3 animate-spin" />
          Agent đang chụp screenshot {zone.siteUrl}...
        </div>
      )}
      {state === 'done' && mockImg && (
        <div className="space-y-1">
          <p className="text-[10px] text-brand-600 font-semibold flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3" /> Screenshot captured
          </p>
          <img
            src={mockImg}
            alt={`Screenshot ${zone.name}`}
            className="rounded-md border border-border w-full max-w-[200px] object-cover"
            onError={e => { e.target.style.display = 'none' }}
          />
        </div>
      )}
    </div>
  )
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

export default function SuccessStep({ brief, zones, selectedZoneIds, audienceSize, setup, allZones }) {
  const ids = selectedZoneIds || []
  // Use real API zones (from setup state) — fall back to static ALL_ZONES
  const catalog = allZones?.length ? allZones : ALL_ZONES
  const selectedZones = catalog.filter(z => ids.includes(z.id))
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

  // AdsPilot base URL
  const ADSPILOT_URL = 'https://adspilot.pawgrammers.io.vn'
  const ADSPILOT_ORDERS = `${ADSPILOT_URL}/#/orders`

  return (
    <div className="space-y-4">
      {/* Hero banner */}
      <div className="rounded-2xl bg-gradient-to-br from-brand-500 to-violet-600 p-5 text-white shadow-lg">
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
      <Card className="border-brand-200">
        <CardHeader className="pb-2 pt-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <Monitor className="w-4 h-4 text-brand-500" />
            Liên kết nhanh
          </CardTitle>
        </CardHeader>
        <CardContent className="pb-3 pt-0 space-y-2">
          {/* AdsPilot link */}
          <a
            href={ADSPILOT_ORDERS}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-2.5 p-2.5 rounded-lg border border-brand-200 bg-brand-50 hover:bg-brand-100 transition-colors group"
          >
            <div className="w-8 h-8 rounded-lg bg-brand-500 flex items-center justify-center flex-shrink-0">
              <LayoutGrid className="w-4 h-4 text-white" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-bold text-brand-700">Xem trong AdsPilot</p>
              <p className="text-[10px] text-brand-500 truncate">{ADSPILOT_ORDERS}</p>
            </div>
            <ExternalLink className="w-3.5 h-3.5 text-brand-400 group-hover:text-brand-600 flex-shrink-0" />
          </a>

          {/* Site links (unique platforms) */}
          {[...new Map(selectedZones.filter(z => z.siteUrl).map(z => [z.platform, z])).values()].map(zone => (
            <a key={zone.platform}
              href={zone.siteUrl}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-2.5 p-2.5 rounded-lg border border-border hover:border-brand-300 hover:bg-brand-50/40 transition-colors group"
            >
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

      {/* KPI grid */}
      <div className="grid grid-cols-2 gap-2">
        <KpiCard icon={LayoutGrid} label="Ad zones" value={selectedZones.length} color="text-brand-600" bg="bg-brand-50 border-brand-200" />
        <KpiCard icon={Users} label="Audience" value={fmt(audienceSize || 0)} sub="người dùng" color="text-blue-600" bg="bg-blue-50 border-blue-200" />
        <KpiCard icon={DollarSign} label="Ngân sách" value={`${brief?.budget}M`} sub="VND" color="text-violet-600" bg="bg-violet-50 border-violet-200" />
        <KpiCard icon={Eye} label="Est. Impressions" value={fmtImp(totalEstImps)} color="text-green-600" bg="bg-green-50 border-green-200" />
        <KpiCard icon={MousePointerClick} label="Avg CTR" value={`${avgCTR}%`} color="text-amber-600" bg="bg-amber-50 border-amber-200" />
        <KpiCard icon={BarChart2} label="Avg Viewability" value={`${avgVI}%`} color="text-pink-600" bg="bg-pink-50 border-pink-200" />
      </div>

      {/* Zone breakdown + screenshots */}
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
                {/* Zone header */}
                <div className="flex items-start gap-2.5">
                  {/* Thumbnail */}
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

                {/* Links + screenshot capture */}
                <div className="flex items-start justify-between pl-1 flex-wrap gap-2">
                  <div className="flex items-center gap-2 flex-wrap">
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

                  {/* Screenshot capture for live ads */}
                  {live && <ScreenshotCapture zone={zone} brief={brief} />}
                </div>
              </div>
            )
          })}
        </CardContent>
      </Card>
    </div>
  )
}
