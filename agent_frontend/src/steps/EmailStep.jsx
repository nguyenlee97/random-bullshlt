import { useState, useEffect, useCallback } from 'react'
import { AgentAPI } from '@/api/agentApi'
import { fmt } from '@/lib/utils'
import {
  Mail, Send, Loader2, Check, Download, FileText,
  FileJson, FileSpreadsheet, ChevronDown, ChevronUp,
  AlertCircle, RefreshCw, Paperclip,
} from 'lucide-react'

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:3000'

// ── Sub-components ─────────────────────────────────────────────────────────────

function KpiBadge({ label, value, color }) {
  return (
    <div style={{ borderColor: color + '33', background: color + '11' }}
      className="flex-1 rounded-xl border px-3 py-2 text-center min-w-[80px]">
      <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-0.5">{label}</p>
      <p className="text-sm font-black" style={{ color }}>{value}</p>
    </div>
  )
}

function SectionBadge({ icon, label, color }) {
  return (
    <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-1 rounded-full"
      style={{ background: color + '18', color }}>
      {icon} {label}
    </span>
  )
}

function AttachToggle({ icon: Icon, label, description, checked, onChange, disabled }) {
  return (
    <label className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-all
      ${checked ? 'border-indigo-400 bg-indigo-50' : 'border-border bg-white hover:border-indigo-200'}
      ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}>
      <div className={`w-4 h-4 mt-0.5 rounded border-2 flex items-center justify-center flex-shrink-0 transition-colors
        ${checked ? 'bg-indigo-500 border-indigo-500' : 'border-muted-foreground'}`}>
        {checked && <Check className="w-2.5 h-2.5 text-white" strokeWidth={3} />}
      </div>
      <input type="checkbox" className="sr-only" checked={checked} onChange={e => onChange(e.target.checked)} disabled={disabled} />
      <Icon className="w-4 h-4 mt-0.5 flex-shrink-0 text-indigo-500" />
      <div>
        <p className="text-xs font-semibold text-foreground">{label}</p>
        <p className="text-[10px] text-muted-foreground mt-0.5">{description}</p>
      </div>
    </label>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function EmailStep({ brief, zones, selectedZoneIds, audiences, data, onChange, isDone, formState }) {
  const [email, setEmail]       = useState(data?.email || '')
  const [cc, setCc]             = useState(data?.cc || '')
  const [attachCsv, setAttachCsv]   = useState(false)
  const [attachJson, setAttachJson] = useState(false)
  const [sending, setSending]   = useState(false)
  const [sent, setSent]         = useState(data?.sent || false)
  const [sentResult, setSentResult] = useState(data?.sentResult || null)
  const [error, setError]       = useState('')
  const [showCc, setShowCc]     = useState(false)
  const [showSections, setShowSections] = useState(false)

  const campaignId = formState?.report?.campaignId || data?.campaignId || ''
  const brand      = brief?.brand || 'Unknown'
  const objective  = brief?.objective || 'awareness'

  // Pre-fill email from brief brand
  useEffect(() => {
    if (!email && brand && brand !== 'Unknown') {
      const slug = brand.toLowerCase().replace(/\s+/g, '').replace(/-/g, '')
      setEmail(`${slug}@adtima.vn`)
    }
  }, [brand])

  const handleSend = useCallback(async () => {
    if (!email.trim()) { setError('Vui lòng nhập địa chỉ email'); return }
    if (!email.includes('@')) { setError('Email không hợp lệ'); return }
    setError('')
    setSending(true)
    try {
      const res = await fetch(`${BACKEND_URL}/api/reports/send-email/${campaignId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), cc: cc.trim() || undefined, attachCsv, attachJson }),
        signal: AbortSignal.timeout(90000),
      })
      const json = await res.json()
      if (!res.ok || json.error) throw new Error(json.error || `HTTP ${res.status}`)
      setSent(true)
      setSentResult(json)
      onChange({ sent: true, email: email.trim(), sentResult: json, campaignId })
    } catch (e) {
      setError(e.message || 'Gửi thất bại')
    } finally {
      setSending(false)
    }
  }, [email, cc, attachCsv, attachJson, campaignId, onChange])

  const reportSections = [
    { icon: '📊', label: 'Daily Ops',      color: '#3b82f6' },
    { icon: '👁',  label: 'Awareness',     color: '#8b5cf6' },
    { icon: '🖱',  label: 'Consideration', color: '#f59e0b' },
    { icon: '🎯',  label: 'Conversion',    color: '#10b981' },
    { icon: '🔄',  label: 'Retention',     color: '#ec4899' },
    { icon: '💼',  label: 'Executive',     color: '#6366f1' },
  ]

  // ── Sent state ───────────────────────────────────────────────────────────────
  if (sent && sentResult) {
    const attachments = ['PDF']
    if (attachCsv)  attachments.push('CSV')
    if (attachJson) attachments.push('JSON')

    return (
      <div className="space-y-4">
        {/* Success card */}
        <div className="rounded-2xl border border-emerald-200 bg-gradient-to-br from-emerald-50 to-teal-50 p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-full bg-emerald-500 flex items-center justify-center flex-shrink-0">
              <Check className="w-5 h-5 text-white" strokeWidth={3} />
            </div>
            <div>
              <p className="text-sm font-black text-emerald-800">Email đã gửi thành công!</p>
              <p className="text-[11px] text-emerald-600">{new Date().toLocaleString('vi-VN')}</p>
            </div>
          </div>
          <div className="space-y-1.5 text-xs text-emerald-800">
            <p><span className="font-semibold">📬 Đến:</span> {sentResult.to || email}</p>
            {cc && <p><span className="font-semibold">CC:</span> {cc}</p>}
            <p><span className="font-semibold">📎 File:</span> {attachments.join(', ')}</p>
            {sentResult.messageId && (
              <p className="font-mono text-[10px] text-emerald-600">ID: {sentResult.messageId}</p>
            )}
          </div>
        </div>

        {/* Download links */}
        <div className="rounded-xl border border-border p-4 space-y-2">
          <p className="text-xs font-bold text-foreground mb-3">📥 Tải xuống trực tiếp</p>
          <a
            href={`${BACKEND_URL}/api/reports/export/${campaignId}/pdf`}
            target="_blank" rel="noreferrer"
            className="flex items-center gap-2.5 w-full px-4 py-2.5 rounded-xl border border-indigo-200 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs font-semibold transition-colors"
          >
            <FileText className="w-4 h-4" /> Download PDF Report
          </a>
          <a
            href={`${BACKEND_URL}/api/reports/export/${campaignId}/csv`}
            target="_blank" rel="noreferrer"
            className="flex items-center gap-2.5 w-full px-4 py-2.5 rounded-xl border border-emerald-200 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 text-xs font-semibold transition-colors"
          >
            <FileSpreadsheet className="w-4 h-4" /> Download CSV Data
          </a>
          <a
            href={`${BACKEND_URL}/api/reports/export/${campaignId}/json`}
            target="_blank" rel="noreferrer"
            className="flex items-center gap-2.5 w-full px-4 py-2.5 rounded-xl border border-amber-200 bg-amber-50 hover:bg-amber-100 text-amber-700 text-xs font-semibold transition-colors"
          >
            <FileJson className="w-4 h-4" /> Download JSON Data
          </a>
        </div>

        {/* Re-send button */}
        <button
          onClick={() => { setSent(false); setSentResult(null) }}
          className="flex items-center gap-2 w-full justify-center px-4 py-2 rounded-xl border border-border text-xs text-muted-foreground hover:bg-muted transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Gửi lại hoặc gửi đến email khác
        </button>
      </div>
    )
  }

  // ── Compose state ─────────────────────────────────────────────────────────────
  return (
    <div className="space-y-4">

      {/* Report preview card */}
      <div className="rounded-2xl border border-indigo-100 bg-gradient-to-br from-indigo-50/60 to-purple-50/40 p-4">
        <div className="flex items-start gap-3 mb-3">
          <div className="w-9 h-9 rounded-xl bg-indigo-500 flex items-center justify-center flex-shrink-0">
            <FileText className="w-4 h-4 text-white" />
          </div>
          <div>
            <p className="text-sm font-black text-foreground">Báo cáo sẵn sàng để gửi</p>
            <p className="text-[11px] text-muted-foreground">Campaign: <span className="font-semibold text-indigo-600">{campaignId || '—'}</span></p>
          </div>
        </div>

        {/* Sections preview */}
        <button
          onClick={() => setShowSections(v => !v)}
          className="flex items-center gap-1 text-[11px] text-indigo-600 font-semibold mb-2 hover:text-indigo-800 transition-colors"
        >
          {showSections ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          {showSections ? 'Ẩn' : 'Xem'} nội dung PDF
        </button>
        {showSections && (
          <div className="flex flex-wrap gap-1.5 mt-1 mb-2">
            {reportSections.map(s => (
              <SectionBadge key={s.label} icon={s.icon} label={s.label} color={s.color} />
            ))}
            <SectionBadge icon="📋" label="Zone Table" color="#374151" />
            <SectionBadge icon="📈" label="Sparklines" color="#374151" />
          </div>
        )}

        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <div className="w-2 h-2 rounded-full bg-emerald-500" />
            Dữ liệu từ MongoDB
          </div>
          <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <div className="w-2 h-2 rounded-full bg-indigo-500" />
            AI analysis 6 hạng mục
          </div>
        </div>
      </div>

      {/* Email input */}
      <div className="rounded-xl border border-border bg-white p-4 space-y-3">
        <p className="text-xs font-bold text-foreground flex items-center gap-2">
          <Mail className="w-3.5 h-3.5 text-indigo-500" /> Thông tin gửi
        </p>

        <div className="space-y-1">
          <label className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">Email nhận báo cáo *</label>
          <input
            id="email-to-input"
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="example@company.com"
            className="w-full px-3 py-2 text-sm border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400 transition-all"
          />
        </div>

        <button
          onClick={() => setShowCc(v => !v)}
          className="text-[11px] text-indigo-500 hover:text-indigo-700 font-medium flex items-center gap-1"
        >
          {showCc ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          {showCc ? 'Ẩn CC' : '+ Thêm CC'}
        </button>

        {showCc && (
          <div className="space-y-1">
            <label className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">CC (tùy chọn)</label>
            <input
              type="email"
              value={cc}
              onChange={e => setCc(e.target.value)}
              placeholder="cc@company.com"
              className="w-full px-3 py-2 text-sm border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-all"
            />
          </div>
        )}
      </div>

      {/* Attachment options */}
      <div className="space-y-2">
        <p className="text-xs font-bold text-foreground flex items-center gap-2">
          <Paperclip className="w-3.5 h-3.5 text-indigo-500" /> File đính kèm
        </p>

        <AttachToggle
          icon={FileText}
          label="PDF Report (bắt buộc)"
          description="Báo cáo đầy đủ: cover, KPI, 6 tab phân tích AI, zone table"
          checked={true}
          onChange={() => {}}
          disabled={true}
        />
        <AttachToggle
          icon={FileSpreadsheet}
          label="CSV Raw Data"
          description="Toàn bộ analytics records dạng bảng — dùng cho Excel/BI tools"
          checked={attachCsv}
          onChange={setAttachCsv}
        />
        <AttachToggle
          icon={FileJson}
          label="JSON Raw Data"
          description="Toàn bộ analytics records dạng JSON — dùng cho developers"
          checked={attachJson}
          onChange={setAttachJson}
        />
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 p-3 rounded-xl border border-red-200 bg-red-50 text-xs text-red-700">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Action buttons */}
      <div className="flex gap-2">
        <button
          id="send-email-btn"
          onClick={handleSend}
          disabled={sending || !email}
          className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-500 hover:bg-indigo-600 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-semibold transition-all shadow-sm hover:shadow"
        >
          {sending
            ? <><Loader2 className="w-4 h-4 animate-spin" /> Đang tạo PDF & gửi...</>
            : <><Send className="w-4 h-4" /> Gửi báo cáo</>
          }
        </button>

        {campaignId && (
          <a
            href={`${BACKEND_URL}/api/reports/export/${campaignId}/pdf`}
            target="_blank" rel="noreferrer"
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-border bg-white hover:bg-muted text-xs font-semibold text-foreground transition-all"
          >
            <Download className="w-4 h-4" /> PDF
          </a>
        )}
      </div>

      {sending && (
        <p className="text-[11px] text-center text-muted-foreground animate-pulse">
          ⏳ Đang tạo PDF từ dữ liệu MongoDB... có thể mất 10-20 giây
        </p>
      )}
    </div>
  )
}
