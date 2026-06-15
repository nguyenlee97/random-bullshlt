import ReactMarkdown from 'react-markdown'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow
} from '@/components/ui/table'
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer
} from 'recharts'
import { fmt } from '@/lib/utils'
import { Users, TrendingUp, TrendingDown, Minus, Mail, CheckCircle2, RefreshCw } from 'lucide-react'

// ─── Table Block ─────────────────────────────────────────────────────────────
function TableBlock({ block }) {
  return (
    <div className="mt-2">
      {block.title && (
        <p className="text-xs font-semibold text-muted-foreground mb-1.5 flex items-center gap-1">
          {block.title}
        </p>
      )}
      <Table>
        <TableHeader>
          <TableRow>
            {block.columns.map((col, i) => (
              <TableHead key={i}>{col}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {block.rows.map((row, i) => (
            <TableRow key={i}>
              {row.map((cell, j) => (
                <TableCell key={j} className="text-xs">{cell}</TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

// ─── Chart Block ─────────────────────────────────────────────────────────────
function ChartBlock({ block }) {
  const chartData = block.data.labels.map((label, i) => {
    const entry = { label }
    block.data.series.forEach(s => { entry[s.name] = s.values[i] })
    return entry
  })

  return (
    <Card className="mt-2">
      <CardHeader className="pb-2 pt-3">
        <CardTitle className="text-xs text-muted-foreground">{block.title}</CardTitle>
      </CardHeader>
      <CardContent className="pt-0 pb-3">
        <ResponsiveContainer width="100%" height={180}>
          {block.chartType === 'line' ? (
            <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="label" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {block.data.series.map(s => (
                <Line key={s.name} type="monotone" dataKey={s.name} stroke={s.color} strokeWidth={2} dot={{ r: 3 }} />
              ))}
            </LineChart>
          ) : (
            <BarChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="label" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {block.data.series.map(s => (
                <Bar key={s.name} dataKey={s.name} fill={s.color} radius={[3, 3, 0, 0]} />
              ))}
            </BarChart>
          )}
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}

// ─── Audience Size Block ──────────────────────────────────────────────────────
function AudienceSizeBlock({ block }) {
  return (
    <Card className="mt-2 border-brand-200 bg-brand-50">
      <CardContent className="py-3 flex items-center gap-4">
        <div className="w-10 h-10 rounded-full bg-brand-500 flex items-center justify-center flex-shrink-0">
          <Users className="w-5 h-5 text-white" />
        </div>
        <div>
          <p className="text-2xl font-black text-brand-700">{fmt(block.size)}</p>
          <p className="text-xs text-brand-600 font-medium">người dùng · {block.count} attributes</p>
        </div>
      </CardContent>
    </Card>
  )
}

// ─── Campaign List Block ──────────────────────────────────────────────────────
function CampaignListBlock({ block }) {
  const statusConfig = {
    running:  { label: 'Đang chạy', dot: 'bg-brand-500', text: 'text-brand-700', bg: 'bg-brand-50' },
    paused:   { label: 'Tạm dừng', dot: 'bg-amber-500', text: 'text-amber-700', bg: 'bg-amber-50' },
    draft:    { label: 'Nháp',     dot: 'bg-gray-400',  text: 'text-gray-600',  bg: 'bg-gray-50' },
  }
  return (
    <div className="mt-2 space-y-2">
      {block.campaigns.map(c => {
        const s = statusConfig[c.status] || statusConfig.draft
        return (
          <Card key={c.id} className="border-border">
            <CardContent className="py-3 flex items-center gap-3">
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold text-foreground truncate">{c.name}</p>
                <p className="text-[11px] text-muted-foreground mt-0.5">
                  {c.id} · {c.budget}M · CPM {(c.cpm / 1000).toFixed(0)}k VND
                </p>
              </div>
              <div className={`flex items-center gap-1.5 px-2 py-1 rounded-full ${s.bg}`}>
                <div className={`w-1.5 h-1.5 rounded-full ${s.dot}`} />
                <span className={`text-[11px] font-semibold ${s.text}`}>{s.label}</span>
              </div>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}

// ─── Verdict Block (donut summary) ───────────────────────────────────────────
function VerdictBlock({ block }) {
  const total = block.total || (block.good + block.watch + block.bad)
  const pctGood = Math.round(block.good / total * 100)
  return (
    <Card className="mt-2">
      <CardContent className="py-3">
        <p className="text-xs font-semibold text-muted-foreground mb-2">Verdict · {total} campaigns</p>
        <div className="grid grid-cols-3 gap-2">
          {[
            { label: 'Good', count: block.good, color: 'text-brand-600', bg: 'bg-brand-50 border-brand-200', Icon: TrendingUp },
            { label: 'Watch', count: block.watch, color: 'text-amber-600', bg: 'bg-amber-50 border-amber-200', Icon: Minus },
            { label: 'Bad',  count: block.bad,  color: 'text-red-600',   bg: 'bg-red-50 border-red-200',   Icon: TrendingDown },
          ].map(({ label, count, color, bg, Icon }) => (
            <div key={label} className={`rounded-lg border p-2.5 text-center ${bg}`}>
              <Icon className={`w-4 h-4 mx-auto mb-1 ${color}`} />
              <p className={`text-lg font-black ${color}`}>{count}</p>
              <p className={`text-[10px] font-semibold ${color}`}>{label}</p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

// ─── Info Block ───────────────────────────────────────────────────────────────
function InfoBlock({ block }) {
  return (
    <div className="mt-2 flex items-start gap-2 p-3 rounded-lg bg-brand-50 border border-brand-100">
      <CheckCircle2 className="w-4 h-4 text-brand-500 flex-shrink-0 mt-0.5" />
      <p className="text-xs text-brand-700 font-medium">{block.text}</p>
    </div>
  )
}

// ─── Email Preview Block ──────────────────────────────────────────────────────
function EmailPreviewBlock({ block }) {
  return (
    <Card className="mt-2 border-blue-200">
      <CardHeader className="pb-2 pt-3 flex-row items-center gap-2">
        <Mail className="w-4 h-4 text-blue-500" />
        <CardTitle className="text-xs text-blue-700">Email Preview</CardTitle>
      </CardHeader>
      <CardContent className="pt-0 pb-3 space-y-1">
        {[['To', block.to], ['Cc', block.cc], ['Subject', block.subject]].map(([k, v]) => (
          <div key={k} className="flex gap-2 text-xs">
            <span className="font-semibold text-muted-foreground w-12 flex-shrink-0">{k}:</span>
            <span className="text-foreground">{v}</span>
          </div>
        ))}
        <div className="mt-2 pt-2 border-t border-border">
          <pre className="text-xs text-muted-foreground whitespace-pre-wrap font-sans leading-relaxed max-h-32 overflow-y-auto">{block.body}</pre>
        </div>
      </CardContent>
    </Card>
  )
}

// ─── Action Reset Block ───────────────────────────────────────────────────────
function ActionResetBlock({ block }) {
  return (
    <div className="mt-2 p-3 rounded-lg border border-violet-200 bg-violet-50 flex items-start gap-2.5">
      <RefreshCw className="w-4 h-4 text-violet-500 flex-shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <p className="text-xs text-violet-700 font-medium mb-2">{block.text || 'Bắt đầu chiến dịch mới từ đầu?'}</p>
        <button
          onClick={() => window.dispatchEvent(new CustomEvent('agent:reset'))}
          className="px-3 py-1.5 rounded-lg bg-violet-500 hover:bg-violet-600 text-white text-xs font-bold transition-colors"
        >
          🔄 Bắt đầu lại
        </button>
      </div>
    </div>
  )
}

// ─── Block Router ─────────────────────────────────────────────────────────────
export default function BlockRenderer({ block }) {
  switch (block.type) {
    case 'table':         return <TableBlock block={block} />
    case 'chart':         return <ChartBlock block={block} />
    case 'audience_size': return <AudienceSizeBlock block={block} />
    case 'campaign_list': return <CampaignListBlock block={block} />
    case 'verdict':       return <VerdictBlock block={block} />
    case 'info':          return <InfoBlock block={block} />
    case 'email_preview': return <EmailPreviewBlock block={block} />
    case 'action_reset':  return <ActionResetBlock block={block} />
    default: return null
  }
}
