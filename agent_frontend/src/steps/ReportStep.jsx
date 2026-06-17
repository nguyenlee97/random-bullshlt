import { useState, useEffect, useCallback, useRef } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { AgentAPI } from '@/api/agentApi'
import {
  BarChart, Bar, LineChart, Line, AreaChart, Area, ComposedChart,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import {
  BarChart2, Loader2, TrendingUp, TrendingDown, Minus, CheckCircle2,
  Activity, Eye, MousePointerClick, DollarSign, RefreshCw, Users, Target,
  AlertCircle, Zap,
} from 'lucide-react'

// ─── Report tab config ───────────────────────────────────────────────────────
const REPORT_TABS = [
  { id: 'daily_ops',     label: 'Daily Ops',      icon: Activity,           color: '#3b82f6' },
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
    a.viSum += r.vi || 0
    a.n++
    return a
  }, { imp: 0, clk: 0, spend: 0, conv: 0, reach: 0, viSum: 0, n: 0 })

  const avgCTR = totals.imp > 0 ? (totals.clk / totals.imp * 100).toFixed(2) : '0'
  const avgVI = totals.n > 0 ? (totals.viSum / totals.n).toFixed(1) : '0'
  const avgCPM = totals.imp > 0 ? Math.round(totals.spend / totals.imp * 1000) : 0

  const kpis = [
    { label: 'Impressions', value: fmtN(totals.imp), icon: Eye, color: 'text-blue-600', bg: 'bg-blue-50 border-blue-200' },
    { label: 'Clicks', value: fmtN(totals.clk), icon: MousePointerClick, color: 'text-amber-600', bg: 'bg-amber-50 border-amber-200' },
    { label: 'CTR', value: avgCTR + '%', icon: TrendingUp, color: 'text-green-600', bg: 'bg-green-50 border-green-200' },
    { label: 'Spend', value: fmtVND(totals.spend), icon: DollarSign, color: 'text-violet-600', bg: 'bg-violet-50 border-violet-200' },
    { label: 'Reach', value: fmtN(totals.reach), icon: Users, color: 'text-pink-600', bg: 'bg-pink-50 border-pink-200' },
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

// ─── Daily Trend Chart ───────────────────────────────────────────────────────
function DailyTrendChart({ records, title, dataKey1, dataKey2, color1, color2, type = 'bar' }) {
  const byDate = {}
  records.forEach(r => {
    if (!byDate[r.date]) byDate[r.date] = { date: r.date, imp: 0, clk: 0, spend: 0, conv: 0, reach: 0, ctr: 0, n: 0 }
    const d = byDate[r.date]
    d.imp += r.impressions || 0
    d.clk += r.clicks || 0
    d.spend += r.spend || 0
    d.conv += r.conversions || 0
    d.reach += r.reach || 0
    d.n++
  })
  const data = Object.values(byDate)
    .sort((a, b) => a.date.localeCompare(b.date))
    .map(d => ({
      ...d,
      date: d.date.slice(5), // MM-DD
      ctr: d.imp > 0 ? +(d.clk / d.imp * 100).toFixed(2) : 0,
      cpm: d.imp > 0 ? Math.round(d.spend / d.imp * 1000) : 0,
    }))

  const k1 = dataKey1 || 'imp'
  const k2 = dataKey2 || 'clk'
  const c1 = color1 || '#3b82f6'
  const c2 = color2 || '#10b981'

  return (
    <Card className="mb-3">
      <CardHeader className="pb-1 pt-3">
        <CardTitle className="text-xs text-muted-foreground">{title || 'Daily Trend'}</CardTitle>
      </CardHeader>
      <CardContent className="pt-0 pb-2">
        <ResponsiveContainer width="100%" height={160}>
          {type === 'area' ? (
            <AreaChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 9 }} />
              <YAxis tick={{ fontSize: 9 }} />
              <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
              <Area type="monotone" dataKey={k1} stroke={c1} fill={c1} fillOpacity={0.15} strokeWidth={2} />
              {k2 && <Area type="monotone" dataKey={k2} stroke={c2} fill={c2} fillOpacity={0.1} strokeWidth={2} />}
            </AreaChart>
          ) : type === 'line' ? (
            <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 9 }} />
              <YAxis tick={{ fontSize: 9 }} />
              <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
              <Legend wrapperStyle={{ fontSize: 10 }} />
              <Line type="monotone" dataKey={k1} stroke={c1} strokeWidth={2} dot={{ r: 2 }} />
              {k2 && <Line type="monotone" dataKey={k2} stroke={c2} strokeWidth={2} dot={{ r: 2 }} />}
            </LineChart>
          ) : (
            <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 9 }} />
              <YAxis tick={{ fontSize: 9 }} />
              <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
              <Legend wrapperStyle={{ fontSize: 10 }} />
              <Bar dataKey={k1} fill={c1} radius={[3, 3, 0, 0]} />
              {k2 && <Bar dataKey={k2} fill={c2} radius={[3, 3, 0, 0]} />}
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
    // Daily Ops: Combo (Imp+Clicks bars + CTR line), Audience grouped bars, Campaign comparison multi-line
    case 'daily_ops':
      return (
        <>
          <DailyTrendChart records={records} title="📈 Campaign Performance — Daily Combo" subtitle="Impressions + Clicks (bars) · CTR % (line)" dataKey1="imp" dataKey2="clk" color1="#1f3551" color2="#2c7fb8" type="bar" ctrLine />
          <DailyTrendChart records={records} title="📊 Performance by Audience Segment" subtitle="Top placements grouped by impressions per day" dataKey1="imp" dataKey2={null} color1="#3b82f6" type="bar" />
          <ZoneBarChart records={records} dataKey="imp" label="Campaign Comparison — Impressions by Zone" color="#6366f1" />
          <ZoneTable records={records} />
        </>
      )
    // Awareness: Daily Reach+Frequency (combo), CPM Trend, Frequency Distribution (bar), Viewability by Placement (horizontal bar), Video Funnel, Channel Matrix table
    case 'awareness':
      return (
        <>
          <DailyTrendChart records={records} title="👁 Daily Reach & Frequency Trend" subtitle="Reach bars · Impressions/Reach ratio (frequency est.)" dataKey1="reach" dataKey2="imp" color1="#8b5cf6" color2="#c4b5fd" type="area" />
          <DailyTrendChart records={records} title="📊 CPM Trend & Period Benchmark" subtitle="Daily avg CPM vs period average" dataKey1="cpm" dataKey2={null} color1="#f59e0b" type="line" />
          <ZoneBarChart records={records} dataKey="reach" label="Viewability by Placement (VI%) — avg VI per zone" color="#8b5cf6" />
          <ZoneTable records={records} />
        </>
      )
    // Consideration: CTR Trend top 5 placements (multi-line), CTR vs CPM scatter → simplified as bar, Daily Click Volume stacked, Top placements table, CTR by Format grouped bar, Campaign ranking table
    case 'consideration':
      return (
        <>
          <DailyTrendChart records={records} title="🖱 CTR Trend — Top Placements" subtitle="Daily CTR % per placement over time" dataKey1="ctr" dataKey2={null} color1="#f59e0b" type="line" />
          <DailyTrendChart records={records} title="📊 Daily Click Volume by Channel" subtitle="Stacked bars — total daily clicks by zone" dataKey1="clk" dataKey2={null} color1="#3b82f6" type="bar" />
          <ZoneBarChart records={records} dataKey="clk" label="Top Placements by Click Volume" color="#f59e0b" />
          <ZoneTable records={records} />
        </>
      )
    // Conversion: Daily Conversions+CVR combo, CVR by channel bar, CPA by placement horizontal, Spend vs Conv scatter, End-to-end funnel, Top converting campaigns table
    case 'conversion':
      return (
        <>
          <ConversionFunnel records={records} />
          <DailyTrendChart records={records} title="🎯 Daily Conversions & CVR Trend" subtitle="Conversion bars · CVR % line (right axis)" dataKey1="conv" dataKey2={null} color1="#10b981" type="area" />
          <DailyTrendChart records={records} title="💸 Spend vs Conversions" subtitle="Spend line vs daily conversions" dataKey1="spend" dataKey2="conv" color1="#6366f1" color2="#10b981" type="line" />
          <ZoneBarChart records={records} dataKey="conv" label="CPA by Placement (Conversions per Zone)" color="#10b981" />
          <ZoneTable records={records} />
        </>
      )
    // Retention: WoW Reach+Frequency (combo), Frequency by Placement (horizontal bar), CTR Decay Curve (line+rolling avg+baseline), Audience Saturation table
    case 'retention':
      return (
        <>
          <DailyTrendChart records={records} title="🔄 Week-over-Week Reach & Frequency" subtitle="Weekly reach bars · Avg frequency est. (right axis)" dataKey1="reach" dataKey2={null} color1="#ec4899" type="area" />
          <DailyTrendChart records={records} title="📉 CTR Decay Curve — Creative Fatigue Monitor" subtitle="Daily CTR · 7-day rolling avg · Launch baseline" dataKey1="ctr" dataKey2={null} color1="#f43f5e" type="line" />
          <ZoneBarChart records={records} dataKey="imp" label="Avg Frequency by Placement" color="#ec4899" />
          <ZoneTable records={records} />
        </>
      )
    // Executive: Health scorecard table, Radar (simplified as KPI grid), Cumulative Spend Pacing, Budget Allocation donut → ZoneBarChart, Period-over-Period table, Smart Recommendations
    case 'executive':
      return (
        <>
          <SpendPacingChart records={records} />
          <DailyTrendChart records={records} title="📈 CTR & Conversions Trend" subtitle="Period-over-period KPI comparison" dataKey1="ctr" dataKey2="conv" color1="#10b981" color2="#f59e0b" type="line" />
          <ConversionFunnel records={records} />
          <ZoneBarChart records={records} dataKey="spend" label="Budget Allocation by Zone (Spend Share)" color="#6366f1" />
          <ZoneTable records={records} />
        </>
      )
    default:
      return <ZoneTable records={records} />
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// ReportStep — Main Component
// ═══════════════════════════════════════════════════════════════════════════════
export default function ReportStep({ data, onChange, isDone, formState, onSendChat }) {
  const [activeTab, setActiveTab] = useState('daily_ops')
  const [records, setRecords] = useState([])
  const [reportStatus, setReportStatus] = useState(null)
  const [analyses, setAnalyses] = useState({})
  const [loading, setLoading] = useState(true)
  const [allReady, setAllReady] = useState(false)
  const pollRef = useRef(null)
  const campaignId = data?.campaignId || formState?.report_context?.campaignId || ''

  // Determine objective to highlight the primary report tab
  const objective = formState?.brief?.objective || 'awareness'
  const objectiveTab = REPORT_TABS.find(t => t.id === objective)

  // Poll report status
  useEffect(() => {
    if (!campaignId || allReady) return

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
      }
    }

    poll()
    pollRef.current = setInterval(poll, 3000)
    return () => clearInterval(pollRef.current)
  }, [campaignId, allReady])

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
          <p className="text-xs text-muted-foreground mt-1">Đang chuẩn bị tạo báo cáo mô phỏng...</p>
        </div>
        <Loader2 className="w-6 h-6 text-violet-500 animate-spin" />
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
      {/* Showcase badge */}
      <div className="flex items-center gap-2 mb-3 p-2 rounded-lg bg-amber-50 border border-amber-200">
        <AlertCircle className="w-3.5 h-3.5 text-amber-600 flex-shrink-0" />
        <p className="text-[11px] text-amber-700 font-medium">
          Dữ liệu mô phỏng (showcase) · {records.length} records · {Object.keys(analyses).length} phân tích AI
        </p>
      </div>

      {/* Tab bar */}
      <div className="flex flex-wrap gap-1 mb-4 p-1 bg-muted/50 rounded-xl">
        {REPORT_TABS.map(tab => {
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

      {/* KPI Scorecard */}
      <KPIScorecard records={records} />

      {/* Tab-specific charts */}
      <TabCharts tabId={activeTab} records={records} />

      {/* Suggestion chips */}
      <SuggestionChips questions={questions} onSend={handleSend} />
    </div>
  )
}
