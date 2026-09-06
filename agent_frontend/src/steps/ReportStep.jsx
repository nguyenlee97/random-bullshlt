import { useState, useEffect, useCallback, useRef } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { AgentAPI } from '@/api/agentApi'
import {
  BarChart, Bar, LineChart, Line, AreaChart, Area, ComposedChart,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  PieChart, Pie, Cell, ScatterChart, Scatter, ZAxis,
  ReferenceLine, ReferenceArea,
} from 'recharts'
import {
  BarChart2, Loader2, TrendingUp, TrendingDown, Minus, CheckCircle2,
  Activity, Eye, MousePointerClick, DollarSign, RefreshCw, Users, Target,
  AlertCircle, Zap, Download, FileText,
} from 'lucide-react'

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:3000'

// ─── Report tab config ───────────────────────────────────────────────────────
const REPORT_TABS = [
  { id: 'daily_ops',     label: 'Tổng quan',      icon: Activity,           color: '#3b82f6' },
  { id: 'awareness',     label: 'Awareness',      icon: Eye,                color: '#8b5cf6' },
  { id: 'consideration', label: 'Consideration',  icon: MousePointerClick,  color: '#f59e0b' },
  { id: 'conversion',    label: 'Conversion',     icon: Target,             color: '#10b981' },
  { id: 'retention',     label: 'Retention',      icon: RefreshCw,          color: '#ec4899' },
  { id: 'executive',     label: 'Executive',      icon: DollarSign,         color: '#6366f1' },
]

// ─── Number formatters ───────────────────────────────────────────────────────
const fmtN = (n) => {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}
const fmtVND = (n) => {
  if (n >= 1_000_000_000) return (n / 1_000_000_000).toFixed(1) + 'B ₫'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M ₫'
  if (n >= 1_000) return (n / 1_000).toFixed(0) + 'K ₫'
  return n + ' ₫'
}

// ─── KPI Scorecard ───────────────────────────────────────────────────────────
function KPIScorecard({ records }) {
  if (!records?.length) return null
  const totals = records.reduce((a, r) => {
    a.imp += r.impressions || 0
    a.clk += r.clicks || 0
    a.spend += r.spend || 0
    a.conv += r.conversions || 0
    a.reach += r.reach || 0
    a.viWeighted += (r.vi || 0) * (r.impressions || 0)
    a.n++
    return a
  }, { imp: 0, clk: 0, spend: 0, conv: 0, reach: 0, viWeighted: 0, n: 0 })

  const avgCTR = totals.imp > 0 ? (totals.clk / totals.imp * 100).toFixed(2) : '0'
  const avgVI = totals.imp > 0 ? (totals.viWeighted / totals.imp).toFixed(1) : '0'
  const avgCPM = totals.imp > 0 ? Math.round(totals.spend / totals.imp * 1000) : 0

  const kpis = [
    { label: 'Impressions', value: fmtN(totals.imp), icon: Eye, color: 'text-blue-600', bg: 'bg-blue-50 border-blue-200' },
    { label: 'Clicks', value: fmtN(totals.clk), icon: MousePointerClick, color: 'text-amber-600', bg: 'bg-amber-50 border-amber-200' },
    { label: 'CTR', value: avgCTR + '%', icon: TrendingUp, color: 'text-green-600', bg: 'bg-green-50 border-green-200' },
    { label: 'Spend', value: fmtVND(totals.spend), icon: DollarSign, color: 'text-violet-600', bg: 'bg-violet-50 border-violet-200' },
    { label: 'Daily reach (sum)', value: fmtN(totals.reach), icon: Users, color: 'text-pink-600', bg: 'bg-pink-50 border-pink-200' },
    { label: 'Viewability', value: avgVI + '%', icon: Activity, color: 'text-cyan-600', bg: 'bg-cyan-50 border-cyan-200' },
  ]

  return (
    <div className="grid grid-cols-3 gap-2 mb-4">
      {kpis.map(({ label, value, icon: Icon, color, bg }) => (
        <div key={label} className={`rounded-xl border p-2.5 ${bg}`}>
          <div className="flex items-center gap-1.5 mb-1">
            <Icon className={`w-3.5 h-3.5 ${color}`} />
            <span className="text-[10px] font-semibold text-muted-foreground uppercase">{label}</span>
          </div>
          <p className={`text-lg font-black ${color}`}>{value}</p>
        </div>
      ))}
    </div>
  )
}

const STATUS_STYLE = {
  good: { label: 'GOOD', badge: 'bg-emerald-100 text-emerald-800', border: 'border-emerald-200', bar: 'bg-emerald-500' },
  watch: { label: 'WATCH', badge: 'bg-amber-100 text-amber-900', border: 'border-amber-200', bar: 'bg-amber-500' },
  bad: { label: 'BAD', badge: 'bg-red-100 text-red-800', border: 'border-red-200', bar: 'bg-red-500' },
}

function BusinessPerformance({ contract }) {
  if (contract?.contractVersion !== 'report-evidence-v2') return null
  const performanceStatus = contract.performanceStatus || { status: 'watch', counts: {} }
  const overallStyle = STATUS_STYLE[performanceStatus.status] || STATUS_STYLE.watch
  const kpiScorecard = contract.kpiScorecard || []
  const funnel = contract.businessFunnel || []
  const actions = contract.actions || []
  const funnelMax = Math.max(1, ...funnel.map(item => Number(item.value || 0)))

  return (
    <div className="mb-4 space-y-3" data-testid="report-business-performance">
      <Card className={`${overallStyle.border} bg-white`}>
        <CardContent className="py-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Hiệu quả theo KPI trong brief</p>
              <p className="mt-1 text-sm font-bold text-slate-900">{performanceStatus.summary}</p>
            </div>
            <span className={`rounded-full px-3 py-1 text-xs font-black ${overallStyle.badge}`}>{overallStyle.label}</span>
          </div>
        </CardContent>
      </Card>

      {kpiScorecard.length > 0 && (
        <div className="grid gap-2 sm:grid-cols-2" data-testid="report-kpi-scorecard">
          {kpiScorecard.map(kpi => {
            const style = STATUS_STYLE[kpi.status] || STATUS_STYLE.watch
            const actual = kpi.unit === 'VND' ? fmtVND(kpi.actual || 0)
              : kpi.unit === 'percent' ? `${Number(kpi.actual || 0).toFixed(1)}%`
              : fmtN(kpi.actual || 0)
            const target = kpi.unit === 'VND' ? fmtVND(kpi.target || 0)
              : kpi.unit === 'percent' ? `${kpi.target}%` : fmtN(kpi.target || 0)
            return (
              <article key={kpi.id} className={`rounded-xl border bg-white p-3 ${style.border}`}>
                <div className="flex items-start justify-between gap-2">
                  <p className="text-xs font-bold leading-5 text-slate-900">{kpi.label}</p>
                  <span className={`rounded-full px-2 py-0.5 text-[9px] font-black ${style.badge}`}>{style.label}</span>
                </div>
                <p className="mt-2 text-lg font-black text-slate-950">{actual}</p>
                <p className="text-[10px] text-slate-500">Mục tiêu {kpi.operator} {target} · Mức đạt {kpi.attainment ?? '—'}%</p>
              </article>
            )
          })}
        </div>
      )}

      {funnel.length > 0 && (
        <Card data-testid="report-business-funnel">
          <CardHeader className="pb-2"><CardTitle className="text-sm">Business outcome funnel</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {funnel.map((item, index) => (
              <div key={item.eventId} className="grid grid-cols-[minmax(120px,1fr)_2fr_auto] items-center gap-2">
                <span className="truncate text-[11px] font-semibold text-slate-700">{index + 1}. {item.label}</span>
                <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                  <div className="h-full rounded-full bg-brand-500" style={{ width: `${Math.max(2, item.value / funnelMax * 100)}%` }} />
                </div>
                <strong className="min-w-12 text-right text-[11px] text-slate-900">{fmtN(item.value)}</strong>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {actions.length > 0 && (
        <Card className="border-slate-200" data-testid="report-actions">
          <CardHeader className="pb-2"><CardTitle className="text-sm">Action ưu tiên có kiểm chứng</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {actions.map(action => {
              const style = STATUS_STYLE[action.status] || STATUS_STYLE.watch
              return (
                <article key={action.id} className={`rounded-xl border p-3 ${style.border}`}>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`rounded-full px-2 py-0.5 text-[9px] font-black ${style.badge}`}>{action.priority?.toUpperCase()}</span>
                    <p className="text-xs font-bold text-slate-900">{action.problem}</p>
                  </div>
                  <p className="mt-2 text-xs leading-5 text-slate-700">{action.proposedAction}</p>
                  <p className="mt-1 text-[10px] leading-4 text-slate-500"><strong>Guardrail:</strong> {action.guardrail} · <strong>Đánh giá lại:</strong> {action.nextReviewWindow}</p>
                </article>
              )
            })}
          </CardContent>
        </Card>
      )}
    </div>
  )
}

// ─── Daily Trend Chart ───────────────────────────────────────────────────────
function DailyTrendChart({ records, title, dataKey1, dataKey2, color1, color2, type = 'bar', refLine = false, rightKey = null, rightColor = '#f59e0b' }) {
  const byDate = {}
  records.forEach(r => {
    if (!byDate[r.date]) byDate[r.date] = { date: r.date, imp: 0, clk: 0, spend: 0, conv: 0, reach: 0, n: 0 }
    const d = byDate[r.date]
    d.imp   += r.impressions || 0
    d.clk   += r.clicks      || 0
    d.spend += r.spend       || 0
    d.conv  += r.conversions || 0
    d.reach += r.reach       || 0
    d.n++
  })
  const data = Object.values(byDate)
    .sort((a, b) => a.date.localeCompare(b.date))
    .map(d => ({
      ...d,
      date: d.date.slice(5),
      ctr: d.imp > 0 ? +(d.clk / d.imp * 100).toFixed(2) : 0,
      cpm: d.imp > 0 ? Math.round(d.spend / d.imp * 1000) : 0,
    }))

  const k1 = dataKey1 || 'imp'
  const k2 = dataKey2 || null
  const c1 = color1 || '#3b82f6'
  const c2 = color2 || '#10b981'
  const avg1 = data.length ? data.reduce((s, d) => s + (d[k1] || 0), 0) / data.length : 0
  const useComposed = !!(rightKey || (type === 'bar' && k2))
  const margin = { top: 4, right: rightKey ? 30 : 8, bottom: 0, left: -20 }

  return (
    <Card className="mb-3">
      <CardHeader className="pb-1 pt-3">
        <CardTitle className="text-xs text-muted-foreground">{title || 'Daily Trend'}</CardTitle>
      </CardHeader>
      <CardContent className="pt-0 pb-2">
        <ResponsiveContainer width="100%" height={165}>
          {useComposed ? (
            <ComposedChart data={data} margin={margin}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 9 }} />
              <YAxis yAxisId="left" tick={{ fontSize: 9 }} />
              {rightKey && <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 9 }} />}
              <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
              <Legend wrapperStyle={{ fontSize: 10 }} />
              {refLine && <ReferenceLine yAxisId="left" y={avg1} stroke={c1} strokeDasharray="5 3" strokeOpacity={0.6} />}
              <Bar yAxisId="left" dataKey={k1} name={k1} fill={c1} radius={[3,3,0,0]} />
              {k2 && !rightKey && <Bar yAxisId="left" dataKey={k2} name={k2} fill={c2} radius={[3,3,0,0]} />}
              {rightKey && <Line yAxisId="right" type="monotone" dataKey={rightKey} name={rightKey} stroke={rightColor} strokeWidth={2} dot={{ r: 3 }} />}
            </ComposedChart>
          ) : type === 'area' ? (
            <AreaChart data={data} margin={margin}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 9 }} />
              <YAxis tick={{ fontSize: 9 }} />
              <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
              {refLine && <ReferenceLine y={avg1} stroke={c1} strokeDasharray="5 3" strokeOpacity={0.6} />}
              <Area type="monotone" dataKey={k1} stroke={c1} fill={c1} fillOpacity={0.15} strokeWidth={2} dot={{ r: 2 }} />
              {k2 && <Area type="monotone" dataKey={k2} stroke={c2} fill={c2} fillOpacity={0.1} strokeWidth={2} dot={{ r: 2 }} />}
            </AreaChart>
          ) : type === 'line' ? (
            <LineChart data={data} margin={margin}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 9 }} />
              <YAxis tick={{ fontSize: 9 }} />
              <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
              <Legend wrapperStyle={{ fontSize: 10 }} />
              {refLine && <ReferenceLine y={avg1} stroke={c1} strokeDasharray="5 3" strokeOpacity={0.7} label={{ value: 'avg', fontSize: 8 }} />}
              <Line type="monotone" dataKey={k1} stroke={c1} strokeWidth={2} dot={{ r: 3 }} />
              {k2 && <Line type="monotone" dataKey={k2} stroke={c2} strokeWidth={2} dot={{ r: 3 }} />}
            </LineChart>
          ) : (
            <BarChart data={data} margin={margin}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 9 }} />
              <YAxis tick={{ fontSize: 9 }} />
              <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
              <Legend wrapperStyle={{ fontSize: 10 }} />
              {refLine && <ReferenceLine y={avg1} stroke={c1} strokeDasharray="5 3" strokeOpacity={0.7} />}
              <Bar dataKey={k1} fill={c1} radius={[3,3,0,0]} />
              {k2 && <Bar dataKey={k2} fill={c2} radius={[3,3,0,0]} />}
            </BarChart>
          )}
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}

// ─── Zone Performance Table ──────────────────────────────────────────────────
function ZoneTable({ records }) {
  const zoneMap = {}
  records.forEach(r => {
    if (!zoneMap[r.placementId]) zoneMap[r.placementId] = { id: r.placementId, ch: r.channel, fmt: r.format, imp: 0, clk: 0, spend: 0, conv: 0, viS: 0, n: 0 }
    const z = zoneMap[r.placementId]
    z.imp += r.impressions || 0
    z.clk += r.clicks || 0
    z.spend += r.spend || 0
    z.conv += r.conversions || 0
    z.viS += r.vi || 0
    z.n++
  })
  const zones = Object.values(zoneMap).sort((a, b) => b.imp - a.imp)

  return (
    <Card className="mb-3">
      <CardHeader className="pb-1 pt-3">
        <CardTitle className="text-xs text-muted-foreground">📊 Zone Performance</CardTitle>
      </CardHeader>
      <CardContent className="pt-0 pb-2">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-1.5 px-1 font-semibold text-muted-foreground">Zone</th>
                <th className="text-right py-1.5 px-1 font-semibold text-muted-foreground">Imps</th>
                <th className="text-right py-1.5 px-1 font-semibold text-muted-foreground">CTR</th>
                <th className="text-right py-1.5 px-1 font-semibold text-muted-foreground">VI%</th>
                <th className="text-right py-1.5 px-1 font-semibold text-muted-foreground">CPM</th>
                <th className="text-right py-1.5 px-1 font-semibold text-muted-foreground">Spend</th>
                <th className="text-right py-1.5 px-1 font-semibold text-muted-foreground">Conv</th>
              </tr>
            </thead>
            <tbody>
              {zones.map(z => (
                <tr key={z.id} className="border-b border-border/50 hover:bg-muted/50">
                  <td className="py-1.5 px-1 font-medium">{z.id.replace(/_/g, ' ')}</td>
                  <td className="py-1.5 px-1 text-right">{fmtN(z.imp)}</td>
                  <td className="py-1.5 px-1 text-right">{z.imp > 0 ? (z.clk / z.imp * 100).toFixed(2) : '0'}%</td>
                  <td className="py-1.5 px-1 text-right">{z.n > 0 ? (z.viS / z.n).toFixed(1) : '0'}%</td>
                  <td className="py-1.5 px-1 text-right">{z.imp > 0 ? fmtVND(Math.round(z.spend / z.imp * 1000)) : '—'}</td>
                  <td className="py-1.5 px-1 text-right">{fmtVND(z.spend)}</td>
                  <td className="py-1.5 px-1 text-right">{z.conv}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  )
}

// ─── Zone Bar Chart ──────────────────────────────────────────────────────────
function ZoneBarChart({ records, dataKey = 'imp', label = 'Impressions', color = '#6366f1' }) {
  const zoneMap = {}
  records.forEach(r => {
    if (!zoneMap[r.placementId]) zoneMap[r.placementId] = { name: r.placementId.replace(/_/g, ' ').slice(0, 14), imp: 0, clk: 0, spend: 0, conv: 0 }
    const z = zoneMap[r.placementId]
    z.imp += r.impressions || 0
    z.clk += r.clicks || 0
    z.spend += r.spend || 0
    z.conv += r.conversions || 0
  })
  const data = Object.values(zoneMap).sort((a, b) => b[dataKey] - a[dataKey])
  return (
    <Card className="mb-3">
      <CardHeader className="pb-1 pt-3">
        <CardTitle className="text-xs text-muted-foreground">📊 {label} by Zone</CardTitle>
      </CardHeader>
      <CardContent className="pt-0 pb-2">
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={data} layout="vertical" margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
            <XAxis type="number" tick={{ fontSize: 9 }} />
            <YAxis type="category" dataKey="name" tick={{ fontSize: 9 }} width={90} />
            <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
            <Bar dataKey={dataKey} fill={color} radius={[0, 3, 3, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}

// ─── Grouped Zone Bar ────────────────────────────────────────────────────────
// Clustered bar: imp + clicks side-by-side per top zones
function GroupedZoneBar({ records, title = '📊 Performance by Zone' }) {
  const map = {}
  records.forEach(r => {
    if (!map[r.placementId]) map[r.placementId] = { name: r.placementId.replace(/_/g,  ' ').slice(0, 14), imp: 0, clk: 0 }
    map[r.placementId].imp += r.impressions || 0
    map[r.placementId].clk += r.clicks      || 0
  })
  const data = Object.values(map).sort((a, b) => b.imp - a.imp).slice(0, 8)
  return (
    <Card className="mb-3">
      <CardHeader className="pb-1 pt-3"><CardTitle className="text-xs text-muted-foreground">{title}</CardTitle></CardHeader>
      <CardContent className="pt-0 pb-2">
        <ResponsiveContainer width="100%" height={165}>
          <BarChart data={data} margin={{ top: 4, right: 8, bottom: 20, left: -20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="name" tick={{ fontSize: 8 }} angle={-20} textAnchor="end" interval={0} />
            <YAxis tick={{ fontSize: 9 }} />
            <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
            <Legend wrapperStyle={{ fontSize: 10 }} />
            <Bar dataKey="imp" name="Impressions" fill="#3b82f6" radius={[3,3,0,0]} />
            <Bar dataKey="clk" name="Clicks"      fill="#f59e0b" radius={[3,3,0,0]} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}

// ─── Color-Coded Horizontal Bar Chart ─────────────────────────────────────────
// green = top third, yellow = mid, red = bottom third (inverted for CPA: lower=better)
function ColorHBarChart({ records, metricFn, labelFn, title, invert = false }) {
  const map = {}
  records.forEach(r => { if (!map[r.placementId]) map[r.placementId] = { id: r.placementId, ...( {_r: []} ) }; map[r.placementId]._r.push(r) })
  let data = Object.values(map).map(z => ({ name: z.id.replace(/_/g, ' ').slice(0, 18), value: metricFn(z._r), label: labelFn ? labelFn(z._r) : null }))
    .filter(d => d.value > 0).sort((a, b) => b.value - a.value).slice(0, 10)
  const max = data[0]?.value || 1
  const color = (v) => {
    const p = v / max
    if (invert) return p > 0.66 ? '#ef4444' : p > 0.33 ? '#f59e0b' : '#10b981'
    return p > 0.66 ? '#10b981' : p > 0.33 ? '#f59e0b' : '#ef4444'
  }
  return (
    <Card className="mb-3">
      <CardHeader className="pb-1 pt-3"><CardTitle className="text-xs text-muted-foreground">{title}</CardTitle></CardHeader>
      <CardContent className="pt-0 pb-3 space-y-1.5">
        {data.map(d => (
          <div key={d.name}>
            <div className="flex justify-between text-[10px] mb-0.5">
              <span className="text-foreground font-medium truncate max-w-[55%]">{d.name}</span>
              <span className="text-muted-foreground">{d.label || d.value.toFixed(2)}</span>
            </div>
            <div className="h-3.5 bg-muted rounded-sm overflow-hidden">
              <div className="h-full rounded-sm" style={{ width: `${(d.value / max * 100)}%`, background: color(d.value) }} />
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

// ─── Multi-Zone Line Chart ────────────────────────────────────────────────────
// CTR trend per top N zones over time (consideration tab)
function MultiZoneLineChart({ records, title = '🖱 CTR Trend — Top Placements', maxZones = 5 }) {
  const ZONE_COLORS = ['#3b82f6','#10b981','#f59e0b','#8b5cf6','#ec4899']
  // Pick top N zones by total impressions
  const totals = {}
  records.forEach(r => { totals[r.placementId] = (totals[r.placementId] || 0) + (r.impressions || 0) })
  const topZones = Object.entries(totals).sort(([,a],[,b]) => b - a).slice(0, maxZones).map(([id]) => id)
  // Build date × zone matrix
  const byDate = {}
  records.forEach(r => {
    if (!topZones.includes(r.placementId)) return
    if (!byDate[r.date]) byDate[r.date] = { date: r.date.slice(5) }
    const key = r.placementId.replace(/_/g, ' ').slice(0, 12)
    if (!byDate[r.date][key]) byDate[r.date][key] = { imp: 0, clk: 0 }
    byDate[r.date][key].imp += r.impressions || 0
    byDate[r.date][key].clk += r.clicks      || 0
  })
  const zoneLabels = topZones.map(id => id.replace(/_/g, ' ').slice(0, 12))
  const data = Object.values(byDate).sort((a, b) => a.date.localeCompare(b.date)).map(d => {
    const out = { date: d.date }
    zoneLabels.forEach(z => { out[z] = d[z]?.imp > 0 ? +(d[z].clk / d[z].imp * 100).toFixed(2) : 0 })
    return out
  })
  return (
    <Card className="mb-3">
      <CardHeader className="pb-1 pt-3"><CardTitle className="text-xs text-muted-foreground">{title}</CardTitle></CardHeader>
      <CardContent className="pt-0 pb-2">
        <ResponsiveContainer width="100%" height={165}>
          <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="date" tick={{ fontSize: 9 }} />
            <YAxis tick={{ fontSize: 9 }} unit="%" />
            <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} formatter={v => v.toFixed(2) + '%'} />
            <Legend wrapperStyle={{ fontSize: 9 }} />
            {zoneLabels.map((z, i) => (
              <Line key={z} type="monotone" dataKey={z} stroke={ZONE_COLORS[i % ZONE_COLORS.length]} strokeWidth={1.5} dot={{ r: 2 }} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}

// ─── Stacked Zone Bar ─────────────────────────────────────────────────────────
// Daily clicks stacked by zone (consideration tab)
function StackedZoneBar({ records, title = '📊 Daily Click Volume by Zone', dataKey = 'clk', maxZones = 5 }) {
  const ZONE_COLORS = ['#3b82f6','#10b981','#f59e0b','#8b5cf6','#ec4899','#06b6d4','#f43f5e']
  const totals = {}
  records.forEach(r => { totals[r.placementId] = (totals[r.placementId] || 0) + (r.clicks || 0) })
  const topZones = Object.entries(totals).sort(([,a],[,b]) => b - a).slice(0, maxZones).map(([id]) => id)
  const byDate = {}
  records.forEach(r => {
    if (!topZones.includes(r.placementId)) return
    if (!byDate[r.date]) byDate[r.date] = { date: r.date.slice(5) }
    const key = r.placementId.replace(/_/g, ' ').slice(0, 12)
    byDate[r.date][key] = (byDate[r.date][key] || 0) + (r.clicks || 0)
  })
  const zoneLabels = topZones.map(id => id.replace(/_/g, ' ').slice(0, 12))
  const data = Object.values(byDate).sort((a, b) => a.date.localeCompare(b.date))
  return (
    <Card className="mb-3">
      <CardHeader className="pb-1 pt-3"><CardTitle className="text-xs text-muted-foreground">{title}</CardTitle></CardHeader>
      <CardContent className="pt-0 pb-2">
        <ResponsiveContainer width="100%" height={165}>
          <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="date" tick={{ fontSize: 9 }} />
            <YAxis tick={{ fontSize: 9 }} />
            <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
            <Legend wrapperStyle={{ fontSize: 9 }} />
            {zoneLabels.map((z, i) => (
              <Bar key={z} dataKey={z} stackId="a" fill={ZONE_COLORS[i % ZONE_COLORS.length]} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}

// ─── Scatter Bubble Chart ─────────────────────────────────────────────────────
// X=CPM, Y=CTR, Z=spend bubble size — efficiency quadrant per zone
function ScatterBubbleChart({ records, title = '🔵 CTR vs CPM — Efficiency Scatter' }) {
  const map = {}
  records.forEach(r => {
    if (!map[r.placementId]) map[r.placementId] = { id: r.placementId.slice(0, 14), imp: 0, clk: 0, spend: 0 }
    map[r.placementId].imp   += r.impressions || 0
    map[r.placementId].clk   += r.clicks      || 0
    map[r.placementId].spend += r.spend       || 0
  })
  const data = Object.values(map).filter(z => z.imp > 0).map(z => ({
    name:  z.id,
    cpm:   Math.round(z.spend / z.imp * 1000),
    ctr:   +(z.clk / z.imp * 100).toFixed(3),
    spend: Math.round(z.spend / 1_000_000),
  }))
  return (
    <Card className="mb-3">
      <CardHeader className="pb-1 pt-3"><CardTitle className="text-xs text-muted-foreground">{title}</CardTitle></CardHeader>
      <CardContent className="pt-0 pb-2">
        <ResponsiveContainer width="100%" height={165}>
          <ScatterChart margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="cpm" name="CPM" tick={{ fontSize: 9 }} label={{ value: 'CPM (₫)', fontSize: 8, offset: -5, position: 'insideBottom' }} />
            <YAxis dataKey="ctr" name="CTR" tick={{ fontSize: 9 }} unit="%" />
            <ZAxis dataKey="spend" range={[40, 300]} name="Spend (M₫)" />
            <Tooltip cursor={{ strokeDasharray: '3 3' }} contentStyle={{ fontSize: 11, borderRadius: 8 }}
              content={({ payload }) => payload?.[0] ? (
                <div className="bg-white border border-border rounded-lg p-2 text-xs shadow">
                  <p className="font-bold mb-1">{payload[0].payload.name}</p>
                  <p>CPM: {fmtVND(payload[0].payload.cpm)}</p>
                  <p>CTR: {payload[0].payload.ctr}%</p>
                  <p>Spend: {payload[0].payload.spend}M₫</p>
                </div>
              ) : null}
            />
            <Scatter data={data} fill="#6366f1" fillOpacity={0.7} />
          </ScatterChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}

// ─── Donut Pie Chart ──────────────────────────────────────────────────────────
// Budget allocation by zone as donut — executive tab
function DonutPieChart({ records, title = '🍩 Budget Allocation by Zone' }) {
  const COLORS = ['#3b82f6','#10b981','#f59e0b','#8b5cf6','#ec4899','#06b6d4','#f43f5e','#6366f1']
  const map = {}
  records.forEach(r => { map[r.placementId] = (map[r.placementId] || 0) + (r.spend || 0) })
  const data = Object.entries(map)
    .sort(([,a],[,b]) => b - a).slice(0, 8)
    .map(([id, spend]) => ({ name: id.replace(/_/g, ' ').slice(0, 16), value: Math.round(spend / 1000) }))
  const total = data.reduce((s, d) => s + d.value, 0)
  return (
    <Card className="mb-3">
      <CardHeader className="pb-1 pt-3"><CardTitle className="text-xs text-muted-foreground">{title}</CardTitle></CardHeader>
      <CardContent className="pt-0 pb-2">
        <div className="flex items-center gap-3">
          <ResponsiveContainer width="50%" height={165}>
            <PieChart>
              <Pie data={data} cx="50%" cy="50%" innerRadius={45} outerRadius={70} paddingAngle={3} dataKey="value">
                {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} formatter={(v) => [fmtVND(v * 1000), 'Spend']} />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex-1 space-y-1 text-[10px]">
            {data.map((d, i) => (
              <div key={d.name} className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{ background: COLORS[i % COLORS.length] }} />
                <span className="truncate text-foreground">{d.name}</span>
                <span className="ml-auto text-muted-foreground font-medium">{total > 0 ? (d.value / total * 100).toFixed(0) : 0}%</span>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

// ─── Spend Pacing Chart ──────────────────────────────────────────────────────
function SpendPacingChart({ records }) {
  const byDate = {}
  let cumSpend = 0
  records.forEach(r => {
    if (!byDate[r.date]) byDate[r.date] = { date: r.date, daily: 0 }
    byDate[r.date].daily += r.spend || 0
  })
  const data = Object.values(byDate)
    .sort((a, b) => a.date.localeCompare(b.date))
    .map(d => {
      cumSpend += d.daily
      return { date: d.date.slice(5), daily: Math.round(d.daily / 1000), cumulative: Math.round(cumSpend / 1000) }
    })
  return (
    <Card className="mb-3">
      <CardHeader className="pb-1 pt-3">
        <CardTitle className="text-xs text-muted-foreground">💰 Spend Pacing (K ₫/ngày + Lũy kế)</CardTitle>
      </CardHeader>
      <CardContent className="pt-0 pb-2">
        <ResponsiveContainer width="100%" height={160}>
          <ComposedChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="date" tick={{ fontSize: 9 }} />
            <YAxis yAxisId="left" tick={{ fontSize: 9 }} />
            <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 9 }} />
            <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} formatter={(v, n) => [v + 'K ₫', n]} />
            <Legend wrapperStyle={{ fontSize: 10 }} />
            <Bar yAxisId="left" dataKey="daily" name="Daily Spend" fill="#6366f1" radius={[3,3,0,0]} />
            <Line yAxisId="right" type="monotone" dataKey="cumulative" name="Cumulative" stroke="#f59e0b" strokeWidth={2} dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}

// ─── Conversion Funnel ───────────────────────────────────────────────────────
function ConversionFunnel({ records }) {
  const totals = records.reduce((a, r) => {
    a.imp += r.impressions || 0
    a.clk += r.clicks || 0
    a.conv += r.conversions || 0
    return a
  }, { imp: 0, clk: 0, conv: 0 })
  const data = [
    { name: 'Impressions', value: totals.imp, fill: '#6366f1' },
    { name: 'Clicks', value: totals.clk, fill: '#3b82f6' },
    { name: 'Conversions', value: totals.conv, fill: '#10b981' },
  ]
  const max = totals.imp || 1
  return (
    <Card className="mb-3">
      <CardHeader className="pb-1 pt-3">
        <CardTitle className="text-xs text-muted-foreground">🎯 Conversion Funnel</CardTitle>
      </CardHeader>
      <CardContent className="pt-0 pb-3">
        <div className="space-y-2">
          {data.map(d => (
            <div key={d.name}>
              <div className="flex justify-between text-xs mb-0.5">
                <span className="font-medium">{d.name}</span>
                <span className="text-muted-foreground">{fmtN(d.value)} ({(d.value / max * 100).toFixed(1)}%)</span>
              </div>
              <div className="h-5 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{ width: `${(d.value / max * 100)}%`, background: d.fill }}
                />
              </div>
            </div>
          ))}
        </div>
        <div className="grid grid-cols-3 gap-2 mt-3 text-center">
          <div className="text-[10px] text-muted-foreground">
            <p className="font-bold text-sm text-foreground">{totals.imp > 0 ? (totals.clk / totals.imp * 100).toFixed(2) : 0}%</p>
            CTR
          </div>
          <div className="text-[10px] text-muted-foreground">
            <p className="font-bold text-sm text-foreground">{totals.clk > 0 ? (totals.conv / totals.clk * 100).toFixed(2) : 0}%</p>
            CVR
          </div>
          <div className="text-[10px] text-muted-foreground">
            <p className="font-bold text-sm text-foreground">{totals.conv > 0 ? fmtVND(Math.round(records.reduce((a,r) => a + (r.spend||0), 0) / totals.conv)) : '—'}</p>
            CPA
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

// ─── Suggestion Chips ────────────────────────────────────────────────────────
function SuggestionChips({ questions, onSend }) {
  if (!questions?.length) return null
  return (
    <div className="mt-3 pt-3 border-t border-border">
      <p className="text-[10px] font-semibold text-muted-foreground uppercase mb-2">💡 Hỏi Agent phân tích</p>
      <div className="flex flex-wrap gap-1.5">
        {questions.map((q) => (
          <button
            key={q.id}
            onClick={() => onSend(q.question)}
            className="px-2.5 py-1.5 text-[11px] font-medium rounded-full border border-violet-200 bg-violet-50 text-violet-700 hover:bg-violet-100 hover:border-violet-300 transition-colors"
          >
            {q.question}
          </button>
        ))}
      </div>
    </div>
  )
}

// ─── Loading State ───────────────────────────────────────────────────────────
function GeneratingState({ status }) {
  const types = status?.types || {}
  const total = status?.total || 6
  const ready = status?.ready || 0
  const pct = Math.round((ready / total) * 100)

  return (
    <div className="flex flex-col items-center justify-center py-10 gap-4">
      <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-100 to-indigo-100 border border-violet-200 flex items-center justify-center animate-pulse">
        <BarChart2 className="w-8 h-8 text-violet-500" />
      </div>
      <div className="text-center">
        <p className="font-semibold text-foreground">Đang tạo báo cáo...</p>
        <p className="text-xs text-muted-foreground mt-1">{ready}/{total} hạng mục hoàn tất ({pct}%)</p>
      </div>
      <div className="w-64 h-2 bg-muted rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-violet-500 to-indigo-500 rounded-full transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="grid grid-cols-3 gap-2 mt-2">
        {Object.entries(types).map(([type, st]) => (
          <div key={type} className="flex items-center gap-1.5 text-xs">
            {st === 'ready' ? (
              <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />
            ) : st === 'error' ? (
              <AlertCircle className="w-3.5 h-3.5 text-red-500" />
            ) : (
              <Loader2 className="w-3.5 h-3.5 text-violet-500 animate-spin" />
            )}
            <span className={st === 'ready' ? 'text-green-700' : st === 'error' ? 'text-red-600' : 'text-muted-foreground'}>
              {type.replace('_', ' ')}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Tab-specific chart sets ─────────────────────────────────────────────────
function TabCharts({ tabId, records }) {
  if (!records?.length) return null

  switch (tabId) {
    // Daily Ops: Combo Bar+CTR-line, Grouped zone bar (imp+clk), Zone table
    case 'daily_ops':
      return (
        <>
          <DailyTrendChart records={records} title="📈 Campaign Performance — Daily Combo"
            dataKey1="imp" color1="#1f3551" type="bar" rightKey="ctr" rightColor="#f59e0b" />
          <GroupedZoneBar records={records} title="📊 Performance by Zone — Impressions vs Clicks" />
          <ZoneBarChart records={records} dataKey="imp" label="Impressions by Zone" color="#6366f1" />
          <ZoneTable records={records} />
        </>
      )

    // Awareness: Reach+Freq combo, CPM trend+benchmark refLine, Viewability color-coded hbar
    case 'awareness':
      return (
        <>
          <DailyTrendChart records={records} title="👁 Daily Reach & Frequency Trend"
            dataKey1="reach" color1="#8b5cf6" type="bar" rightKey="imp" rightColor="#c4b5fd" />
          <DailyTrendChart records={records} title="📊 CPM Trend & Period Benchmark"
            dataKey1="cpm" color1="#f59e0b" type="line" refLine />
          <ColorHBarChart records={records} title="👁 Viewability by Placement (VI%)"
            metricFn={rows => rows.length ? rows.reduce((s, r) => s + (r.vi || 0), 0) / rows.length : 0}
            labelFn={rows => rows.length ? (rows.reduce((s, r) => s + (r.vi || 0), 0) / rows.length).toFixed(1) + '%' : '—'} />
          <DailyTrendChart records={records} title="📦 Frequency Distribution — Daily Impressions"
            dataKey1="imp" color1="#10b981" type="bar" />
          <ZoneTable records={records} />
        </>
      )

    // Consideration: Multi-zone CTR line, CTR vs CPM bubble, Stacked click vol, CTR by channel grouped
    case 'consideration':
      return (
        <>
          <MultiZoneLineChart records={records} title="🖱 CTR Trend — Top 5 Placements" maxZones={5} />
          <ScatterBubbleChart records={records} title="🔵 CTR vs CPM — Efficiency Scatter" />
          <StackedZoneBar records={records} title="📊 Daily Click Volume by Zone (Stacked)" />
          <GroupedZoneBar records={records} title="📊 CTR by Zone — Grouped Comparison" />
          <ZoneTable records={records} />
        </>
      )

    // Conversion: Funnel, Conv+CVR combo, CVR hbar, CPA color-coded hbar, Spend vs Conv scatter
    case 'conversion':
      return (
        <>
          <ConversionFunnel records={records} />
          <DailyTrendChart records={records} title="🎯 Daily Conversions & CVR Trend"
            dataKey1="conv" color1="#10b981" type="bar" rightKey="ctr" rightColor="#f59e0b" />
          <ColorHBarChart records={records} title="📊 CVR by Zone"
            metricFn={rows => { const i = rows.reduce((s,r)=>s+(r.impressions||0),0); const c = rows.reduce((s,r)=>s+(r.conversions||0),0); return i > 0 ? c/i*100 : 0 }}
            labelFn={rows => { const i = rows.reduce((s,r)=>s+(r.impressions||0),0); const c = rows.reduce((s,r)=>s+(r.conversions||0),0); return i > 0 ? (c/i*100).toFixed(3)+'%' : '0%' }} />
          <ColorHBarChart records={records} title="💸 CPA by Placement (lower = better)" invert
            metricFn={rows => { const s = rows.reduce((a,r)=>a+(r.spend||0),0); const c = rows.reduce((a,r)=>a+(r.conversions||0),0); return c > 0 ? s/c : 0 }}
            labelFn={rows => { const s = rows.reduce((a,r)=>a+(r.spend||0),0); const c = rows.reduce((a,r)=>a+(r.conversions||0),0); return c > 0 ? fmtVND(Math.round(s/c)) : '—' }} />
          <ScatterBubbleChart records={records} title="🔵 Spend vs Conversions — Zone Scatter" />
          <ZoneTable records={records} />
        </>
      )

    // Retention: WoW Reach+Freq combo, CTR decay + refLine baseline, Avg Freq hbar
    case 'retention':
      return (
        <>
          <DailyTrendChart records={records} title="🔄 Week-over-Week Reach & Frequency"
            dataKey1="reach" color1="#ec4899" type="bar" rightKey="imp" rightColor="#fb7185" />
          <DailyTrendChart records={records} title="📉 CTR Decay Curve — Creative Fatigue Monitor"
            dataKey1="ctr" color1="#f43f5e" type="line" refLine />
          <ColorHBarChart records={records} title="📊 Avg Frequency by Placement"
            metricFn={rows => rows.length ? rows.reduce((s,r) => s + (r.impressions||0), 0) / rows.reduce((s,r) => s + (r.reach||1), 0) : 0}
            labelFn={rows => { const i = rows.reduce((s,r)=>s+(r.impressions||0),0); const rc = rows.reduce((s,r)=>s+(r.reach||1),0); return (i/rc).toFixed(2)+'x' }} />
          <ZoneTable records={records} />
        </>
      )

    // Executive: Spend pacing + linear ref, Donut budget allocation, CTR+Conv trend, KPI funnel
    case 'executive':
      return (
        <>
          <SpendPacingChart records={records} />
          <DonutPieChart records={records} title="🍩 Budget Allocation by Zone" />
          <DailyTrendChart records={records} title="📈 CTR & Conversions Trend"
            dataKey1="ctr" dataKey2="conv" color1="#10b981" color2="#f59e0b" type="line" />
          <ConversionFunnel records={records} />
          <ZoneTable records={records} />
        </>
      )

    default:
      return <ZoneTable records={records} />
  }
}

// ─── Tab-specific chart sets end ─────────────────────────────────────────────

// ═══════════════════════════════════════════════════════════════════════════════
// ReportStep — Main Component
// ═══════════════════════════════════════════════════════════════════════════════
export default function ReportStep({ data, onChange, isDone, formState, onSendChat, onRetry }) {
  const [activeTab, setActiveTab] = useState('daily_ops')
  const [records, setRecords] = useState([])
  const [reportStatus, setReportStatus] = useState(null)
  const [analyses, setAnalyses] = useState({})
  const [loading, setLoading] = useState(true)
  const [allReady, setAllReady] = useState(false)
  const [failed, setFailed] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const pollRef = useRef(null)
  const campaignId = data?.campaignId || formState?.report?.campaignId || ''
  const objective = formState?.brief?.objective || 'awareness'

  // All six generated report perspectives remain available. The campaign
  // objective is used inside the report content, not to hide other evidence.
  const visibleTabs = REPORT_TABS

  // Poll report status
  useEffect(() => {
    if (!campaignId || allReady || failed || retrying) return

    const poll = async () => {
      const status = await AgentAPI.getReportStatus(campaignId)
      if (!status) return
      setReportStatus(status)

      if (status.ready >= status.total) {
        setAllReady(true)
        clearInterval(pollRef.current)
        // Fetch all data
        const [recs, analyses] = await Promise.all([
          AgentAPI.getReportData(campaignId),
          AgentAPI.getReportAnalyses(campaignId),
        ])
        setRecords(recs || [])
        const analysisMap = {}
        ;(analyses || []).forEach(a => { analysisMap[a.reportType] = a })
        setAnalyses(analysisMap)
        setLoading(false)
        onChange?.({ ...data, analyzed: true, campaignId })
      } else if (status.errors > 0 && status.ready + status.errors >= status.total) {
        clearInterval(pollRef.current)
        setLoading(false)
        setFailed(true)
      }
    }

    poll()
    pollRef.current = setInterval(poll, 3000)
    return () => clearInterval(pollRef.current)
  }, [campaignId, allReady, failed, retrying])

  const retryGeneration = async () => {
    setRetrying(true)
    setFailed(false)
    setLoading(true)
    setReportStatus(null)
    try {
      if (onRetry) await onRetry()
      else await AgentAPI.reportEntry()
    } finally {
      setRetrying(false)
    }
  }

  // Get questions for current tab
  const currentAnalysis = analyses[activeTab] || analyses['daily_ops']
  const questions = currentAnalysis?.questions || []

  const handleSend = useCallback((text) => {
    if (onSendChat) onSendChat(text)
  }, [onSendChat])

  // Notify parent about active tab change
  useEffect(() => {
    if (data?.activeTab !== activeTab) {
      onChange?.({ ...data, activeTab: activeTab })
    }
  }, [activeTab])

  // ── Not yet generating ─────────────────────────────────────────────────────
  if (!campaignId) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-4">
        <div className="w-16 h-16 rounded-2xl bg-violet-50 border border-violet-200 flex items-center justify-center">
          <BarChart2 className="w-8 h-8 text-violet-500" />
        </div>
        <div className="text-center">
          <p className="font-semibold text-foreground">Báo cáo chiến dịch</p>
          <p className="text-xs text-muted-foreground mt-1">Đang chuẩn bị dữ liệu và phân tích báo cáo...</p>
        </div>
        <Loader2 className="w-6 h-6 text-violet-500 animate-spin" />
      </div>
    )
  }

  if (failed) {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-center" role="alert">
        <AlertCircle className="mx-auto h-8 w-8 text-red-600" />
        <h3 className="mt-3 font-bold text-red-950">Không thể tạo báo cáo</h3>
        <p className="mt-2 text-xs leading-5 text-red-800">
          {reportStatus?.errors || 0}/{reportStatus?.total || 6} hạng mục gặp lỗi. Vui lòng thử tạo lại báo cáo.
        </p>
        <button type="button" onClick={retryGeneration} disabled={retrying}
          className="mt-4 rounded-xl bg-red-600 px-4 py-2 text-xs font-bold text-white hover:bg-red-700 disabled:opacity-60">
          {retrying ? 'Đang thử lại…' : 'Tạo lại báo cáo'}
        </button>
      </div>
    )
  }

  // ── Generating (polling) ───────────────────────────────────────────────────
  if (loading) {
    return <GeneratingState status={reportStatus} />
  }

  // ── Reports ready — show tabs + charts ─────────────────────────────────────
  return (
    <div className="space-y-0">
      {/* Ready summary + shared Copilot/Autopilot export action */}
      <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 p-2">
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 flex-shrink-0" />
          <p className="text-[11px] text-slate-700 font-medium">
            {records.length} bản ghi · {Object.keys(analyses).length} nhóm phân tích đã sẵn sàng
          </p>
        </div>
        <a
          href={`${BACKEND_URL}/api/reports/export/${encodeURIComponent(campaignId)}/pdf`}
          target="_blank"
          rel="noreferrer"
          download={`report-${campaignId}.pdf`}
          className="inline-flex min-h-9 shrink-0 items-center justify-center gap-2 rounded-xl bg-brand-600 px-3 py-2 text-[11px] font-bold text-white shadow-sm transition hover:bg-brand-700"
          aria-label="Tải PDF đầy đủ gồm 6 báo cáo tương thích"
        >
          <FileText className="h-3.5 w-3.5" />
          Tải PDF đầy đủ (6 báo cáo)
          <Download className="h-3.5 w-3.5" />
        </a>
      </div>

      {/* Tab bar */}
      <div className="flex flex-wrap gap-1 mb-4 p-1 bg-muted/50 rounded-xl">
        {visibleTabs.map(tab => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          const isObjective = tab.id === objective
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`
                flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[11px] font-semibold transition-all
                ${isActive
                  ? 'bg-white shadow-sm text-foreground border border-border'
                  : 'text-muted-foreground hover:text-foreground hover:bg-white/60'
                }
              `}
            >
              <Icon className="w-3 h-3" style={{ color: isActive ? tab.color : undefined }} />
              {tab.label}
              {isObjective && <Badge variant="violet" className="text-[8px] px-1 py-0 ml-0.5">⭐</Badge>}
            </button>
          )
        })}
      </div>

      {/* Overall summary */}
      {currentAnalysis?.overall && (
        <Card className="mb-3 border-violet-200 bg-gradient-to-r from-violet-50 to-indigo-50">
          <CardContent className="py-3">
            <p className="text-xs text-violet-800 font-medium leading-relaxed">{currentAnalysis.overall}</p>
          </CardContent>
        </Card>
      )}

      {currentAnalysis?.dataContract && (
        <details className="mb-3 rounded-xl border border-slate-200 bg-white p-3 text-[11px] text-slate-700" data-testid="report-evidence-contract">
          <summary className="cursor-pointer font-bold text-slate-900">
            Nguồn số liệu, công thức & giới hạn · {currentAnalysis.dataContract.contractVersion}
          </summary>
          <div className="mt-3 space-y-3">
            <p>
              <strong>Thời gian:</strong> {currentAnalysis.dataContract.timeframe?.start || 'N/A'} → {currentAnalysis.dataContract.timeframe?.end || 'N/A'}
              {' · '}<strong>Contract:</strong> {currentAnalysis.dataContract.contractVersion}
              {' · '}<strong>Nguồn:</strong> {currentAnalysis.dataContract.source}
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              {Object.entries(currentAnalysis.dataContract.metricDefinitions || {}).map(([metricId, metric]) => (
                <div key={metricId} className="rounded-lg border border-slate-100 bg-slate-50 p-2">
                  <p className="font-bold">{metric.label} <code className="text-[9px] text-slate-500">{metricId}</code></p>
                  <p className="mt-0.5 text-slate-600">{metric.formula}</p>
                  {metric.limitation && <p className="mt-0.5 text-amber-700">{metric.limitation}</p>}
                </div>
              ))}
            </div>
            <ul className="list-disc space-y-1 pl-4 text-slate-600">
              {(currentAnalysis.dataContract.limitations || []).map((item, index) => <li key={index}>{item}</li>)}
            </ul>
          </div>
        </details>
      )}

      {/* KPI Scorecard */}
      <BusinessPerformance contract={currentAnalysis?.dataContract} />
      <KPIScorecard records={records} />

      {/* Tab-specific charts */}
      <TabCharts tabId={activeTab} records={records} />

      {/* Suggestion chips */}
      <SuggestionChips questions={questions} onSend={handleSend} />
    </div>
  )
}
