import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import log from '@/lib/logger'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow
} from '@/components/ui/table'
import { fmt } from '@/lib/utils'
import { Users, TrendingUp, TrendingDown, Minus, Mail, CheckCircle2, RefreshCw, Pencil, X, AlertTriangle, BarChart } from 'lucide-react'
import ChartBlock from './ChartBlock'

// ─── Table Block ─────────────────────────────────────────────────────────────
function TableBlock({ block }) {
  return (
    <div className="mt-2">
      {block.title && (
        <p className="text-xs font-semibold text-muted-foreground mb-1.5 flex items-center gap-1">
          {block.title}
        </p>
      )}
      {/* overflow-x-auto: wide tables scroll horizontally instead of breaking viewport */}
      <div className="overflow-x-auto">
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
    </div>
  )
}

// ─── Chart Block ─────────────────────────────────────────────────────────────
// ─── Audience Size Block ──────────────────────────────────────────────────────
function AudienceSizeBlock({ block }) {
  const sizeKnown = block.size_known ?? (
    Number(block.size || 0) > 0
    || (block.breakdown || []).some(item => Number(item.size || 0) > 0)
  )
  return (
    <Card className="mt-2 border-brand-200 bg-brand-50">
      <CardContent className="py-3 flex items-center gap-4">
        <div className="w-10 h-10 rounded-full bg-brand-500 flex items-center justify-center flex-shrink-0">
          <Users className="w-5 h-5 text-white" />
        </div>
        <div>
          <p className="text-2xl font-black text-brand-700">{sizeKnown ? fmt(block.size) : '—'}</p>
          <p className="text-xs text-brand-600 font-medium">
            {sizeKnown
              ? `unique reach ước lượng · ${block.confidence || 'medium'} confidence`
              : 'chưa thể tính unique reach'} · {block.count ?? block.breakdown?.length ?? 0} attributes
          </p>
          {block.range && (
            <p className="text-[10px] text-brand-600 mt-0.5">
              Khoảng {fmt(block.range.low)}–{fmt(block.range.high)} · universe tối đa {fmt(block.universe)}
            </p>
          )}
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
            <span className="text-foreground min-w-0 flex-1 break-words">{v}</span>
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

// ─── Workspace Proposal Block ─────────────────────────────────────────────────
function WorkspaceProposalBlock({ block }) {
  const { changes = {}, is_locked, warning, instruction } = block
  const field = changes.field || ''
  const rawValue = changes.value
  const reason = changes.reason || ''

  // ── Smart display value ────────────────────────────────────────────────────
  const displayValue = (() => {
    // SETUP (zones) proposal — show selected zone IDs
    if (field === 'setup' && typeof rawValue === 'object' && rawValue !== null) {
      const ids = rawValue.selectedZoneIds || []
      const reco = rawValue.recoZones || []
      const lines = [`🎯 ${ids.length} zones được đề xuất`]
      if (reco.length) {
        reco.slice(0, 5).forEach(z => {
          const zoneName = z.name || (z.id ? z.id.replace(/_/g, ' ') : '?')
          const reach = z.reach ? `Reach ${(z.reach >= 1_000_000 ? (z.reach / 1_000_000).toFixed(1) : z.reach)}M` : ''
          lines.push(`• ${zoneName}${reach ? ' — ' + reach : ''}`)
        })
        if (reco.length > 5) lines.push(`... +${reco.length - 5} zones khác`)
      } else {
        ids.slice(0, 6).forEach(id => lines.push(`• ${id.replace(/_/g, ' ')}`))
      }
      lines.push('\n👉 Anh/chị xem và chỉnh sửa danh sách ở panel phải, rồi bấm xác nhận.')
      return lines.join('\n')
    }

    // AUDIENCE SEGMENT proposal — show human-friendly summary
    if (field === 'segment' && typeof rawValue === 'object' && rawValue !== null) {
      const attrs = rawValue.attrs || []
      const size = rawValue.size
      const targeting = rawValue.targeting || {}
      const lines = []
      lines.push(`📦 ${attrs.length} DMP segments`)
      if (size) lines.push(`👥 Audience ước tính: ${size.toLocaleString('vi-VN')} người`)
      const geoStr = (targeting.geo || []).slice(0, 3).join(', ')
      if (geoStr) lines.push(`🗺 Geo: ${geoStr}`)
      const ageStr = (targeting.age || []).slice(0, 3).join(', ')
      if (ageStr) lines.push(`🎂 Tuổi: ${ageStr}`)
      const genderStr = (targeting.gender || []).join(', ')
      if (genderStr) lines.push(`⚥ Giới tính: ${genderStr}`)
      // Show first 4 segment names
      const segNames = attrs.slice(0, 4).map(a => a.fullLabel || a.name || '?')
      if (segNames.length) lines.push(`\nSegments: ${segNames.join(' · ')}${attrs.length > 4 ? ` +${attrs.length - 4} khác` : ''}`)
      return lines.join('\n')
    }

    // BRIEF / generic object — show key: value pairs
    if (typeof rawValue === 'string') {
      try {
        const parsed = JSON.parse(rawValue)
        if (typeof parsed === 'object' && parsed !== null) {
          // If this is a segment value that was serialized as a string, route to
          // the audience display so we don't show "[object Object]" for attrs
          if (field === 'segment' && Array.isArray(parsed.attrs)) {
            const attrs = parsed.attrs || []
            const size = parsed.size
            const targeting = parsed.targeting || {}
            const lines = []
            lines.push(`📦 ${attrs.length} DMP segments`)
            if (size) lines.push(`👥 Audience ước tính: ${size.toLocaleString('vi-VN')} người`)
            const geoStr = (targeting.geo || []).slice(0, 3).join(', ')
            if (geoStr) lines.push(`🗺 Geo: ${geoStr}`)
            const segNames = attrs.slice(0, 4).map(a => a.fullLabel || a.name || '?')
            if (segNames.length) lines.push(`\nSegments: ${segNames.join(' · ')}${attrs.length > 4 ? ` +${attrs.length - 4} khác` : ''}`)
            return lines.join('\n')
          }
          return Object.entries(parsed)
            .filter(([, v]) => v !== null && v !== '' && v !== undefined && typeof v !== 'object')
            .map(([k, v]) => `${k}: ${v}`)
            .join('\n')
        }
      } catch {}
    }
    if (typeof rawValue === 'object' && rawValue !== null) {
      return Object.entries(rawValue)
        .filter(([, v]) => v !== null && v !== '' && !Array.isArray(v))
        .map(([k, v]) => `${k}: ${v}`)
        .join('\n')
    }
    return String(rawValue ?? '')
  })()

  const isAudience = field === 'segment'
  const isSetup = field === 'setup' || field === 'setup.selectedZoneIds'
  const proposalId = changes.proposal_id
  const [decision, setDecision] = useState(changes.status || 'pending')

  useEffect(() => {
    const listener = event => {
      if (!proposalId || event.detail?.proposal_id !== proposalId) return
      setDecision(event.detail.status || 'pending')
    }
    window.addEventListener('agent:workspace_proposal_result', listener)
    return () => window.removeEventListener('agent:workspace_proposal_result', listener)
  }, [proposalId])

  const handleConfirm = () => {
    if (!['pending', 'failed'].includes(decision)) return
    setDecision('processing')
    log.block('workspace_proposal CONFIRM', { field, value_type: typeof rawValue })
    if (isSetup) {
      // Setup is special: do NOT apply the stale proposal value (which has all recommended
      // zones regardless of what the user deselected). Instead dispatch a dedicated event
      // so App.jsx advances the sub-phase to 'assign' using the CURRENT workspace selection.
      window.dispatchEvent(new CustomEvent('agent:setup_zones_confirmed', {
        detail: { proposal_id: changes.proposal_id }
      }))
      setDecision('approved')
    } else {
      window.dispatchEvent(new CustomEvent('agent:workspace_confirm', {
        detail: { patch: changes }
      }))
    }
  }

  const handleCancel = () => {
    if (!['pending', 'failed'].includes(decision)) return
    setDecision('rejected')
    log.block('workspace_proposal CANCEL', { field })
    window.dispatchEvent(new CustomEvent('agent:workspace_cancel', {
      detail: { field, proposal_id: changes.proposal_id }
    }))
  }

  return (
    <div className="mt-2 rounded-xl border border-amber-200 bg-amber-50 overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 bg-amber-100 border-b border-amber-200">
        <Pencil className="w-3.5 h-3.5 text-amber-600 flex-shrink-0" />
        <p className="text-xs font-semibold text-amber-800">
          {isAudience ? '👥 Đề xuất Audience' : isSetup ? '🎯 Đề xuất Ad Zones' : 'Đề xuất cập nhật workspace'}
        </p>
      </div>

      {/* Change details */}
      <div className="px-3 py-2.5 space-y-1.5">
        <div className="flex gap-2 text-xs">
          <span className="text-amber-700 font-medium w-14 flex-shrink-0">Field:</span>
          <code className="text-amber-900 bg-amber-100 px-1.5 py-0.5 rounded font-mono text-[11px]">{field}</code>
        </div>
        <div className="flex gap-2 text-xs">
          <span className="text-amber-700 font-medium w-14 flex-shrink-0">
            {isAudience ? 'Tóm tắt:' : 'Giá trị:'}
          </span>
          <pre className="text-amber-900 text-[11px] whitespace-pre-wrap break-words font-sans flex-1 leading-relaxed">{displayValue}</pre>
        </div>
        {reason && (
          <div className="flex gap-2 text-xs min-w-0">
            <span className="text-amber-700 font-medium w-14 flex-shrink-0">Lý do:</span>
            <span className="text-amber-800 italic break-words min-w-0 flex-1">{reason}</span>
          </div>
        )}
        {/* Instruction for audience proposals (guide to deselect) */}
        {instruction && (
          <div className="mt-1 text-[11px] text-amber-700 bg-amber-100 border border-amber-200 rounded px-2 py-1.5">
            💡 {instruction}
          </div>
        )}
        {warning && (
          <p className="text-[11px] text-red-600 bg-red-50 border border-red-200 rounded px-2 py-1.5 mt-1">
            {warning}
          </p>
        )}
        {is_locked && !warning && (
          <p className="text-[11px] text-amber-700 italic">
            ⚠️ Bước này đã xác nhận — thay đổi sẽ reset các bước sau.
          </p>
        )}
      </div>

      {/* Proposal lifecycle */}
      {decision === 'approved' ? (
        <div className="mx-3 mb-3 flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-xs font-bold text-green-700">
          <CheckCircle2 className="h-4 w-4" /> Đã áp dụng vào workspace
        </div>
      ) : decision === 'rejected' ? (
        <div className="mx-3 mb-3 flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-bold text-slate-600">
          <X className="h-4 w-4" /> Đã bỏ qua đề xuất
        </div>
      ) : decision === 'superseded' ? (
        <div className="mx-3 mb-3 flex items-center gap-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs font-bold text-amber-800">
          <AlertTriangle className="h-4 w-4" /> Đề xuất đã lỗi thời vì workspace có thay đổi mới. Hãy tạo lại đề xuất nếu vẫn cần.
        </div>
      ) : decision === 'processing' ? (
        <div className="mx-3 mb-3 flex items-center gap-2 rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-xs font-bold text-brand-700" role="status">
          <RefreshCw className="h-4 w-4 animate-spin" /> Đang cập nhật workspace…
        </div>
      ) : <div className="flex gap-2 px-3 pb-3">
        <button
          onClick={handleConfirm}
          data-demo="workspace-proposal-confirm"
          data-workspace-field={field}
          className="flex-1 px-3 py-1.5 rounded-lg bg-brand-500 hover:bg-brand-600 text-white text-xs font-semibold transition-colors"
        >
          {isAudience ? '✅ Áp dụng tất cả segments' : isSetup ? '✅ Duyệt các zones này' : '✅ Đồng ý, cập nhật'}
        </button>
        <button
          onClick={handleCancel}
          className="px-3 py-1.5 rounded-lg border border-border bg-white hover:bg-muted text-xs font-semibold text-muted-foreground transition-colors flex items-center gap-1"
        >
          <X className="w-3 h-3" /> {isAudience ? 'Tự chọn' : isSetup ? 'Chỉnh sửa' : 'Hủy'}
        </button>
        {decision === 'failed' && <span className="self-center text-[10px] font-semibold text-red-600">Cập nhật thất bại · thử lại</span>}
      </div>}
    </div>
  )
}

// ─── Report Analysis Block ────────────────────────────────────────────────────
function ReportAnalysisBlock({ block }) {
  const sections = block.sections || []
  return (
    <Card className="border-violet-200 bg-gradient-to-br from-violet-50/50 to-indigo-50/50 overflow-hidden">
      {block.title && (
        <CardHeader className="px-3.5 pb-2.5 pt-3.5 flex-row items-start gap-2 border-b border-violet-100/80">
          <BarChart className="w-4 h-4 mt-0.5 text-violet-500 flex-shrink-0" />
          <CardTitle className="text-[13px] leading-snug text-violet-800 font-bold break-words">{block.title}</CardTitle>
        </CardHeader>
      )}
      <CardContent className="pt-3 px-3.5 pb-3.5 space-y-3">
        {sections.map((section, i) => {
          switch (section.type) {
            case 'summary':
            case 'paragraph':
              return (
                <div key={i} className="markdown-content text-xs text-foreground leading-relaxed [&_p]:my-0 [&_ul]:my-1 [&_ol]:my-1">
                  <ReactMarkdown>{section.text || ''}</ReactMarkdown>
                </div>
              )
            case 'heading':
              return (
                <p key={i} className="text-xs font-bold text-foreground pt-0.5">
                  {section.text}
                </p>
              )
            case 'metrics': {
              const items = section.items || []
              const useSingleColumn = items.some(m =>
                String(m.label || '').length > 24 ||
                String(m.value || '').length > 18 ||
                String(m.delta || '').length > 22
              )
              return (
                <div key={i} className={`grid gap-2 ${useSingleColumn ? 'grid-cols-1' : 'grid-cols-2'}`}>
                  {items.map((m, j) => {
                    const delta = String(m.delta || '').trim()
                    const showTrend = Boolean(
                      m.trend &&
                      delta &&
                      !/^(?:0(?:[.,]0+)?%?|n\/?a|—|-)$/i.test(delta)
                    )
                    return (
                    <div key={j} className="p-2.5 rounded-lg bg-white/90 border border-violet-100 shadow-sm min-w-0">
                      <div className="w-full min-w-0">
                        <p className="text-[10px] leading-snug text-muted-foreground font-semibold break-words">{m.label}</p>
                        <p className="mt-0.5 text-sm leading-snug font-bold text-foreground break-words">{m.value}</p>
                        {showTrend && (
                          <div className={`mt-1 flex items-start gap-1 text-[10px] leading-snug font-semibold min-w-0 ${
                            m.trend === 'up' ? 'text-green-600' : m.trend === 'down' ? 'text-red-600' : 'text-muted-foreground'
                          }`}>
                            {m.trend === 'up' ? <TrendingUp className="w-3 h-3 mt-px flex-shrink-0" /> :
                             m.trend === 'down' ? <TrendingDown className="w-3 h-3 mt-px flex-shrink-0" /> : null}
                            <span className="min-w-0 break-words">{delta}</span>
                          </div>
                        )}
                      </div>
                    </div>
                    )
                  })}
                </div>
              )
            }
            case 'insight':
              return (
                <div key={i} className={`flex items-start gap-1.5 p-2.5 rounded-lg border text-xs leading-relaxed font-medium ${
                  section.level === 'good' ? 'bg-green-50 border-green-200 text-green-800' :
                  section.level === 'bad' || section.level === 'warning' ? 'bg-amber-50 border-amber-200 text-amber-800' :
                  'bg-blue-50 border-blue-200 text-blue-800'
                }`}>
                  <span className="flex-shrink-0">{section.level === 'good' ? '✅' : section.level === 'bad' || section.level === 'warning' ? '⚠️' : '💡'}</span>
                  <div className="markdown-content min-w-0 [&_p]:my-0"><ReactMarkdown>{section.text || ''}</ReactMarkdown></div>
                </div>
              )
            case 'comparison':
              return (
                <div key={i} className="overflow-x-auto rounded-lg border border-violet-100 bg-white/80">
                  {section.title && <p className="text-[10px] font-semibold text-muted-foreground px-2.5 pt-2">{section.title}</p>}
                  <table className="w-full min-w-[420px] text-[11px]">
                    <thead>
                      <tr className="border-b border-violet-100 bg-violet-50/60">
                        {(section.headers || []).map((h, hi) => (
                          <th key={hi} className="text-left py-2 px-2.5 font-semibold text-violet-800 whitespace-nowrap">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {(section.rows || []).map((row, ri) => (
                        <tr key={ri} className="border-b border-border/50 last:border-0 even:bg-slate-50/60">
                          {(Array.isArray(row) ? row : []).map((cell, ci) => (
                            <td key={ci} className="py-2 px-2.5 align-top leading-snug">{cell}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            case 'recommendation':
              return (
                <div key={i} className="space-y-1">
                  {(section.items || []).map((r, ri) => (
                    <div key={ri} className={`flex items-start gap-2 p-2.5 rounded-lg border ${
                      r.priority === 'high' ? 'bg-red-50 border-red-200' :
                      r.priority === 'medium' ? 'bg-amber-50 border-amber-200' :
                      'bg-blue-50 border-blue-200'
                    }`}>
                      <Badge variant={r.priority === 'high' ? 'destructive' : r.priority === 'medium' ? 'yellow' : 'default'}
                             className="text-[8px] px-1.5 py-0 flex-shrink-0 mt-0.5">
                        {r.priority === 'high' ? '🔴 Cao' : r.priority === 'medium' ? '🟡 TB' : '🟢 Thấp'}
                      </Badge>
                      <div className="markdown-content text-[11px] leading-relaxed text-foreground [&_p]:my-0 [&_ul]:my-1">
                        <ReactMarkdown>{r.text || ''}</ReactMarkdown>
                      </div>
                    </div>
                  ))}
                </div>
              )
            default:
              return section.text ? (
                <div key={i} className="markdown-content text-xs leading-relaxed text-muted-foreground [&_p]:my-0">
                  <ReactMarkdown>{section.text}</ReactMarkdown>
                </div>
              ) : null
          }
        })}
      </CardContent>
    </Card>
  )
}


export default function BlockRenderer({ block }) {
  switch (block.type) {
    case 'table':              return <TableBlock block={block} />
    case 'chart':              return <ChartBlock block={block} />
    case 'audience_size':      return <AudienceSizeBlock block={block} />
    case 'campaign_list':      return <CampaignListBlock block={block} />
    case 'verdict':            return <VerdictBlock block={block} />
    case 'info':               return <InfoBlock block={block} />
    case 'email_preview':      return <EmailPreviewBlock block={block} />
    case 'action_reset':       return <ActionResetBlock block={block} />
    case 'workspace_proposal': return <WorkspaceProposalBlock block={block} />
    case 'report_analysis':    return <ReportAnalysisBlock block={block} />
    default: return null
  }
}
