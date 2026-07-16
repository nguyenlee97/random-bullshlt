import { MessageSquare, Download } from 'lucide-react'
import ChatThread from './ChatThread'
import ChatComposer from './ChatComposer'

// ─── Global fetch interceptor ─────────────────────────────────────────────────
// Installed once per page load. Captures all fetch() calls (DMP, agent, campaigns).
const _networkLog = []
if (typeof window !== 'undefined' && !window.__fetchIntercepted) {
  window.__fetchIntercepted = true
  const _origFetch = window.fetch
  window.fetch = async function (...args) {
    const url = typeof args[0] === 'string' ? args[0] : args[0]?.url || '?'
    const method = args[1]?.method || 'GET'
    const reqBody = args[1]?.body || null
    const t0 = Date.now()
    let status = null
    let responsePreview = null
    try {
      const res = await _origFetch(...args)
      status = res.status
      // Capture a clone of small JSON responses (skip large/binary)
      try {
        const clone = res.clone()
        const ct = res.headers.get('content-type') || ''
        if (ct.includes('json')) {
          const json = await clone.json()
          // Only keep first 500 chars to avoid bloat
          responsePreview = JSON.stringify(json).slice(0, 500)
        }
      } catch { /* ignore */ }
      _networkLog.push({
        ts: new Date().toISOString(),
        method,
        url,
        status,
        duration_ms: Date.now() - t0,
        req_body: reqBody ? String(reqBody).slice(0, 300) : null,
        res_preview: responsePreview,
      })
      return res
    } catch (err) {
      _networkLog.push({
        ts: new Date().toISOString(),
        method,
        url,
        status: 'NETWORK_ERROR',
        duration_ms: Date.now() - t0,
        error: err.message,
      })
      throw err
    }
  }
  // Expose log globally so export can reference it
  window.__networkLog = _networkLog
}

// ─── Export chat log ──────────────────────────────────────────────────────────
function exportChatLog(messages) {
  const AGENT_URL = import.meta.env.VITE_AGENT_URL || 'http://localhost:8000'

  // Attempt to pull session logs from backend
  const sessionId = window.__AGENT_SESSION_ID__ || 'unknown'

  const exportData = {
    export_time: new Date().toISOString(),
    session_id: sessionId,
    agent_url: AGENT_URL,

    // ── Conversation transcript ─────────────────────────────────────
    conversation: messages.map((m, i) => ({
      index: i,
      role: m.role,           // 'user' | 'assistant' | 'thinking'
      content: m.content,
      timestamp: m.timestamp,
      metadata: m.metadata || null,
      blocks: (m.blocks || []).map(b => ({
        type: b.type,
        // Include table rows, text, etc for debugging
        ...(b.title && { title: b.title }),
        ...(b.columns && { columns: b.columns }),
        ...(b.rows && { rows: b.rows }),
        ...(b.text && { text: b.text }),
        ...(b.campaigns && { campaigns: b.campaigns }),
        ...(b.metrics && { metrics: b.metrics }),
        ...(b.size !== undefined && { size: b.size }),
      })),
    })),

    // ── Tool call summary ───────────────────────────────────────────
    tools_used: messages
      .filter(m => m.metadata?.tool)
      .map(m => ({
        tool: m.metadata.tool,
        model: m.metadata.model,
        step: m.metadata.step,
        timestamp: m.timestamp,
      })),

    // ── Debug tips ──────────────────────────────────────────────────
    debug_info: {
      total_messages: messages.length,
      agent_messages: messages.filter(m => m.role === 'assistant').length,
      user_messages: messages.filter(m => m.role === 'user').length,
      fetch_backend_logs: `GET ${AGENT_URL}/api/agent/logs/${sessionId}`,
    },

    // ── Network log (all fetch/XHR — like DevTools Network tab) ─────
    // Captured by the fetch interceptor installed at page load
    network_log: (window.__networkLog || []).map(entry => ({
      ts: entry.ts,
      method: entry.method,
      url: entry.url,
      status: entry.status,
      duration_ms: entry.duration_ms,
      ...(entry.req_body && { req_body: entry.req_body }),
      ...(entry.res_preview && { res_preview: entry.res_preview }),
      ...(entry.error && { error: entry.error }),
    })),
  }

  // Trigger download
  const json = JSON.stringify(exportData, null, 2)
  const blob = new Blob([json], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `advertising-agent-log-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.json`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// ─── ChatPane ───────────────────────────────────────────────────────────────────────────────
export default function ChatPane({ messages, busy, currentStep, onSend, onBack, onRetry, canRetry, policy = { mode: 'normal' } }) {
  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Pane header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border bg-white/80 flex-shrink-0">
          <MessageSquare className="w-4 h-4 text-blue-500" />
          <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Chat</span>
          <span className="ml-1 text-xs text-muted-foreground">· Trao đổi với Agent</span>

          <div className="ml-auto flex items-center gap-2">
            {busy && (
              <span className="text-[11px] font-semibold text-brand-600 animate-pulse">
                ● Đang xử lý...
              </span>
            )}

            {/* Export button — hidden on mobile to save space */}
            <button
              onClick={() => exportChatLog(messages)}
              disabled={messages.length === 0}
              title="Xuất log chat (JSON)"
              className="hidden md:flex items-center gap-1 text-[11px] font-semibold text-muted-foreground border border-border rounded-full px-2 py-1 hover:bg-muted/60 hover:text-foreground transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
              id="export-chat-btn"
            >
              <Download className="w-3 h-3" />
              Export log
            </button>
          </div>
        </div>

      {/* Thread — always visible */}
      <div className="flex flex-col flex-1 min-h-0 bg-gradient-to-b from-slate-50/50 to-white">
        <ChatThread messages={messages} canRetry={canRetry} onRetry={onRetry} onSend={onSend} />
      </div>

      {/* Composer — always visible */}
      <ChatComposer busy={busy} currentStep={currentStep} onSend={onSend} onBack={onBack} policy={policy} />
    </div>
  )
}
