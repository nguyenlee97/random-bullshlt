import { fmt, generateId } from '@/lib/utils'
import log from '@/lib/logger'
import { normalizeDmpAttr } from '@/lib/audience'
import { isRetryableCreativeAnalysisFailure } from '@/lib/creativeIntel'
import {
  creativeUploadIdempotencyKey,
  OPENAI_CREATIVE_UPLOAD_MAX_ATTEMPTS,
  OPENAI_CREATIVE_UPLOAD_TIMEOUT_MS,
  shouldRetryCreativeUpload,
} from '@/lib/creativeUploadPolicy'

export { normalizeDmpAttr } from '@/lib/audience'

// ─── Real Agent API client ────────────────────────────────────────────────────
const AGENT_URL = import.meta.env.VITE_AGENT_URL || 'http://localhost:8080'
// AdsPilot backend (for /api/creative/upload)
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:3000'
const DEMO_NAMESPACE = String(import.meta.env.VITE_DEMO_NAMESPACE || '')
  .toLowerCase().replace(/[^a-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 32)

const STORAGE_PREFIX = `advertising-agent${DEMO_NAMESPACE ? `:${DEMO_NAMESPACE}` : ''}`
const storageGet = key => {
  try { return window.localStorage.getItem(`${STORAGE_PREFIX}:${key}`) || '' } catch { return '' }
}
const storageSet = (key, value) => {
  try {
    if (value) window.localStorage.setItem(`${STORAGE_PREFIX}:${key}`, value)
    else window.localStorage.removeItem(`${STORAGE_PREFIX}:${key}`)
  } catch {}
}

// Migration-only: builds before FE-2 briefly stored this token in localStorage.
// New identities are issued only as an HttpOnly cookie by the server.
let LEGACY_ANONYMOUS_TOKEN = typeof window !== 'undefined' ? storageGet('anonymous-token') : ''
let CURRENT_CONVERSATION_ID = typeof window !== 'undefined' ? storageGet('conversation-id') : ''
const STORED_SESSION_ID = typeof window !== 'undefined' ? storageGet('session-id') : ''
let IDENTITY_BOOTSTRAP_PROMISE = null
let IDENTITY_BOOTSTRAP_RESULT = null

const cookieGet = name => {
  if (typeof document === 'undefined') return ''
  const prefix = `${encodeURIComponent(name)}=`
  const item = document.cookie.split(';').map(value => value.trim())
    .find(value => value.startsWith(prefix))
  if (!item) return ''
  try { return decodeURIComponent(item.slice(prefix.length)) } catch { return '' }
}

const agentFetch = async (url, opts = {}) => {
  const method = String(opts.method || 'GET').toUpperCase()
  const unsafe = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)
  const send = () => {
    const csrf = unsafe ? cookieGet('aa_csrf') : ''
    return fetch(url, {
      ...opts,
      credentials: 'include',
      headers: {
        ...(LEGACY_ANONYMOUS_TOKEN ? { 'X-Anonymous-Token': LEGACY_ANONYMOUS_TOKEN } : {}),
        ...(opts.headers || {}),
        ...(csrf ? { 'X-CSRF-Token': csrf } : {}),
      },
    })
  }

  let response = await send()
  if (!unsafe || response.status !== 403) return response
  const failure = await response.clone().json().catch(() => ({}))
  if (failure?.error !== 'csrf_failed') return response

  // The 403 response rotates the readable double-submit cookie. Re-read it
  // and retry once; the rejected first request never reached application code.
  response = await send()
  return response
}

async function responseError(response, fallback) {
  const data = await response.json().catch(() => ({}))
  const detail = data?.detail
  const error = new Error(detail?.message || detail || fallback)
  error.status = response.status
  error.data = data
  return error
}

const withRequestId = (data, response) => ({
  ...data,
  request_id: response.headers.get('x-request-id') || data?.request_id || null,
})

let _agentReachable = null // null=unknown, true/false after first probe

async function probeAgent() {
  if (_agentReachable !== null) return _agentReachable
  try {
    const r = await agentFetch(`${AGENT_URL}/api/health`, { signal: AbortSignal.timeout(2000) })
    _agentReachable = r.ok
  } catch {
    _agentReachable = false
  }
  return _agentReachable
}

async function probeVersion() {
  try {
    const r = await agentFetch(`${AGENT_URL}/api/version`, { signal: AbortSignal.timeout(3000) })
    if (!r.ok) return
    const data = await r.json()
    // Big, visible log so you can confirm the deployed backend version instantly
    console.log(
      `%c🚀 BACKEND v${data.version}%c  ${AGENT_URL}`,
      'background:#0068ff;color:#fff;font-size:13px;font-weight:bold;padding:3px 10px;border-radius:4px',
      'color:#6b7280;font-size:11px',
    )
    log.api('VERSION CHECK', {
      version: data.version,
      features: data.features,
      agent_url: AGENT_URL,
    })
  } catch (e) {
    log.error('version probe failed', e.message)
  }
}

// Probe version immediately on module load
probeVersion()


/**
 * Call real agent backend. Returns null on failure (caller falls back to mock).
 * @param {Object} payload  ChatRequest body
 */
async function callAgent(payload) {
  const t0 = Date.now()
  log.api('callAgent → request', {
    step: payload.step,
    message: payload.message?.slice(0, 120),
    has_workspace: !!payload.workspace,
    confirmed_steps: payload.confirmed_steps,
    workspace_events: payload.workspace_events,
    formData: payload.formData,
  })
  try {
    const res = await agentFetch(`${AGENT_URL}/api/agent/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(180000),
    })
    if (!res.ok) {
      log.error(`callAgent HTTP ${res.status}`, { status: res.status, payload })
      return null
    }
    const data = await res.json()
    const duration = Date.now() - t0
    log.api('callAgent ← response', {
      duration_ms: duration,
      tool: data.meta?.tool,
      model: data.meta?.model,
      text_preview: (data.text || '').slice(0, 200),
      blocks: (data.blocks || []).map(b => b.type),
      workspace_update: data.workspace_update,
    })
    if (data.workspace_update) {
      log.workspace('workspace_update received from API', data.workspace_update)
    }
    // Normalise to frontend message format
    return {
      id: generateId(),
      role: 'assistant',
      content: data.text || '',
      blocks: data.blocks || [],
      timestamp: new Date().toISOString(),
      metadata: {
        tool: data.meta?.tool || null,
        model: data.meta?.model || 'minimax',
        step: data.meta?.step ?? null,
      },
      workspace_update: data.workspace_update || null,
      // Proposal cards own approve/reject actions. Repeating confirmation as
      // quick-reply chips creates two competing control paths for one mutation.
      suggestions: (data.blocks || []).some(block => block.type === 'workspace_proposal')
        ? []
        : (data.suggestions || []),
    }
  } catch (err) {
    log.error('callAgent failed', { error: err.message, duration_ms: Date.now() - t0 })
    _agentReachable = false
    return null
  }
}



// ─── DMP Attributes from real backend ────────────────────────────────────────
const DMP_FALLBACK = [
  { code: 'INT001', name: 'Du lịch · SEA', type: 'interest', category: 'Travel', est_size: 1850000 },
  { code: 'INT002', name: 'Du lịch quốc tế', type: 'interest', category: 'Travel', est_size: 2200000 },
  { code: 'INT003', name: 'Khách sạn & Resort', type: 'interest', category: 'Travel', est_size: 1430000 },
  { code: 'BEH001', name: 'Người dùng thẻ tín dụng', type: 'behavior', category: 'Finance', est_size: 3100000 },
  { code: 'BEH002', name: 'Fintech · Giá trị cao', type: 'behavior', category: 'Finance', est_size: 680000 },
  { code: 'INT010', name: 'HCM / HN / ĐN', type: 'geo', category: 'Geographic', est_size: 5200000 },
  { code: 'INT020', name: 'Độ tuổi 25-44', type: 'demographic', category: 'Age', est_size: 8900000 },
  { code: 'BEH010', name: 'Premium Lifestyle', type: 'behavior', category: 'Lifestyle', est_size: 920000 },
  { code: 'INT050', name: 'Mua sắm online thường xuyên', type: 'interest', category: 'Shopping', est_size: 4100000 },
  { code: 'BEH005', name: 'Người dùng mobile banking', type: 'behavior', category: 'Finance', est_size: 2700000 },
  { code: 'INT030', name: 'Thể thao & Fitness', type: 'interest', category: 'Sports', est_size: 3300000 },
  { code: 'INT040', name: 'Ẩm thực & Nhà hàng', type: 'interest', category: 'Food', est_size: 4800000 },
]

// Unique audience reach is calculated only by POST /api/agent/audience/reach.
// The frontend keeps normalization helpers but owns no reach arithmetic.

// ─── Generate mock campaigns from brief ──────────────────────────────────────
function generateMockCampaigns(brief) {
  const totalBudget = brief.budget || 100
  const zones = [
    { zone: 'ZingNews Masthead', pct: 45, cpm: 55000, type: 'awareness' },
    { zone: 'BaoMoi Background', pct: 35, cpm: 48000, type: 'consideration' },
    { zone: 'ZingMP3 Masthead', pct: 20, cpm: 52000, type: 'awareness' },
  ]
  return zones.map((z, i) => ({
    id: `CA-${String(i + 1).padStart(3, '0')}`,
    name: `${brief.brand} · ${brief.objective === 'awareness' ? 'Nhận biết' : 'Chuyển đổi'} · ${z.zone}`,
    zone: z.zone,
    budget: Math.round(totalBudget * z.pct / 100),
    budgetPct: z.pct,
    cpm: z.cpm,
    status: 'draft',
    objective: brief.objective,
  }))
}

// ─── Agent message factory ────────────────────────────────────────────────────
function agentMessage(text, blocks = [], meta = {}) {
  return {
    id: generateId(),
    role: 'assistant',
    content: text,
    blocks,
    timestamp: new Date().toISOString(),
    metadata: {
      tool: meta.tool || null,
      model: meta.model || 'minimax',
      step: meta.step ?? null,
    },
  }
}

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

// ─── Mock agent scenarios ─────────────────────────────────────────────────────
export const AGENT_SCENARIOS = {

  // ── BOOT ──────────────────────────────────────────────────────────────────
  async boot(experienceMode = 'guided') {
    await delay(600)
    const isAutopilot = experienceMode === 'autopilot'
    const modeIntro = isAutopilot
      ? 'Bạn đang ở **Campaign Autopilot**. Agent sẽ dùng brief để xây dựng plan theo chế độ duyệt bạn chọn.'
      : 'Bạn đang ở **Campaign Copilot**. Bạn có thể hoàn thiện campaign từng phần và điều chỉnh mọi đề xuất trước khi áp dụng.'
    return agentMessage(
      `Xin chào 👋 Tôi là **Advertising Agent**.\n\n${modeIntro}\n\nMột brief hữu ích nên có **brand + sản phẩm/dịch vụ, mục tiêu, KPI, ngân sách, thời gian, đối tượng mục tiêu, thông điệp, creative, placement** và các lưu ý đặc biệt.\n\nNếu chưa biết một mục, hãy gửi phần bạn đang có và nhắn **“gợi ý giúp tôi phần còn thiếu”**.`,
      [],
      { tool: 'agent_boot', model: 'minimax', step: 0 }
    )
  },

  // ── CHAT REPLY (free text) ─────────────────────────────────────────────────
  async chat(text, currentStep, formState) {
    await delay(500 + Math.random() * 400)
    const t = text.toLowerCase()
    const stepNames = ['Brief', 'Creative', 'Audience', 'Setup Camp', 'Kết quả', 'Phân tích Report', 'Email']
    const stepName = stepNames[currentStep] || 'hiện tại'

    if (t.includes('giải thích') || t.includes('explain') || t.includes('là gì')) {
      const explanations = [
        'Bước **Brief** là nơi anh/chị điền thông tin chiến dịch: tên thương hiệu, mục tiêu (awareness/conversion/...), KPI mong muốn và ngân sách. Em sẽ dùng thông tin này để đề xuất audience và ad zones phù hợp.',
        'Bước **Creative** là nơi anh/chị upload nhiều hình ảnh / video quảng cáo. Creative sẽ được lưu vào storage và dùng ở bước Setup Camp để gắn vào từng zone.',
        'Bước **Audience** sử dụng DMP (Data Management Platform) với 310+ audience segments. Anh/Chị chọn attributes phù hợp, em tự tính audience size theo logic giao tệp.',
        'Bước **Setup Camp** em sẽ tự động phân bổ ngân sách vào 3 zone tối ưu CPM dựa trên objective. Anh/Chị có thể điều chỉnh và pause/run từng campaign.',
      ]
      return agentMessage(explanations[currentStep] || `Bước **${stepName}**: Em đang hỗ trợ anh/chị hoàn thành bước này. Tương tác với form ở panel phải và bấm **Đồng ý & Tiếp tục** khi xong.`, [], { model: 'minimax', step: currentStep })
    }

    if (t.includes('rủi ro') || t.includes('risk') || t.includes('lưu ý')) {
      return agentMessage(
        `⚠️ **Lưu ý ở bước ${stepName}:**\n\n- Dữ liệu không đầy đủ sẽ ảnh hưởng đến các bước sau\n- Em đã đặt validation — nút *Đồng ý* chỉ bật khi đủ điều kiện\n- Anh/Chị có thể quay lại bước trước bất cứ lúc nào để chỉnh sửa`,
        [],
        { model: 'minimax', step: currentStep }
      )
    }

    if (t.includes('budget') || t.includes('ngân sách')) {
      return agentMessage(
        'Về ngân sách, em sẽ tự động phân bổ theo công thức:\n\n- **45%** → Zone tin tức (Reach cao nhất)\n- **35%** → Zone giải trí (CPM tối ưu)\n- **20%** → Zone âm nhạc (Target chính xác)\n\nAnh/Chị có thể điều chỉnh % này ở bước Setup Camp.',
        [{ type: 'table', title: 'Phân bổ ngân sách gợi ý', columns: ['Zone', 'Tỷ lệ', 'CPM dự kiến'], rows: [['ZingNews Masthead', '45%', '55.000đ'], ['BaoMoi Background', '35%', '48.000đ'], ['ZingMP3 Masthead', '20%', '52.000đ']] }],
        { tool: 'budget_split', model: 'minimax', step: currentStep }
      )
    }

    if (t.includes('kpi') || t.includes('mục tiêu')) {
      return agentMessage(
        '**Gợi ý KPI theo objective:**\n\n- **Awareness** → Reach + VTR (View-Through Rate)\n- **Consideration** → Click + CTR + Engagement\n- **Conversion** → CPA + ROAS + Conversion Rate\n- **Retention** → Frequency + Return Visit Rate',
        [{ type: 'table', title: 'KPI theo mục tiêu', columns: ['Objective', 'KPI chính', 'KPI phụ'], rows: [['Awareness', 'Reach, VTR', 'Impression, Freq'], ['Consideration', 'CTR, Click', 'Engagement, VI%'], ['Conversion', 'CPA, ROAS', 'CVR, Revenue'], ['Retention', 'Frequency', 'Return Visit']] }],
        { tool: 'kpi_suggest', model: 'minimax', step: currentStep }
      )
    }

    if (t.includes('tiếp') || t.includes('next') || t.includes('đồng ý') || t.includes('xong')) {
      return agentMessage(
        `Anh/Chị bấm nút **"Đồng ý & Tiếp tục"** ở cuối panel phải để em xử lý và chuyển sang bước tiếp theo nhé! 👉`,
        [],
        { model: 'minimax', step: currentStep }
      )
    }

    if (t.includes('xin chào') || t.includes('hello') || t.includes('hi')) {
      return agentMessage(
        `Chào anh/chị! 👋 Em đang ở bước **${stepName}**. Anh/Chị cần hỗ trợ gì không?`,
        [],
        { model: 'minimax', step: currentStep }
      )
    }

    // Default
    return agentMessage(
      `Rõ — em đang ở bước **${stepName}**. Anh/Chị có thể tương tác với form ở panel phải và bấm **Đồng ý & Tiếp tục** khi hoàn tất. Nếu cần giải thích thêm, cứ hỏi em!`,
      [],
      { model: 'minimax', step: currentStep }
    )
  },

  // ── STEP APPROVALS ──────────────────────────────────────────────────────────

  async approveBrief(briefData) {
    await delay(1200)
    return agentMessage(
      `✅ Em đã phân tích brief của **${briefData.brand}**. Đây là tóm tắt chiến dịch:`,
      [
        {
          type: 'table',
          title: '📋 Brief Campaign',
          columns: ['Thuộc tính', 'Giá trị'],
          rows: [
            ['Thương hiệu', briefData.brand],
            ['Mục tiêu', briefData.objective === 'awareness' ? 'Tăng nhận biết (Awareness)' : briefData.objective === 'consideration' ? 'Tăng quan tâm (Consideration)' : briefData.objective === 'conversion' ? 'Chuyển đổi (Conversion)' : 'Giữ chân (Retention)'],
            ['KPI', briefData.kpi],
            ['Ngân sách', `${briefData.budget} triệu đồng`],
            ['Thời gian', briefData.startDate && briefData.endDate ? `${briefData.startDate} → ${briefData.endDate}` : briefData.startDate || '—'],
            ['Ghi chú', briefData.notes || '—'],
          ]
        },
        {
          type: 'info',
          text: '📸 Tiếp theo, anh/chị upload creative (hình ảnh / video) cho chiến dịch này nhé!'
        }
      ],
      { tool: 'brief_parse', model: 'minimax', step: 0 }
    )
  },

  async approveCreative(creativeData) {
    await delay(1000)
    const files = creativeData.files || []
    const fileRows = files.map((f, i) => [
      String(i + 1),
      f.name,
      f.type?.split('/')[1]?.toUpperCase() || 'FILE',
      f.width && f.height ? `${f.width}×${f.height}px` : `${(f.size / 1024).toFixed(0)} KB`,
      '✅ Đã duyệt',
    ])
    return agentMessage(
      `✅ **${files.length} creative** đã được upload và kiểm tra thành công! Em đã xác minh format và kích thước.`,
      [
        {
          type: 'table',
          title: '🎨 Creative đã upload',
          columns: ['#', 'Tên file', 'Định dạng', 'Kích thước', 'Trạng thái'],
          rows: fileRows.length ? fileRows : [['—', '—', '—', '—', '—']],
        },
        {
          type: 'info',
          text: '🎯 Tiếp theo, anh/chị chọn audience segments từ DMP để nhắm mục tiêu chính xác!'
        }
      ],
      { tool: 'creative_upload', model: 'minimax', step: 1 }
    )
  },


  async approveAudience(selectedAttrs, audienceSize) {
    await delay(1500)
    const attrRows = selectedAttrs.map(a => [a.code || a._uid || '—', a.name || '—', fmt(a.est_size || 0), a.type || '—'])
    return agentMessage(
      `✅ Em đã tính toán audience size: **${fmt(audienceSize)} người dùng** dựa trên ${selectedAttrs.length} attributes được chọn.`,
      [
        {
          type: 'table',
          title: '🎯 Audience Segments đã chọn',
          columns: ['Mã', 'Tên segment', 'Size', 'Loại'],
          rows: attrRows
        },
        {
          type: 'audience_size',
          size: audienceSize,
          count: selectedAttrs.length
        },
        {
          type: 'info',
          text: '⚙️ Tiếp theo, em sẽ tạo campaign ads với ngân sách được phân bổ tối ưu!'
        }
      ],
      { tool: 'dmp_match', model: 'minimax', step: 2 }
    )
  },

  async createCampaigns(brief, setupData) {
    await delay(2000)
    const zoneIds = setupData?.selectedZoneIds || []
    const recoZones = setupData?.recoZones || []
    const count = zoneIds.length || 3
    const budgetPerZone = count > 0 ? (brief.budget || 0) / count : 0

    // Build mock campaign rows from zone data
    const campRows = zoneIds.map((id, i) => {
      const zone = recoZones.find(z => z.id === id) || { name: id, cpm: 40000, reach: 10 }
      const est = Math.round((budgetPerZone * 1_000_000) / zone.cpm * 1000)
      return {
        id: `CAMP-${String(i + 1).padStart(3, '0')}`,
        name: `${brief.brand || 'Brand'} · ${zone.name}`,
        status: 'running',
        budget: budgetPerZone,
        reach: zone.reach,
        impressions: est,
        ctr: zone.ctr || 0,
      }
    })

    return agentMessage(
      `✅ Em đã tạo thành công **${count} ad orders** với tổng ngân sách **${brief.budget} triệu đồng**!`,
      [
        {
          type: 'campaign_list',
          campaigns: campRows,
        },
        {
          type: 'info',
          text: '🎉 Chiến dịch đã được khởi tạo! Anh/Chị xem tổng kết ở bước tiếp theo.',
        },
      ],
      { tool: 'camp_create', model: 'minimax', step: 3 }
    )
  },

  async approveSetup(setupData) {
    return AGENT_SCENARIOS.createCampaigns(
      { brand: 'Brand', budget: 100, objective: 'awareness' },
      setupData
    )
  },



  async runReport(brief) {
    await delay(2500)
    return agentMessage(
      `✅ Phân tích hoàn tất! Em đã xử lý **500 campaign** trong hệ thống và đưa ra đánh giá chi tiết.`,
      [
        {
          type: 'chart',
          chartType: 'bar',
          title: '📊 Performance theo tuần — Reach, CPM, CTR',
          data: {
            labels: ['Tuần 1', 'Tuần 2', 'Tuần 3', 'Tuần 4'],
            series: [
              { name: 'Reach (M)', color: '#1F7A3D', values: [1.2, 1.8, 2.1, 2.4] },
              { name: 'CPM (k VND)', color: '#9A6700', values: [58, 53, 52, 49] },
            ]
          }
        },
        {
          type: 'chart',
          chartType: 'line',
          title: '📈 CTR theo tuần (%)',
          data: {
            labels: ['Tuần 1', 'Tuần 2', 'Tuần 3', 'Tuần 4'],
            series: [
              { name: 'CTR (%)', color: '#185FA5', values: [1.1, 1.35, 1.42, 1.58] },
            ]
          }
        },
        {
          type: 'verdict',
          good: 312, watch: 96, bad: 92, total: 500
        },
        {
          type: 'table',
          title: '🧠 AI Đề xuất hành động',
          columns: ['#', 'Hành động', 'Ưu tiên'],
          rows: [
            ['1', 'Pause 92 camp "bad" — ưu tiên 12 camp tiêu lớn nhất', '🔴 Cao'],
            ['2', 'Scale +20% budget cho 312 camp "good" — CPM giảm dần', '🟢 Cao'],
            ['3', 'Re-test creative cho 96 camp "watch" — đổi angle', '🟡 Trung bình'],
            ['4', 'Shift budget sang zone Du lịch · CPM thấp nhất', '🟡 Trung bình'],
          ]
        }
      ],
      { tool: 'report_extract + chart_render', model: 'minimax', step: 5 }
    )
  },

  async sendEmail(brief, campaigns) {
    await delay(1000)
    return agentMessage(
      `✅ Email đã gửi thành công đến **account@adtima.vn** và **adopt@adtima.vn**!\n\nQuy trình hoàn tất 🎉`,
      [
        {
          type: 'email_preview',
          to: 'account@adtima.vn, adopt@adtima.vn',
          cc: `${(brief.brand || 'brand').toLowerCase().replace(/\s/g, '')}-pm@adtima.vn`,
          subject: `[Advertising Agent] Báo cáo & đề xuất ${brief.brand}`,
          body: `Hi Account & Ad Opt teams,

Advertising Agent đã hoàn tất setup + phân tích chiến dịch ${brief.brand}.

Tóm tắt:
• ${campaigns.length} campaigns đang chạy · Budget ${brief.budget}M · ${brief.duration} tuần
• Performance 500 camp tham chiếu: 312 good · 96 watch · 92 bad

Đề xuất ưu tiên:
1. Pause 92 camp 'bad'
2. Scale +20% budget cho 312 camp 'good'
3. Re-test creative cho 96 camp 'watch'
4. Shift budget sang zone Du lịch

— Advertising Agent`
        }
      ],
      { tool: 'email_compose + smtp_send', model: 'minimax', step: 6 }
    )
  },
}

// ─── Real DMP fetch (paginated, cached, correct field mapping) ───────────────
const DMP_BASE_URL = `${BACKEND_URL}/api/dmp/attributes`
let _dmpCache = null
let _dmpFetchPromise = null

/**
 * Normalize a raw DMP attribute from the real API.
 * Real API shape: { segmentId, type, category, name, fullLabel, sizeMin, sizeMax, sizeRaw }
 */
/**
 * Fetch ALL DMP attributes with pagination.
 * Uses module-level cache so multiple components don't trigger duplicate requests.
 */
export async function fetchDmpAttributes() {
  if (_dmpCache) return _dmpCache
  if (_dmpFetchPromise) return _dmpFetchPromise

  _dmpFetchPromise = (async () => {
    // The campaign backend returns a bounded list and does not implement
    // `page`; request its full supported range in one call.
    const PAGE_SIZE = 1000
    let allItems = []
    const seenIds = new Set()
    let page = 1

    try {
      while (true) {
        const qs = new URLSearchParams({ limit: PAGE_SIZE, page }).toString()
        const res = await fetch(`${DMP_BASE_URL}?${qs}`, {
          signal: AbortSignal.timeout(8000),
        })
        if (!res.ok) throw new Error(`DMP API error ${res.status}`)
        const json = await res.json()
        const items = Array.isArray(json) ? json : (json.data || json.items || [])
        if (!items.length) break

        // Detect duplicate pages: if ALL items in this page are already seen, stop
        const newItems = items.filter(it => {
          const id = it._id || it.segmentId || JSON.stringify(it)
          if (seenIds.has(id)) return false
          seenIds.add(id)
          return true
        })
        if (!newItems.length) {
          console.log(`[DMP] Duplicate page detected at page=${page}, stopping.`)
          break
        }
        allItems = allItems.concat(newItems)
        // Stop if returned fewer than PAGE_SIZE (last real page)
        if (items.length < PAGE_SIZE) break
        // Safety cap
        if (++page > 10) break
      }
      console.log(`[DMP] Loaded ${allItems.length} unique attributes`)
      _dmpCache = allItems.map(normalizeDmpAttr)
    } catch (err) {
      console.warn('[DMP] API failed, using fallback:', err.message)
      _dmpCache = DMP_FALLBACK.map(a => ({ ...a, _uid: a.code }))
    }

    return _dmpCache
  })()


  return _dmpFetchPromise
}

/**
 * Given a list of keyword strings (from AI targeting response),
 * returns up to `limit` DMP segments that best match by name/category.
 *
 * @param {string[]} keywords - e.g. ['Sports', 'Fashion', 'Entertainment']
 * @param {object[]} allAttrs  - normalized DMP segments (already loaded)
 * @param {number}   limit
 */
export function matchDmpByKeywords(keywords, allAttrs, limit = 6) {
  if (!keywords.length || !allAttrs.length) return []
  const kwLower = keywords.map(k => k.toLowerCase().trim())

  const scored = allAttrs.map(attr => {
    const haystack = `${attr.name} ${attr.category} ${attr.type}`.toLowerCase()
    let score = 0
    for (const kw of kwLower) {
      if (!kw || kw.length < 2) continue
      // Full word match scores more than partial
      if (haystack.includes(kw)) score += kw.length > 4 ? 4 : 2
      // Partial: first 4 chars match
      else if (kw.length >= 4 && haystack.includes(kw.slice(0, 4))) score += 1
    }
    return { attr, score }
  })

  return scored
    .filter(s => s.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map(s => s.attr)
}

/**
 * Given the blocks from a targeting_autopick AI response,
 * extract the interest/category keywords to use for DMP matching.
 */
export function extractTargetingKeywords(blocks) {
  const keywords = []
  for (const b of blocks || []) {
    if (b.type !== 'table' || !b.rows) continue
    for (const row of b.rows) {
      const group = String(row[0] || '').toLowerCase()
      const values = String(row[1] || '')
      if (group === 'interest' || group === 'category') {
        values.split(/[,>]/).forEach(v => keywords.push(v.trim()))
      }
    }
  }
  return keywords.filter(Boolean)
}

/**
 * Parse ALL rows from a targeting_autopick table into a structured map.
 * Returns: { geo: ['Hà Nội','TP.HCM'], age: ['18-24','25-34'], gender: [...], ... }
 */
export function extractTargetingMap(blocks) {
  const map = {}
  for (const b of blocks || []) {
    if (b.type !== 'table' || !b.rows) continue
    for (const row of b.rows) {
      const key = String(row[0] || '').trim().toLowerCase()
      const values = String(row[1] || '').trim()
      if (!key || !values) continue
      // Split on commas, handle "A > B" style by keeping full token
      map[key] = values.split(/\s*,\s*/).map(v => v.trim()).filter(Boolean)
    }
  }
  return map
}

/**
 * Session ID — regenerated on newChat/reset so backend history is always clean.
 */
function _genSessionId() {
  const namespace = DEMO_NAMESPACE ? `${DEMO_NAMESPACE}_` : ''
  return `sess_${namespace}${Date.now()}_${Math.random().toString(36).slice(2, 7)}`
}
let SESSION_ID = STORED_SESSION_ID || _genSessionId()
let WORKSPACE_REVISION = null
const _workspaceMutationKeys = new Map()

function _mutationKey(field, value) {
  const signature = `${field}:${JSON.stringify(value)}`
  const now = Date.now()
  for (const [key, entry] of _workspaceMutationKeys.entries()) {
    if (now - entry.createdAt > 60_000) _workspaceMutationKeys.delete(key)
  }
  if (!_workspaceMutationKeys.has(signature)) {
    const id = globalThis.crypto?.randomUUID?.()
      || `wmut_${now}_${Math.random().toString(36).slice(2)}`
    _workspaceMutationKeys.set(signature, { id, createdAt: now })
  }
  return _workspaceMutationKeys.get(signature).id
}

// Expose to window so ChatPane export can reference it
if (typeof window !== 'undefined') window.__AGENT_SESSION_ID__ = SESSION_ID

function applyConversationContext(context) {
  if (!context?.session_id || !context?.conversation_id) return context
  SESSION_ID = context.session_id
  CURRENT_CONVERSATION_ID = context.conversation_id
  WORKSPACE_REVISION = context.workspace?.revision ?? null
  _workspaceMutationKeys.clear()
  storageSet('session-id', SESSION_ID)
  storageSet('conversation-id', CURRENT_CONVERSATION_ID)
  if (typeof window !== 'undefined') {
    window.__AGENT_SESSION_ID__ = SESSION_ID
    window.__AGENT_CONVERSATION_ID__ = CURRENT_CONVERSATION_ID
  }
  return context
}

function clearConversationContext(conversationId = null) {
  if (conversationId && CURRENT_CONVERSATION_ID !== conversationId) return
  CURRENT_CONVERSATION_ID = ''
  SESSION_ID = _genSessionId()
  WORKSPACE_REVISION = null
  _workspaceMutationKeys.clear()
  storageSet('conversation-id', '')
  storageSet('session-id', '')
  if (typeof window !== 'undefined') {
    window.__AGENT_CONVERSATION_ID__ = ''
    window.__AGENT_SESSION_ID__ = SESSION_ID
  }
}

function conversationMessages(context) {
  const messages = (context?.messages || []).map(item => ({
    id: generateId(),
    role: item.role === 'user' ? 'user' : 'assistant',
    content: item.content || '',
    blocks: [],
    timestamp: item.timestamp || new Date().toISOString(),
    metadata: { tool: 'conversation_history', model: 'stored' },
  }))
  for (const proposal of context?.pending_proposals || []) {
    messages.push({
      id: generateId(),
      role: 'assistant',
      content: `Đề xuất cập nhật ${proposal.field || 'workspace'} này vẫn đang chờ Anh/Chị duyệt.`,
      blocks: [{
        type: 'workspace_proposal',
        changes: {
          proposal_id: proposal.proposal_id,
          field: proposal.field,
          value: proposal.value,
          reason: proposal.reason,
          status: proposal.status || 'pending',
        },
      }],
      timestamp: proposal.created_at || new Date().toISOString(),
      metadata: { tool: 'workspace_proposal_resume', model: 'stored' },
    })
  }
  return messages
}

async function bootstrapIdentity() {
  if (IDENTITY_BOOTSTRAP_RESULT) return IDENTITY_BOOTSTRAP_RESULT
  if (IDENTITY_BOOTSTRAP_PROMISE) return IDENTITY_BOOTSTRAP_PROMISE

  IDENTITY_BOOTSTRAP_PROMISE = (async () => {
    const response = await agentFetch(`${AGENT_URL}/api/agent/auth/anonymous`, {
      method: 'POST',
      signal: AbortSignal.timeout(5000),
    })
    if (!response.ok) throw new Error('Không thể khởi tạo danh tính ẩn danh.')
    const identity = await response.json()
    // The response has now installed an HttpOnly cookie. Remove any credential
    // left by the short-lived pre-cookie development build.
    LEGACY_ANONYMOUS_TOKEN = ''
    storageSet('anonymous-token', '')
    IDENTITY_BOOTSTRAP_RESULT = identity
    return identity
  })()

  try {
    return await IDENTITY_BOOTSTRAP_PROMISE
  } finally {
    IDENTITY_BOOTSTRAP_PROMISE = null
  }
}

async function fetchConversation(conversationId) {
  const response = await agentFetch(
    `${AGENT_URL}/api/agent/conversations/${encodeURIComponent(conversationId)}`,
    { signal: AbortSignal.timeout(10000) },
  )
  if (!response.ok) return null
  const context = applyConversationContext(await response.json())
  return { ...context, ui_messages: conversationMessages(context) }
}

async function createOwnedConversation({
  title = '', experienceMode = null, conversationModel = null,
} = {}) {
  const response = await agentFetch(`${AGENT_URL}/api/agent/conversations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title,
      experience_mode: experienceMode,
      conversation_model: conversationModel,
    }),
    signal: AbortSignal.timeout(5000),
  })
  if (!response.ok) throw new Error('Không thể tạo chiến dịch mới.')
  const created = await response.json()
  return fetchConversation(created.conversation_id)
}


/**
 * Fetch AI-powered DMP segment recommendations for the current session/brief.
 * Calls GET /api/agent/dmp-recommend?session_id=xxx
 * Returns array of segment objects (with _id, fullLabel, sizeMin, sizeMax, reason).
 */
export async function fetchDmpRecommendations() {
  try {
    const res = await agentFetch(
      `${AGENT_URL}/api/agent/dmp-recommend?session_id=${SESSION_ID}`,
      { signal: AbortSignal.timeout(180000) }  // LLM call — up to 3 min
    )
    if (!res.ok) return []
    const data = await res.json()
    return data.recommendations || []
  } catch (e) {
    console.warn('[dmpRecommend] failed:', e.message)
    return []
  }
}


/**
 * Fetch real zone data + AI-ranked recommendations for the current brief.
 * Calls GET /api/agent/zones-recommend?session_id=xxx
 * Returns { zones: [...], recommended_ids: [...] }
 * NOTE: kept for fallback; primary flow now uses getSetupEntry().
 */
export async function fetchZonesFromAgent() {
  try {
    const res = await agentFetch(
      `${AGENT_URL}/api/agent/zones-recommend?session_id=${SESSION_ID}`,
      { signal: AbortSignal.timeout(180000) }  // LLM-ranked zones
    )
    if (!res.ok) return null
    return await res.json()
  } catch (e) {
    console.warn('[zonesRecommend] failed:', e.message)
    return null
  }
}

/**
 * Proactive zone recommendation for Step 3 (like getAudienceEntry for Step 1).
 * Calls GET /api/agent/setup-entry?session_id=xxx
 * Returns { skip, text, blocks, meta, suggestions } where blocks contains a
 * workspace_proposal with field="setup" and the full allZones + selectedZoneIds.
 */
export async function getSetupEntry() {
  try {
    const res = await agentFetch(
      `${AGENT_URL}/api/agent/setup-entry?session_id=${SESSION_ID}`,
      { signal: AbortSignal.timeout(180000) }  // LLM call — up to 3 min
    )
    if (!res.ok) return null
    return await res.json()
  } catch (e) {
    console.warn('[setupEntry] failed:', e.message)
    return null
  }
}


/**
 * Upload a creative file (base64 dataUrl) to the AdsPilot VPS.
 * Returns the VPS URL string on success, empty string on failure.
 */
/**
 * Phase 3: fire-and-forget creative analysis (deterministic + VLM) once files
 * have real URLs. Results surface via GET /api/agent/creative-intel.
 * @param {Array<{name: string, url: string}>} files
 */
export async function analyzeCreatives(files) {
  const withUrls = (files || []).filter(f => f.url)
  if (!withUrls.length) return { jobs: [] }
  const res = await agentFetch(`${AGENT_URL}/api/agent/creative-analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: SESSION_ID, files: withUrls }),
    signal: AbortSignal.timeout(10000),
  })
  if (!res.ok) throw new Error(`Không thể tạo tác vụ phân tích creative (HTTP ${res.status})`)
  return await res.json()
}

export async function getCreativeIntel() {
  const res = await agentFetch(
    `${AGENT_URL}/api/agent/creative-intel?session_id=${encodeURIComponent(SESSION_ID)}`,
    { signal: AbortSignal.timeout(10000) },
  )
  if (!res.ok) throw new Error(`Không thể đọc kết quả creative (HTTP ${res.status})`)
  return (await res.json()).files || []
}

export async function overrideCreative(analysisId, reason) {
  const res = await agentFetch(`${AGENT_URL}/api/agent/creative-intel/override`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: SESSION_ID,
      analysis_id: analysisId,
      reason,
      actor: 'campaign_operator',
    }),
    signal: AbortSignal.timeout(10000),
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body.detail || 'Không thể ghi nhận phê duyệt thủ công')
  return body
}

const wait = (ms) => new Promise(resolve => setTimeout(resolve, ms))

const SKIN_FORMAT_IDS = new Set(['zuma-Left', 'zuma-Right', 'znews-Background'])
const inferIntendedFormat = (file) => {
  if (file.intendedFormat) return file.intendedFormat
  if (SKIN_FORMAT_IDS.has(file.formatId)) return 'skin'
  if (file.type?.startsWith('video/')) return 'video'
  return 'banner'
}

function mergeCreativeIntel(files, docs) {
  return files.map(file => {
    const doc = docs.find(item =>
      item.analysis_id === file.analysisId ||
      item.url === file.url ||
      (item.name && item.name === file.name)
    )
    if (!doc) return file
    const deterministic = doc.deterministic || {}
    return {
      ...file,
      analysisId: doc.analysis_id,
      analysisStatus: doc.effective_status || doc.status,
      reviewReasons: doc.review_reasons || [],
      generationAdvisories: doc.generation_advisories || [],
      deterministic,
      vlm: doc.vlm || {},
      vlmError: doc.vlm_error || null,
      vlmProvider: doc.vlm_provider || '',
      vlmModel: doc.vlm_model || '',
      vlmRouteKey: doc.vlm_route_key || '',
      override: doc.override || {},
      width: deterministic.width || file.width,
      height: deterministic.height || file.height,
    }
  })
}

/** Upload, enqueue, and wait for terminal creative verdicts before Setup. */
export async function prepareCreativeFiles(
  files,
  onProgress = () => {},
  { resilientUpload = false } = {},
) {
  let prepared = []
  for (let index = 0; index < (files || []).length; index += 1) {
    const file = files[index]
    let url = file.url || ''
    if (!url && file.dataUrl) {
      onProgress([
        ...prepared,
        { ...file, analysisStatus: 'uploading' },
        ...(files || []).slice(index + 1),
      ])
      try {
        url = await uploadCreativeFile(
          file.dataUrl,
          file.name,
          file.type,
          resilientUpload
            ? {
                timeoutMs: OPENAI_CREATIVE_UPLOAD_TIMEOUT_MS,
                maxAttempts: OPENAI_CREATIVE_UPLOAD_MAX_ATTEMPTS,
                idempotencyKey: creativeUploadIdempotencyKey({
                  conversationId: CURRENT_CONVERSATION_ID,
                  sessionId: SESSION_ID,
                  file,
                  index,
                }),
              }
            : {},
        )
      } catch (error) {
        if (resilientUpload) {
          onProgress([
            ...prepared,
            {
              ...file,
              analysisStatus: 'upload_failed',
              uploadError: error.message,
            },
            ...(files || []).slice(index + 1),
          ])
        }
        throw new Error(`Upload creative thất bại: ${file.name} — ${error.message}`)
      }
    }
    if (!url) throw new Error(`Upload creative thất bại: ${file.name}`)
    prepared.push({
      ...file,
      url,
      intendedFormat: inferIntendedFormat(file),
      analysisStatus: ['uploading', 'upload_failed'].includes(file.analysisStatus)
        ? 'queued'
        : (file.analysisStatus || 'queued'),
      uploadError: null,
    })
    onProgress([...prepared, ...(files || []).slice(index + 1)])
  }

  // Re-entering after analysis/manual review must reuse the persisted server
  // verdicts. Creating a new batch here would erase the visible review state
  // and send the operator back to "Đang chờ phân tích".
  prepared = mergeCreativeIntel(prepared, await getCreativeIntel())
  if (!prepared.length) {
    throw new Error('Chưa có creative để phân tích. Hãy tải hoặc tạo ít nhất một creative rồi thử lại.')
  }
  const allTerminal = prepared.length && prepared.every(file =>
    ['auto_approved', 'needs_review', 'approved_override'].includes(file.analysisStatus)
  )
  const hasRetryableFailure = prepared.some(isRetryableCreativeAnalysisFailure)
  if (allTerminal && !hasRetryableFailure) {
    onProgress(prepared)
    return prepared
  }

  // Establish the authoritative creative input revision before workers start.
  // Their verdicts are accepted only if this exact file set is still current.
  const creativeDraft = {
    files: prepared.map(({ dataUrl, ...file }) => ({
      ...file,
      analysisStatus: 'queued',
    })),
    uploaded: prepared.length > 0,
  }
  const creativeCommit = await AgentAPI.commitWorkspace('creative', creativeDraft, {
    mergeCreativeAdditions: true,
  })
  if (!creativeCommit?.ok) {
    throw new Error(
      creativeCommit?.conflict
        ? 'Creative đã thay đổi ở nơi khác; vui lòng tải lại workspace'
        : 'Không thể khóa phiên bản creative trước khi phân tích'
    )
  }

  const queued = await analyzeCreatives(prepared.map(file => ({
    id: file.id,
    name: file.name,
    type: file.type,
    formatId: file.formatId || '',
    intendedFormat: inferIntendedFormat(file),
    url: file.url,
  })))
  if (!(queued.jobs || []).length) {
    throw new Error(
      queued.note === 'USE_VLM_CREATIVE=false'
        ? 'Tính năng phân tích creative hiện chưa sẵn sàng'
        : 'Không thể tạo tác vụ phân tích cho các creative đã chọn'
    )
  }
  prepared = prepared.map(file => {
    const job = queued.jobs.find(item => item.url === file.url || item.name === file.name)
    return { ...file, analysisId: job?.analysis_id || file.analysisId, analysisStatus: job?.effective_status || job?.status || 'queued' }
  })
  onProgress(prepared)

  const deadline = Date.now() + 45000
  while (Date.now() < deadline) {
    prepared = mergeCreativeIntel(prepared, await getCreativeIntel())
    onProgress(prepared)
    const complete = prepared.every(file =>
      ['auto_approved', 'needs_review', 'approved_override'].includes(file.analysisStatus)
    )
    if (complete) return prepared
    await wait(750)
  }
  throw new Error('Phân tích creative quá thời gian. Tác vụ vẫn được lưu; vui lòng thử xác nhận lại.')
}

export async function uploadCreativeFile(
  dataUrl,
  filename,
  mimeType,
  {
    timeoutMs = 20000,
    maxAttempts = 1,
    idempotencyKey = '',
  } = {},
) {
  if (!dataUrl || !dataUrl.startsWith('data:')) return ''
  // Convert once and reuse the same bytes for a safe idempotent retry.
  const base64 = dataUrl.split(',')[1]
  const bytes = atob(base64)
  const arr = new Uint8Array(bytes.length)
  for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i)
  const blob = new Blob([arr], { type: mimeType })
  const file = new File([blob], filename, { type: mimeType })
  const attempts = Math.max(1, Number(maxAttempts || 1))
  const retryEnabled = attempts > 1 || Boolean(idempotencyKey)
  let lastError = null

  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      const form = new FormData()
      form.append('file', file)

      const res = await fetch(`${BACKEND_URL}/api/creative/upload`, {
        method: 'POST',
        headers: idempotencyKey ? { 'X-Idempotency-Key': idempotencyKey } : {},
        body: form,
        signal: AbortSignal.timeout(timeoutMs),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        lastError = new Error(body.error || `HTTP ${res.status}`)
        lastError.status = res.status
        console.warn('[uploadCreativeFile] upload failed:', res.status, {
          filename,
          attempt,
          attempts,
        })
        if (shouldRetryCreativeUpload({
          attempt,
          maxAttempts: attempts,
          status: res.status,
        })) {
          await wait(750 * attempt)
          continue
        }
        if (retryEnabled) throw lastError
        return ''
      }
      const data = await res.json()
      // The AdsPilot backend returns { url } or { path } — normalise
      const raw = data.url || data.path || ''
      if (!raw) {
        lastError = new Error('Server không trả về URL creative')
        if (shouldRetryCreativeUpload({
          attempt,
          maxAttempts: attempts,
          status: 0,
        })) {
          await wait(750 * attempt)
          continue
        }
        if (retryEnabled) throw lastError
        return ''
      }
      // If it's a relative path, prefix with the backend origin
      if (raw && raw.startsWith('/')) {
        const origin = new URL(BACKEND_URL).origin
        return `${origin}${raw}`
      }
      return raw
    } catch (error) {
      lastError = error
      console.warn('[uploadCreativeFile] error:', error.message, {
        filename,
        attempt,
        attempts,
      })
      if (shouldRetryCreativeUpload({
        attempt,
        maxAttempts: attempts,
        status: Number(error.status || 0),
      })) {
        await wait(750 * attempt)
        continue
      }
      if (retryEnabled) throw error
      return ''
    }
  }
  if (retryEnabled && lastError) throw lastError
  return ''
}

/**
 * Create campaign orders via agent backend (phase=2).
 * Called directly from ConfirmPhase to avoid the approveStep flow
 * which was sending phase=0 and triggering zone-recommend instead.
 * @param {string[]} selectedZoneIds
 * @param {Object}  assignments   { zoneId: fileIndexInt }
 * @param {Object}  fileUrls      { "0": "https://...", "1": "https://..." }
 */
// Idempotency (Phase 0): one key per confirm intent. Kept module-level so a
// user retry of the SAME confirm reuses the key (backend dedupes); reset after
// a successful create so a genuinely new campaign gets a fresh key.
let _orderIdempotencyKey = null

export async function createCampaignOrder(selectedZoneIds, assignments, fileUrls = {}) {
  if (!_orderIdempotencyKey) _orderIdempotencyKey = `${DEMO_NAMESPACE || 'app'}:${crypto.randomUUID()}`
  try {
    // Use the same response adapter as every other chat mutation. Returning
    // raw {text, meta} made ConfirmPhase look for missing {content, metadata},
    // hiding guard reasons and treating successful orders as failures.
    const response = await callAgent({
      session_id: SESSION_ID,
      step: 3,
      message: '',
      formData: {
        setup: {
          phase: 2,
          selectedZoneIds: selectedZoneIds || [],
          assignments: assignments || {},
          fileUrls: fileUrls || {},
          idempotencyKey: _orderIdempotencyKey,
        },
      },
    })
    // Success → next confirm is a new campaign, needs a new key.
    // (Guard-rejection returns tool 'order_guard'; keep the key so a fixed
    //  retry of the same intent still dedupes.)
    if (response?.metadata?.tool === 'order_create') _orderIdempotencyKey = null
    return response
  } catch (e) {
    console.warn('[createCampaignOrder] failed:', e.message)
    return null
  }
}

function safeDemoFallback(response) {
  const content = response?.content?.trim()
  return {
    ...response,
    content: content || 'Em chưa thể trả lời câu hỏi này ngay lúc này. Anh/chị vui lòng thử lại sau ít phút.',
    blocks: [],
    workspace_update: null,
    timestamp: response?.timestamp || new Date().toISOString(),
    metadata: { ...(response?.metadata || {}), tool: 'demo_fallback', model: 'deterministic-cache', fallback_mode: true },
  }
}

function serviceUnavailable(content, step) {
  return {
    id: generateId(), role: 'error', content, blocks: [],
    timestamp: new Date().toISOString(), workspace_update: null,
    metadata: { tool: 'agent_unavailable', model: 'none', step },
  }
}


export const AgentAPI = {
  async getDebugLogs(limit = 500) {
    const sessionId = SESSION_ID
    const res = await agentFetch(
      `${AGENT_URL}/api/agent/logs/${encodeURIComponent(sessionId)}?limit=${Math.max(1, Math.min(1000, Number(limit) || 500))}`,
      { signal: AbortSignal.timeout(15000) },
    )
    if (!res.ok) throw new Error(`Không thể tải backend logs (HTTP ${res.status})`)
    return res.json()
  },


  /**
   * Bootstrap the anonymous device identity. Restoring the previous campaign
   * is opt-in: the product homepage must remain the first screen after every
   * fresh load, while explicit History actions still restore full context.
   */
  async initializeIdentity({ restoreCurrent = true } = {}) {
    await bootstrapIdentity()
    if (!restoreCurrent) {
      return { current_conversation_id: CURRENT_CONVERSATION_ID || null }
    }
    let context = CURRENT_CONVERSATION_ID
      ? await fetchConversation(CURRENT_CONVERSATION_ID)
      : null
    if (!context) context = await createOwnedConversation()
    return context
  },

  async getAuthMe() {
    const response = await agentFetch(`${AGENT_URL}/api/agent/auth/me`, {
      signal: AbortSignal.timeout(5000),
    })
    if (!response.ok) throw await responseError(response, 'Không thể tải thông tin tài khoản.')
    return response.json()
  },

  async registerAccount({ email, password, displayName }) {
    const response = await agentFetch(`${AGENT_URL}/api/agent/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, display_name: displayName }),
      signal: AbortSignal.timeout(15000),
    })
    if (!response.ok) throw await responseError(response, 'Không thể tạo tài khoản.')
    return response.json()
  },

  async loginAccount({ email, password }) {
    const response = await agentFetch(`${AGENT_URL}/api/agent/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
      signal: AbortSignal.timeout(15000),
    })
    if (!response.ok) throw await responseError(response, 'Email hoặc mật khẩu không đúng.')
    return response.json()
  },

  async startZaloAuth({ intent = 'login', returnTo = '/' } = {}) {
    const response = await agentFetch(`${AGENT_URL}/api/agent/auth/zalo/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intent, return_to: returnTo }),
      signal: AbortSignal.timeout(5000),
    })
    if (!response.ok) throw await responseError(response, 'Không thể bắt đầu đăng nhập Zalo.')
    return response.json()
  },

  async logoutAccount() {
    const response = await agentFetch(`${AGENT_URL}/api/agent/auth/logout`, {
      method: 'POST', signal: AbortSignal.timeout(5000),
    })
    if (!response.ok) throw await responseError(response, 'Không thể đăng xuất.')
    return response.json()
  },

  async listAccountSessions() {
    const response = await agentFetch(`${AGENT_URL}/api/agent/auth/sessions`, {
      signal: AbortSignal.timeout(5000),
    })
    if (!response.ok) throw await responseError(response, 'Không thể tải các phiên đăng nhập.')
    const data = await response.json()
    return Array.isArray(data.sessions) ? data.sessions : []
  },

  async revokeAccountSession(accountSessionId) {
    const response = await agentFetch(
      `${AGENT_URL}/api/agent/auth/sessions/${encodeURIComponent(accountSessionId)}`,
      { method: 'DELETE', signal: AbortSignal.timeout(5000) },
    )
    if (!response.ok) throw await responseError(response, 'Không thể thu hồi phiên đăng nhập.')
    return response.json()
  },

  async startZaloChannelLink() {
    const response = await agentFetch(`${AGENT_URL}/api/agent/channel-links/zalo`, {
      method: 'POST', signal: AbortSignal.timeout(5000),
    })
    if (!response.ok) throw await responseError(response, 'Không thể tạo mã liên kết Zalo OA.')
    return response.json()
  },

  async getZaloChannelLink(attemptId) {
    const response = await agentFetch(
      `${AGENT_URL}/api/agent/channel-links/zalo/${encodeURIComponent(attemptId)}`,
      { signal: AbortSignal.timeout(5000) },
    )
    if (!response.ok) throw await responseError(response, 'Không thể kiểm tra liên kết Zalo OA.')
    return response.json()
  },

  async recoverExistingZaloFollower(attemptId) {
    const response = await agentFetch(
      `${AGENT_URL}/api/agent/channel-links/zalo/${encodeURIComponent(attemptId)}/recover-existing-follower`,
      { method: 'POST', signal: AbortSignal.timeout(60000) },
    )
    if (!response.ok) throw await responseError(response, 'Không thể kiểm tra trạng thái quan tâm Zalo OA.')
    return response.json()
  },

  async unlinkZaloChannel() {
    const response = await agentFetch(`${AGENT_URL}/api/agent/channel-links/zalo`, {
      method: 'DELETE', signal: AbortSignal.timeout(5000),
    })
    if (!response.ok) throw await responseError(response, 'Không thể hủy liên kết Zalo OA.')
    return response.json()
  },

  async listConversations(includeArchived = false) {
    try {
      await bootstrapIdentity()
      const response = await agentFetch(
        `${AGENT_URL}/api/agent/conversations?include_archived=${includeArchived ? 'true' : 'false'}`,
        { signal: AbortSignal.timeout(5000) },
      )
      if (!response.ok) return []
      const data = await response.json()
      return Array.isArray(data.conversations) ? data.conversations : []
    } catch (error) {
      console.warn('[listConversations] failed:', error.message)
      return []
    }
  },

  async getCampaignEvaluation(campaignId) {
    await bootstrapIdentity()
    const response = await agentFetch(`${AGENT_URL}/api/agent/evaluation/campaigns/${encodeURIComponent(campaignId)}`, { signal: AbortSignal.timeout(15000) })
    if (!response.ok) throw await responseError(response, 'Không thể tải Live Evaluation.')
    return response.json()
  },

  async updateCampaignEvaluationPolicy(campaignId, updates) {
    const response = await agentFetch(`${AGENT_URL}/api/agent/evaluation/campaigns/${encodeURIComponent(campaignId)}/policy`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(updates), signal: AbortSignal.timeout(15000),
    })
    if (!response.ok) throw await responseError(response, 'Không thể cập nhật evaluation policy.')
    return response.json()
  },

  async runCampaignEvaluation(campaignId, force = true) {
    const response = await agentFetch(`${AGENT_URL}/api/agent/evaluation/campaigns/${encodeURIComponent(campaignId)}/runs`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ force }), signal: AbortSignal.timeout(120000),
    })
    if (!response.ok) throw await responseError(response, 'Không thể chạy evaluation.')
    return response.json()
  },

  async getCampaignScenarios(campaignId) {
    await bootstrapIdentity()
    const response = await agentFetch(`${AGENT_URL}/api/agent/evaluation/campaigns/${encodeURIComponent(campaignId)}/scenarios`, { signal: AbortSignal.timeout(15000) })
    if (!response.ok) throw await responseError(response, 'Không thể tải Scenario Lab.')
    return response.json()
  },

  async previewCampaignScenario(campaignId, scenario) {
    const response = await agentFetch(`${AGENT_URL}/api/agent/evaluation/campaigns/${encodeURIComponent(campaignId)}/scenarios/preview`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(scenario), signal: AbortSignal.timeout(30000),
    })
    if (!response.ok) throw await responseError(response, 'Không thể preview scenario.')
    return response.json()
  },

  async applyCampaignScenario(campaignId, scenario) {
    const response = await agentFetch(`${AGENT_URL}/api/agent/evaluation/campaigns/${encodeURIComponent(campaignId)}/scenarios/apply`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(scenario), signal: AbortSignal.timeout(180000),
    })
    if (!response.ok) throw await responseError(response, 'Không thể apply scenario.')
    return response.json()
  },

  async actOnEvaluationIncident(campaignId, incidentId, action, note = '') {
    const response = await agentFetch(`${AGENT_URL}/api/agent/evaluation/campaigns/${encodeURIComponent(campaignId)}/incidents/${encodeURIComponent(incidentId)}/actions`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action, note }), signal: AbortSignal.timeout(120000),
    })
    if (!response.ok) throw await responseError(response, 'Không thể cập nhật incident.')
    return response.json()
  },

  async listCampaigns(includeArchived = true) {
    await bootstrapIdentity()
    const response = await agentFetch(
      `${AGENT_URL}/api/agent/campaigns?include_archived=${includeArchived ? 'true' : 'false'}&limit=100`,
      { signal: AbortSignal.timeout(10000) },
    )
    if (!response.ok) throw await responseError(response, 'Không thể tải danh sách campaign.')
    const data = await response.json()
    return Array.isArray(data.campaigns) ? data.campaigns : []
  },

  async getCampaign(campaignId) {
    await bootstrapIdentity()
    const response = await agentFetch(
      `${AGENT_URL}/api/agent/campaigns/${encodeURIComponent(campaignId)}`,
      { signal: AbortSignal.timeout(10000) },
    )
    if (!response.ok) throw await responseError(response, 'Không thể tải campaign.')
    return (await response.json()).campaign
  },

  async getEvaluationIncident(campaignId, incidentId) {
    const response = await agentFetch(`${AGENT_URL}/api/agent/evaluation/campaigns/${encodeURIComponent(campaignId)}/incidents/${encodeURIComponent(incidentId)}`, { signal: AbortSignal.timeout(15000) })
    if (!response.ok) throw await responseError(response, 'Không tải được lịch sử điều tra.')
    return response.json()
  },

  async askEvaluationIncident(campaignId, incidentId, question) {
    const response = await agentFetch(`${AGENT_URL}/api/agent/evaluation/campaigns/${encodeURIComponent(campaignId)}/incidents/${encodeURIComponent(incidentId)}/questions`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(question), signal: AbortSignal.timeout(60000),
    })
    if (!response.ok) throw await responseError(response, 'Chưa trả lời được câu hỏi incident.')
    return response.json()
  },

  async getIncidentQuestions(campaignId, incidentId) {
    const response = await agentFetch(`${AGENT_URL}/api/agent/evaluation/campaigns/${encodeURIComponent(campaignId)}/incidents/${encodeURIComponent(incidentId)}/questions`, { signal: AbortSignal.timeout(15000) })
    if (!response.ok) throw await responseError(response, 'Chưa tải được lịch sử hỏi đáp.')
    return response.json()
  },

  async listConversationModels() {
    const response = await agentFetch(`${AGENT_URL}/api/agent/conversation-models`, {
      signal: AbortSignal.timeout(5000),
    })
    if (!response.ok) throw await responseError(response, 'Unable to load model catalog.')
    return response.json()
  },

  async resumeConversation(conversationId) {
    const context = await fetchConversation(conversationId)
    if (!context) throw new Error('Không tìm thấy chiến dịch hoặc thiết bị này không có quyền truy cập.')
    return context
  },

  async claimConversation(conversationId) {
    const response = await agentFetch(
      `${AGENT_URL}/api/agent/conversations/${encodeURIComponent(conversationId)}/claim`,
      { method: 'POST', signal: AbortSignal.timeout(10000) },
    )
    if (!response.ok) throw await responseError(response, 'Không thể lưu campaign vào tài khoản.')
    return response.json()
  },

  async createConversation(options = {}) {
    await bootstrapIdentity()
    return createOwnedConversation(options)
  },

  async archiveConversation(conversationId) {
    const response = await agentFetch(
      `${AGENT_URL}/api/agent/conversations/${encodeURIComponent(conversationId)}/archive`,
      { method: 'POST', signal: AbortSignal.timeout(5000) },
    )
    return response.ok
  },

  async deleteConversation(conversationId) {
    const response = await agentFetch(
      `${AGENT_URL}/api/agent/conversations/${encodeURIComponent(conversationId)}`,
      { method: 'DELETE', signal: AbortSignal.timeout(15000) },
    )
    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      const detail = data.detail
      throw new Error(detail?.message || detail || 'Không thể xóa cuộc trò chuyện.')
    }
    clearConversationContext(conversationId)
    return data
  },

  async deleteAllConversations() {
    const response = await agentFetch(`${AGENT_URL}/api/agent/conversations`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ confirmation: 'DELETE_ALL' }),
      signal: AbortSignal.timeout(30000),
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      const detail = data.detail
      throw new Error(detail?.message || detail || 'Không thể xóa toàn bộ lịch sử.')
    }
    clearConversationContext()
    return data
  },

  currentConversationId() {
    return CURRENT_CONVERSATION_ID
  },

  async submitFeedback(payload) {
    const response = await agentFetch(`${AGENT_URL}/api/agent/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...payload,
        session_id: payload.session_id || SESSION_ID,
        workspace_revision: payload.workspace_revision ?? WORKSPACE_REVISION,
      }),
      signal: AbortSignal.timeout(10000),
    })
    if (!response.ok) {
      throw await responseError(response, 'Không thể lưu phản hồi. Vui lòng thử lại.')
    }
    return withRequestId(await response.json(), response)
  },

  async boot(experienceMode = 'guided') {
    const real = await callAgent({
      session_id: SESSION_ID,
      step: -1,
      message: '',
      experience_mode: experienceMode === 'autopilot' ? 'autopilot' : 'guided',
    })
    return real ?? safeDemoFallback(AGENT_SCENARIOS.boot(experienceMode))
  },

  async chat(text, currentStep, formState, stepStatuses, workspaceEvents) {
    // Build compact workspace — strip dataUrls from creative files to minimize payload
    const compactWorkspace = {
      brief: formState?.brief || {},
      segment: {
        attrs: (formState?.segment?.attrs || []).map(a => ({
          name: a.name || a.fullLabel || '',
          type: a.type || '',
          category: a.category || '',
          est_size: a.est_size || 0,
        })),
        size: formState?.segment?.size || 0,
      },
      creative: {
        files: (formState?.creative?.files || []).map(f => ({
          name: f.name, type: f.type, size: f.size,
        })),
      },
      setup: {
        selectedZoneIds: formState?.setup?.selectedZoneIds || [],
        phase: formState?.setup?.phase || 'zones',
        assignments: formState?.setup?.assignments || {},
      },
    }

    // Build confirmed_steps from stepStatuses
    const confirmedSteps = (stepStatuses || []).reduce((acc, s, i) => {
      if (s === 'done') acc.push(i)
      return acc
    }, [])

    const real = await callAgent({
      session_id: SESSION_ID,
      step: currentStep,
      message: text,
      workspace: compactWorkspace,
      workspace_revision: WORKSPACE_REVISION,
      confirmed_steps: confirmedSteps,
      workspace_events: workspaceEvents || [],
    })
    if (real?.workspace_update || real?.metadata?.tool === 'targeting_autopick') {
      await this.getWorkspace()
    }
    return real ?? safeDemoFallback(AGENT_SCENARIOS.chat(text, currentStep, formState))
  },

  async approveBrief(briefData) {
    const real = await callAgent({
      session_id: SESSION_ID,
      step: 0,
      message: '',
      formData: { brief: briefData },
    })
    if (!real) return serviceUnavailable('⚠️ Agent service không khả dụng; brief chưa được lưu. Hãy thử lại khi kết nối phục hồi.', 0)
    await this.getWorkspace()
    return real
  },

  async approveCreative(creativeData) {
    // Creative is now step 2 (Brief=0, Audience=1, Creative=2)
    const compactCreative = {
      ...creativeData,
      files: (creativeData?.files || []).map(file => ({
        id: file.id, name: file.name, type: file.type, size: file.size,
        width: file.width, height: file.height, url: file.url,
        analysisId: file.analysisId, analysisStatus: file.analysisStatus,
        reviewReasons: file.reviewReasons, deterministic: file.deterministic,
        vlm: file.vlm, override: file.override, formatId: file.formatId,
        intendedFormat: file.intendedFormat,
        source: file.source, derivedFromFileId: file.derivedFromFileId,
        repairMethod: file.repairMethod,
      })),
    }
    const real = await callAgent({
      session_id: SESSION_ID,
      step: 2,
      message: '',
      formData: { creative: compactCreative },
    })
    if (!real) throw new Error('Agent không lưu được creative đã phân tích')
    await this.getWorkspace()
    return real
  },

  async approveAudience(segmentData) {
    // Audience is now step 1 (Brief=0, Audience=1)
    const real = await callAgent({
      session_id: SESSION_ID,
      step: 1,
      message: '',
      formData: { segment: segmentData },
    })
    if (!real) return serviceUnavailable('⚠️ Agent service không khả dụng; audience chưa được lưu. Hãy thử lại khi kết nối phục hồi.', 1)
    await this.getWorkspace()
    return real
  },

  async approveSetup(setupData) {
    const real = await callAgent({
      session_id: SESSION_ID,
      step: 3,
      message: '',
      formData: { setup: setupData },
    })
    if (!real) return serviceUnavailable('⚠️ Agent service không khả dụng; setup chưa được lưu. Hãy thử lại khi kết nối phục hồi.', 3)
    return real
  },

  async getResult() {
    const real = await callAgent({
      session_id: SESSION_ID,
      step: 4,
      message: '',
      formData: {},
    })
    if (!real) return serviceUnavailable('⚠️ Agent service không khả dụng; không thể xác minh kết quả campaign.', 4)
    return real
  },

  /** Probe health — called on app mount to decide badge status */
  async isOnline() {
    return probeAgent()
  },

  /** Delete the current agent/session artifacts. Created campaign orders remain. */
  async deleteCurrentSession() {
    try {
      const res = await agentFetch(
        `${AGENT_URL}/api/agent/sessions/${encodeURIComponent(SESSION_ID)}`,
        { method: 'DELETE', signal: AbortSignal.timeout(10000) },
      )
      return res.ok
    } catch (e) {
      console.warn('[deleteCurrentSession] failed:', e.message)
      return false
    }
  },

  /**
   * Legacy non-persistent reset used only by old demos/tests. New product flows
   * should call createConversation() so the previous campaign remains resumable.
   */
  newSession() {
    SESSION_ID = _genSessionId()
    CURRENT_CONVERSATION_ID = ''
    WORKSPACE_REVISION = null
    _workspaceMutationKeys.clear()
    storageSet('session-id', '')
    storageSet('conversation-id', '')
    if (typeof window !== 'undefined') window.__AGENT_SESSION_ID__ = SESSION_ID
    _agentReachable = null   // re-probe health on next call
    return SESSION_ID
  },

  /** @deprecated use newSession() + boot() */
  resetSession() {
    return this.newSession()
  },

  /**
   * Proactive audience recommendation when user enters step 1.
   * Returns { skip, text, blocks, meta, workspace_proposal } or { skip: true }.
   * Called automatically by App.jsx when currentStep becomes 1 with brief done.
   * @param {object} brief - Current formState.brief (used as fallback if backend pending_proposal not committed)
   */
  async getAudienceEntry(brief = null) {
    try {
      let url = `${AGENT_URL}/api/agent/audience-entry?session_id=${SESSION_ID}`
      if (brief && brief.brand) {
        url += `&brief_hint=${encodeURIComponent(JSON.stringify(brief))}`
      }
      const res = await agentFetch(url, { signal: AbortSignal.timeout(180000) })  // LLM call — up to 3 min
      if (!res.ok) return null
      return await res.json()
    } catch (e) {
      console.warn('[getAudienceEntry] failed:', e.message)
      return null
    }
  },

  /** Server-owned unique reach; the browser never computes segment unions. */
  async getAudienceReach(attrs = []) {
    const selectedSegmentIds = attrs.map(item =>
      item.segmentId || item.code || item._uid || item._id || item.fullLabel || item.name
    ).filter(Boolean)
    try {
      const res = await agentFetch(`${AGENT_URL}/api/agent/audience/reach`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: SESSION_ID,
          selected_segment_ids: selectedSegmentIds,
        }),
        signal: AbortSignal.timeout(15000),
      })
      if (!res.ok) return null
      return await res.json()
    } catch (e) {
      console.warn('[getAudienceReach] failed:', e.message)
      return null
    }
  },

  /**
   * Commit a workspace field directly to backend session (MongoDB).
   * Called when user clicks 'Đồng ý' proposal button or footer 'Đồng ý & Tiếp tục',
   * bypassing the chat confirm round-trip. Also clears any pending_proposal for the field.
   * @param {string} field - e.g. 'brief', 'segment'
   * @param {any} value - The value to persist
   */
  async commitWorkspace(field, value, options = {}) {
    try {
      if (WORKSPACE_REVISION == null) await this.getWorkspace()
      const idempotencyKey = _mutationKey(field, value)
      const res = await agentFetch(`${AGENT_URL}/api/agent/commit-workspace`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: SESSION_ID,
          field,
          value,
          base_revision: WORKSPACE_REVISION,
          idempotency_key: idempotencyKey,
          actor: 'campaign_operator',
          reason: 'guided_workspace_confirmation',
        }),
        signal: AbortSignal.timeout(5000),
      })
      const data = await res.json().catch(() => ({}))
      if (res.status === 409) {
        const conflict = data?.detail || data
        WORKSPACE_REVISION = conflict?.actual_revision ?? WORKSPACE_REVISION
        if (options.mergeCreativeAdditions && field === 'creative' && conflict?.workspace) {
          const canonical = conflict.workspace?.artifacts?.creative?.value || {}
          const canonicalFiles = Array.isArray(canonical.files) ? canonical.files : []
          const requestedFiles = Array.isArray(value?.files) ? value.files : []
          const identity = file => String(file?.id || file?.url || file?.name || '').trim()
          const mergedFiles = [...canonicalFiles]
          const existing = new Set(canonicalFiles.map(identity).filter(Boolean))
          requestedFiles.forEach(file => {
            const key = identity(file)
            if (!key || existing.has(key)) return
            existing.add(key)
            mergedFiles.push(file)
          })
          const mergedValue = { ...canonical, ...value, files: mergedFiles, uploaded: mergedFiles.length > 0 }
          const retry = await agentFetch(`${AGENT_URL}/api/agent/commit-workspace`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              session_id: SESSION_ID,
              field,
              value: mergedValue,
              base_revision: conflict.actual_revision,
              idempotency_key: _mutationKey(field, mergedValue),
              actor: 'campaign_operator',
              reason: 'guided_workspace_creative_additive_rebase',
            }),
            signal: AbortSignal.timeout(5000),
          })
          const retryData = await retry.json().catch(() => ({}))
          if (retry.ok) {
            WORKSPACE_REVISION = retryData.workspace_revision ?? WORKSPACE_REVISION
            await this.getWorkspace()
            return { ...retryData, rebased: true }
          }
          const retryConflict = retryData?.detail || retryData
          WORKSPACE_REVISION = retryConflict?.actual_revision ?? WORKSPACE_REVISION
          if (typeof window !== 'undefined') {
            window.dispatchEvent(new CustomEvent('agent:workspace_conflict', { detail: retryConflict }))
          }
          return { ok: false, conflict: true, ...retryConflict }
        }
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('agent:workspace_conflict', { detail: conflict }))
        }
        return { ok: false, conflict: true, ...conflict }
      }
      if (!res.ok) return { ok: false, status: res.status, ...data }
      WORKSPACE_REVISION = data.workspace_revision ?? WORKSPACE_REVISION
      await this.getWorkspace()
      return data
    } catch (e) {
      console.warn('[commitWorkspace] failed:', e.message)
      return { ok: false }
    }
  },

  async confirmWorkflowStep(step) {
    const response = await agentFetch(
      `${AGENT_URL}/api/agent/workflow/steps/${encodeURIComponent(step)}/confirm`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: SESSION_ID }),
        signal: AbortSignal.timeout(5000),
      },
    )
    if (!response.ok) {
      throw await responseError(response, 'Không thể lưu xác nhận bước workflow.')
    }
    return response.json()
  },

  async getWorkspace() {
    try {
      const res = await agentFetch(
        `${AGENT_URL}/api/agent/workspace?session_id=${encodeURIComponent(SESSION_ID)}`,
        { signal: AbortSignal.timeout(5000) },
      )
      if (!res.ok) return null
      const workspace = await res.json()
      WORKSPACE_REVISION = workspace.revision
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('agent:canonical_workspace', {
          detail: workspace,
        }))
      }
      return workspace
    } catch (e) {
      console.warn('[getWorkspace] failed:', e.message)
      return null
    }
  },

  async getPendingWorkspaceProposals() {
    try {
      const res = await agentFetch(
        `${AGENT_URL}/api/agent/workspace/proposals?session_id=${encodeURIComponent(SESSION_ID)}`,
        { signal: AbortSignal.timeout(5000) },
      )
      if (!res.ok) return []
      const data = await res.json()
      return Array.isArray(data?.proposals) ? data.proposals : []
    } catch (e) {
      console.warn('[getPendingWorkspaceProposals] failed:', e.message)
      return []
    }
  },

  async setWorkspacePreferences(experienceMode, approvalPolicy = null, creativeSource = null) {
    try {
      if (WORKSPACE_REVISION == null) await this.getWorkspace()
      const preferenceMutationId = (
        globalThis.crypto?.randomUUID?.()
        || `${Date.now()}-${Math.random().toString(16).slice(2)}`
      )
      const res = await agentFetch(`${AGENT_URL}/api/agent/workspace/preferences`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: SESSION_ID,
          experience_mode: experienceMode,
          approval_policy: approvalPolicy,
          creative_source: creativeSource,
          base_revision: WORKSPACE_REVISION,
          actor: 'campaign_operator',
          // Each click is a distinct operator mutation. Reusing a value-derived
          // key prevents A -> B -> A preference changes from applying the last A.
          idempotency_key: `experience:${SESSION_ID}:${preferenceMutationId}`,
        }),
        signal: AbortSignal.timeout(5000),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) return { ok: false, status: res.status, ...(data.detail || data) }
      WORKSPACE_REVISION = data.workspace_revision ?? WORKSPACE_REVISION
      await this.getWorkspace()
      return data
    } catch (e) {
      console.warn('[setWorkspacePreferences] failed:', e.message)
      return { ok: false, detail: e.message }
    }
  },

  async startAutopilot(approvalPolicy = 'critical_only', creativeSource, startKey = '', creativeInput = {}) {
    try {
      const res = await agentFetch(`${AGENT_URL}/api/agent/autopilot/runs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: SESSION_ID,
          approval_policy: approvalPolicy,
          creative_source: creativeSource,
          creative_direction: creativeInput.direction || '',
          creative_asset_ids: creativeInput.assetIds || [],
          actor: 'campaign_operator',
          idempotency_key: `autopilot-start:${SESSION_ID}:${creativeSource}:${startKey || 'initial'}`,
        }),
        signal: AbortSignal.timeout(10000),
      })
      const data = await res.json().catch(() => ({}))
      return res.ok ? withRequestId(data, res) : { ok: false, status: res.status, ...(data.detail || data) }
    } catch (e) {
      return { ok: false, detail: e.message }
    }
  },

  async getAutopilotRun(runId) {
    try {
      const res = await agentFetch(`${AGENT_URL}/api/agent/autopilot/runs/${encodeURIComponent(runId)}`, {
        signal: AbortSignal.timeout(5000),
      })
      return res.ok ? withRequestId(await res.json(), res) : null
    } catch (e) {
      console.warn('[getAutopilotRun] failed:', e.message)
      return null
    }
  },

  async autopilotAction(runId, action) {
    try {
      const res = await agentFetch(`${AGENT_URL}/api/agent/autopilot/runs/${encodeURIComponent(runId)}/${action}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ actor: 'campaign_operator' }),
        signal: AbortSignal.timeout(5000),
      })
      const data = await res.json().catch(() => ({}))
      return res.ok ? withRequestId(data, res) : { ok: false, status: res.status, ...(data.detail || data) }
    } catch (e) {
      return { ok: false, detail: e.message }
    }
  },

  async reviewAutopilotTask(runId, taskId, approved, reason = '') {
    try {
      const res = await agentFetch(`${AGENT_URL}/api/agent/autopilot/runs/${encodeURIComponent(runId)}/tasks/${encodeURIComponent(taskId)}/review`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approved, actor: 'campaign_operator', reason }),
        signal: AbortSignal.timeout(10000),
      })
      const data = await res.json().catch(() => ({}))
      return res.ok ? withRequestId(data, res) : { ok: false, status: res.status, ...(data.detail || data) }
    } catch (e) {
      return { ok: false, detail: e.message }
    }
  },

  async rerunAutopilotAudience(runId, taskId, reason = '') {
    try {
      const res = await agentFetch(`${AGENT_URL}/api/agent/autopilot/runs/${encodeURIComponent(runId)}/tasks/${encodeURIComponent(taskId)}/rerun`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          actor: 'campaign_operator',
          reason: reason || 'Operator requested a new audience recommendation',
        }),
        signal: AbortSignal.timeout(10000),
      })
      const data = await res.json().catch(() => ({}))
      return res.ok ? withRequestId(data, res) : { ok: false, status: res.status, ...(data.detail || data) }
    } catch (e) {
      return { ok: false, detail: e.message }
    }
  },

  async selectAutopilotStrategy(runId, optionId, reason = '') {
    try {
      const res = await agentFetch(`${AGENT_URL}/api/agent/autopilot/runs/${encodeURIComponent(runId)}/strategy`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ option_id: optionId, actor: 'campaign_operator', reason }),
        signal: AbortSignal.timeout(10000),
      })
      const data = await res.json().catch(() => ({}))
      return res.ok ? withRequestId(data, res) : { ok: false, status: res.status, ...(data.detail || data) }
    } catch (e) {
      return { ok: false, detail: e.message }
    }
  },

  async selectAutopilotPlacements(runId, zoneIds, reason = '') {
    try {
      const res = await agentFetch(`${AGENT_URL}/api/agent/autopilot/runs/${encodeURIComponent(runId)}/placement-intent`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ zone_ids: zoneIds, actor: 'campaign_operator', reason }),
        signal: AbortSignal.timeout(10000),
      })
      const data = await res.json().catch(() => ({}))
      return res.ok ? withRequestId(data, res) : { ok: false, status: res.status, ...(data.detail || data) }
    } catch (e) {
      return { ok: false, detail: e.message }
    }
  },

  async generateAutopilotCreativeRecovery(runId, formatIds = []) {
    try {
      const res = await agentFetch(
        `${AGENT_URL}/api/agent/autopilot/runs/${encodeURIComponent(runId)}/creative-recovery/generate`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            format_ids: formatIds,
            actor: 'campaign_operator',
            reason: 'Operator requested missing-format creative recovery',
          }),
          signal: AbortSignal.timeout(240000),
        },
      )
      const data = await res.json().catch(() => ({}))
      return res.ok
        ? withRequestId(data, res)
        : { ok: false, status: res.status, ...(data.detail || data) }
    } catch (e) {
      return { ok: false, detail: e.message }
    }
  },

  async chooseAutopilotCreativeAnalysis(runId, mode) {
    try {
      const res = await agentFetch(
        `${AGENT_URL}/api/agent/autopilot/runs/${encodeURIComponent(runId)}/creative-analysis`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            mode,
            actor: 'campaign_operator',
            reason: mode === 'skip'
              ? 'Operator explicitly skipped Creative Intelligence analysis'
              : 'Operator started Creative Intelligence analysis',
          }),
          signal: AbortSignal.timeout(10000),
        },
      )
      const data = await res.json().catch(() => ({}))
      return res.ok
        ? withRequestId(data, res)
        : { ok: false, status: res.status, ...(data.detail || data) }
    } catch (e) {
      return { ok: false, detail: e.message }
    }
  },

  subscribeAutopilot(runId, onEvent) {
    if (typeof EventSource === 'undefined') return () => {}
    const source = new EventSource(`${AGENT_URL}/api/agent/autopilot/runs/${encodeURIComponent(runId)}/events`)
    const handler = () => onEvent?.()
    ;['run_created', 'task_started', 'task_completed', 'task_waiting_review', 'task_approved', 'task_rejected', 'task_retry_scheduled', 'task_failed', 'strategy_selected', 'placement_selection_updated', 'creative_recovery_generated', 'creative_analysis_selected', 'run_milestone', 'run_paused', 'run_resumed', 'run_cancelled'].forEach(type => source.addEventListener(type, handler))
    source.onerror = () => source.close()
    return () => source.close()
  },

  async approveWorkspaceProposal(proposalId) {
    try {
      const res = await agentFetch(
        `${AGENT_URL}/api/agent/workspace/proposals/${encodeURIComponent(proposalId)}/approve`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ actor: 'campaign_operator' }),
          signal: AbortSignal.timeout(5000),
        },
      )
      const data = await res.json().catch(() => ({}))
      if (res.status === 409) {
        const conflict = data?.detail || data
        WORKSPACE_REVISION = conflict?.actual_revision ?? WORKSPACE_REVISION
        window.dispatchEvent(new CustomEvent('agent:workspace_conflict', { detail: conflict }))
        return { ok: false, conflict: true, ...conflict }
      }
      if (!res.ok) return { ok: false, status: res.status, ...data }
      WORKSPACE_REVISION = data.workspace_revision ?? WORKSPACE_REVISION
      await this.getWorkspace()
      return data
    } catch (e) {
      console.warn('[approveWorkspaceProposal] failed:', e.message)
      return { ok: false }
    }
  },

  async rejectWorkspaceProposal(proposalId, reason = 'user_rejected') {
    if (!proposalId) return { ok: true }
    try {
      const res = await agentFetch(
        `${AGENT_URL}/api/agent/workspace/proposals/${encodeURIComponent(proposalId)}/reject`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ actor: 'campaign_operator', reason }),
          signal: AbortSignal.timeout(5000),
        },
      )
      return res.ok ? await res.json() : { ok: false, status: res.status }
    } catch (e) {
      console.warn('[rejectWorkspaceProposal] failed:', e.message)
      return { ok: false }
    }
  },

  async getRecomputePlan() {
    try {
      const res = await agentFetch(
        `${AGENT_URL}/api/agent/workspace/recompute-plan?session_id=${encodeURIComponent(SESSION_ID)}`,
        { signal: AbortSignal.timeout(5000) },
      )
      return res.ok ? await res.json() : null
    } catch (e) {
      console.warn('[getRecomputePlan] failed:', e.message)
      return null
    }
  },

  async getTaskContext(artifact) {
    try {
      const res = await agentFetch(
        `${AGENT_URL}/api/agent/workspace/task-context/${encodeURIComponent(artifact)}?session_id=${encodeURIComponent(SESSION_ID)}`,
        { signal: AbortSignal.timeout(5000) },
      )
      return res.ok ? await res.json() : null
    } catch (e) {
      console.warn('[getTaskContext] failed:', e.message)
      return null
    }
  },

  async commitArtifactResult({ artifact, value, taskId, inputRevisions, baseArtifactRevision, reason = '' }) {
    try {
      const res = await agentFetch(`${AGENT_URL}/api/agent/workspace/artifact-results`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: SESSION_ID,
          artifact,
          value,
          task_id: taskId,
          input_revisions: inputRevisions,
          base_artifact_revision: baseArtifactRevision,
          actor: 'campaign_worker',
          reason,
        }),
        signal: AbortSignal.timeout(10000),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) return { ok: false, status: res.status, ...(data.detail || data) }
      WORKSPACE_REVISION = data.workspace_revision ?? WORKSPACE_REVISION
      await this.getWorkspace()
      return data
    } catch (e) {
      console.warn('[commitArtifactResult] failed:', e.message)
      return { ok: false }
    }
  },

  /**
   * Report entry: trigger background report generation.
   * Called when user enters step 5 (Report).
   */
  async reportEntry() {
    try {
      const res = await agentFetch(
        `${AGENT_URL}/api/agent/report-entry?session_id=${SESSION_ID}`,
        { signal: AbortSignal.timeout(180000) }  // triggers background report gen
      )
      if (!res.ok) return serviceUnavailable('⚠️ Agent service không khả dụng; báo cáo chưa được khởi tạo.', 5)
      return await res.json()
    } catch (e) {
      console.warn('[reportEntry] failed:', e.message)
      return serviceUnavailable('⚠️ Agent service không khả dụng; báo cáo chưa được khởi tạo.', 5)
    }
  },

  /**
   * Poll report generation status.
   * Returns { campaignId, total, ready, errors, types: { daily_ops: 'ready', ... } }
   */
  async getReportStatus(campaignId) {
    try {
      const res = await fetch(
        `${BACKEND_URL}/api/reports/status/${campaignId}`,
        { signal: AbortSignal.timeout(5000) }
      )
      if (!res.ok) return null
      return await res.json()
    } catch (e) {
      console.warn('[getReportStatus] failed:', e.message)
      return null
    }
  },

  /**
   * Fetch all pre-generated analyses for a campaign.
   * Returns array of { campaignId, reportType, status, overall, questions: [...] }
   */
  async getReportAnalyses(campaignId) {
    try {
      const res = await fetch(
        `${BACKEND_URL}/api/reports/analysis/${campaignId}`,
        { signal: AbortSignal.timeout(10000) }
      )
      if (!res.ok) return []
      return await res.json()
    } catch (e) {
      console.warn('[getReportAnalyses] failed:', e.message)
      return []
    }
  },

  /**
   * Fetch raw analytics records for a campaign (for charts).
   * Returns array of { campaignId, placementId, date, impressions, clicks, ... }
   */
  async getReportData(campaignId) {
    try {
      const res = await fetch(
        `${BACKEND_URL}/api/reports/data/${campaignId}`,
        { signal: AbortSignal.timeout(10000) }
      )
      if (!res.ok) return []
      return await res.json()
    } catch (e) {
      console.warn('[getReportData] failed:', e.message)
      return []
    }
  },

  /**
   * Generate an ad image using direct OpenAI gpt-image-2.
   * @param {Object} briefObj   - formState.brief
   * @param {string} formatId   - one of the AD_FORMATS ids
   * @returns {Promise<{ok, imageB64, formatId, width, height, remaining} | {ok: false, error}>}
   */
  async generateAdImage(briefObj, formatId, customPrompt = '', options = {}) {
    try {
      const res = await agentFetch(`${AGENT_URL}/api/agent/generate-image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: SESSION_ID,
          brief: briefObj || {},
          format_id: formatId,
          custom_prompt: customPrompt || '',
          asset_ids: options.assetIds || [],
          prompt_spec: options.promptSpec || null,
          quality: options.quality || 'medium',
          campaign_flow: options.campaignFlow || '',
          audience_context: options.audienceContext || {},
          idempotency_key: options.idempotencyKey || `guided:${SESSION_ID}:${globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`}`,
        }),
        signal: AbortSignal.timeout(180000),  // AI image gen — up to 3 min
      })
      if (!res.ok) return { ok: false, error: `HTTP ${res.status}` }
      return await res.json()
    } catch (e) {
      console.warn('[generateAdImage] failed:', e.message)
      return { ok: false, error: e.message }
    }
  },

  /**
   * Get remaining image generation quota for the current session.
   * Returns the durable per-user/per-anonymous daily quota.
   */
  async getImageGenStatus() {
    try {
      const res = await agentFetch(
        `${AGENT_URL}/api/agent/image-gen-status?session_id=${SESSION_ID}`,
        { signal: AbortSignal.timeout(5000) }
      )
      if (!res.ok) return { remaining: 20, max: 20 }
      return await res.json()
    } catch {
      return { remaining: 20, max: 20 }
    }
  },

  async listGeneratedImages() {
    try {
      const res = await agentFetch(
        `${AGENT_URL}/api/agent/generated-images?session_id=${SESSION_ID}`,
        { signal: AbortSignal.timeout(10000) }
      )
      if (!res.ok) return []
      const data = await res.json()
      return data.jobs || []
    } catch {
      return []
    }
  },

  async finalizeGeneratedImage(jobId, dataUrl) {
    const res = await agentFetch(`${AGENT_URL}/api/agent/generated-images/finalize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: SESSION_ID, job_id: jobId, data_url: dataUrl }),
      signal: AbortSignal.timeout(60000),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`)
    return data.job
  },

  async listCreativeAssets() {
    const res = await agentFetch(`${AGENT_URL}/api/agent/creative/assets?session_id=${SESSION_ID}`, {
      signal: AbortSignal.timeout(10000),
    })
    if (!res.ok) return []
    const data = await res.json()
    return data.assets || []
  },

  async createCreativeAsset({ name, kind, useInstruction, required, dataUrl }) {
    const res = await agentFetch(`${AGENT_URL}/api/agent/creative/assets`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: SESSION_ID, name, kind,
        use_instruction: useInstruction || '', required: Boolean(required),
        data_url: dataUrl,
      }),
      signal: AbortSignal.timeout(45000),
    })
    if (!res.ok) throw await responseError(res, 'Không thể lưu reference asset.')
    return res.json()
  },

  async deleteCreativeAsset(assetId) {
    const res = await agentFetch(
      `${AGENT_URL}/api/agent/creative/assets/${encodeURIComponent(assetId)}?session_id=${SESSION_ID}`,
      { method: 'DELETE', signal: AbortSignal.timeout(10000) },
    )
    return res.ok
  },

  async composeCreativePrompt({ brief, formatId, assetIds, direction }) {
    const res = await agentFetch(`${AGENT_URL}/api/agent/creative/prompt-spec`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: SESSION_ID, brief: brief || {}, format_id: formatId,
        asset_ids: assetIds || [], direction: direction || '',
      }),
      signal: AbortSignal.timeout(90000),
    })
    if (!res.ok) throw await responseError(res, 'Không thể soạn prompt creative.')
    return res.json()
  },

  /**
   * Capture a full-page screenshot of a live test-site URL via Playwright.
   * Only works for whitelisted NP-6 staging publisher domains.
   *
   * @param {string}   siteUrl  - e.g. "https://znews-stg.pawgrammers.io.vn"
   * @param {string[]} zoneIds  - DOM element IDs to capture (from selectedZoneIds).
   *                             These match the `testSiteZone` / `id` field in the DB.
   *                             If empty, all known zones for the site are attempted.
   */
  async captureAdScreenshot(siteUrl, zoneIds = []) {
    try {
      const params = new URLSearchParams({
        url: siteUrl,
        session_id: SESSION_ID,
      })
      if (zoneIds && zoneIds.length > 0) {
        params.set('zone_ids', zoneIds.join(','))
      }
      const res = await agentFetch(
        `${AGENT_URL}/api/agent/screenshot?${params.toString()}`,
        { signal: AbortSignal.timeout(60000) }
      )
      if (!res.ok) return { ok: false, error: `HTTP ${res.status}` }
      return await res.json()
    } catch (e) {
      console.warn('[captureAdScreenshot] failed:', e.message)
      return { ok: false, error: e.message }
    }
  },
}

export { generateMockCampaigns }
