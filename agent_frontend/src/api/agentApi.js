import { fmt, generateId } from '@/lib/utils'
import log from '@/lib/logger'

// ─── Real Agent API client ────────────────────────────────────────────────────
const AGENT_URL = import.meta.env.VITE_AGENT_URL || 'http://localhost:8000'
// AdsPilot backend (for /api/creative/upload)
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:3000'

// Phase 0 auth: X-API-Key sent on every agent call when VITE_AGENT_API_KEY is
// set (must match AGENT_API_KEY in agent/.env — middleware no-ops when empty).
const AGENT_API_KEY = import.meta.env.VITE_AGENT_API_KEY || ''
const agentFetch = (url, opts = {}) =>
  fetch(url, {
    ...opts,
    headers: {
      ...(opts.headers || {}),
      ...(AGENT_API_KEY ? { 'X-API-Key': AGENT_API_KEY } : {}),
    },
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
      'background:#16a34a;color:#fff;font-size:13px;font-weight:bold;padding:3px 10px;border-radius:4px',
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
      suggestions: data.suggestions || [],
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

// ─── Calc audience size (union model: OR logic, selecting more = larger reach) ─
// Sorts known sizes desc, applies 30% overlap discount per additional segment.
// Segments with null/0 est_size are counted as "no constraint" (ignored in math).
export function calcAudienceSize(attrs) {
  if (!attrs.length) return 0
  const knownSizes = attrs.map(a => a.est_size || 0).filter(s => s > 0)
  if (!knownSizes.length) return 0
  knownSizes.sort((a, b) => b - a) // largest first
  let total = 0
  for (let i = 0; i < knownSizes.length; i++) {
    // Each additional segment contributes less (30% overlap assumed)
    total += knownSizes[i] * Math.pow(0.7, i)
  }
  return Math.round(total)
}

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
  async boot() {
    await delay(600)
    return agentMessage(
      'Xin chào 👋 Tôi là **Advertising Agent**, trợ lý AI giúp bạn xây dựng và vận hành chiến dịch quảng cáo.\n\nBạn có thể làm theo từng bước hoặc dùng **Campaign Autopilot** để Agent xây dựng bản campaign và chờ bạn duyệt. Hãy bắt đầu bằng Brief nhé!',
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
const DMP_BASE_URL = 'https://api.pawgrammers.io.vn/api/dmp/attributes'
let _dmpCache = null
let _dmpFetchPromise = null

/**
 * Normalize a raw DMP attribute from the real API.
 * Real API shape: { segmentId, type, category, name, fullLabel, sizeMin, sizeMax, sizeRaw }
 */
export function normalizeDmpAttr(raw) {
  const code = raw.segmentId || raw.code || raw.segment_code || String(raw._id || '')
  const name = raw.fullLabel || raw.name || '(unknown)'
  const sizeMin = Number(raw.sizeMin ?? 0)
  const sizeMax = Number(raw.sizeMax ?? 0)
  const estSize = sizeMin && sizeMax ? Math.round((sizeMin + sizeMax) / 2) : (raw.est_size || 0)
  return {
    _uid: code,
    code,
    name,
    type: (raw.type || raw.segment_type || '').toLowerCase(),
    category: raw.category || raw.segment_category || '',
    est_size: estSize,
    sizeMin,
    sizeMax,
    sizeRaw: raw.sizeRaw || null,
  }
}

/**
 * Fetch ALL DMP attributes with pagination.
 * Uses module-level cache so multiple components don't trigger duplicate requests.
 */
export async function fetchDmpAttributes() {
  if (_dmpCache) return _dmpCache
  if (_dmpFetchPromise) return _dmpFetchPromise

  _dmpFetchPromise = (async () => {
    const PAGE_SIZE = 100
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
  return `sess_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`
}
let SESSION_ID = _genSessionId()
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
      deterministic,
      vlm: doc.vlm || {},
      override: doc.override || {},
      width: deterministic.width || file.width,
      height: deterministic.height || file.height,
    }
  })
}

/** Upload, enqueue, and wait for terminal creative verdicts before Setup. */
export async function prepareCreativeFiles(files, onProgress = () => {}) {
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
      url = await uploadCreativeFile(file.dataUrl, file.name, file.type)
    }
    if (!url) throw new Error(`Upload creative thất bại: ${file.name}`)
    prepared.push({
      ...file,
      url,
      intendedFormat: inferIntendedFormat(file),
      analysisStatus: file.analysisStatus || 'queued',
    })
    onProgress([...prepared, ...(files || []).slice(index + 1)])
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
  const creativeCommit = await AgentAPI.commitWorkspace('creative', creativeDraft)
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
    throw new Error('Creative intelligence chưa được bật trên agent')
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

export async function uploadCreativeFile(dataUrl, filename, mimeType) {
  if (!dataUrl || !dataUrl.startsWith('data:')) return ''
  try {
    // Convert base64 dataUrl to Blob
    const base64 = dataUrl.split(',')[1]
    const bytes = atob(base64)
    const arr = new Uint8Array(bytes.length)
    for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i)
    const blob = new Blob([arr], { type: mimeType })
    const file = new File([blob], filename, { type: mimeType })

    const form = new FormData()
    form.append('file', file)

    const res = await fetch(`${BACKEND_URL}/api/creative/upload`, {
      method: 'POST',
      body: form,
      signal: AbortSignal.timeout(20000),
    })
    if (!res.ok) {
      console.warn('[uploadCreativeFile] upload failed:', res.status)
      return ''
    }
    const data = await res.json()
    // The AdsPilot backend returns { url } or { path } — normalise
    const raw = data.url || data.path || ''
    // If it's a relative path, prefix with the backend origin
    if (raw && raw.startsWith('/')) {
      const origin = new URL(BACKEND_URL).origin
      return `${origin}${raw}`
    }
    return raw
  } catch (e) {
    console.warn('[uploadCreativeFile] error:', e.message)
    return ''
  }
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
  if (!_orderIdempotencyKey) _orderIdempotencyKey = crypto.randomUUID()
  try {
    const res = await agentFetch(`${AGENT_URL}/api/agent/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
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
      }),
      signal: AbortSignal.timeout(180000),  // chat/order creation
    })
    if (!res.ok) return null
    const data = await res.json()
    // Success → next confirm is a new campaign, needs a new key.
    // (Guard-rejection returns tool 'order_guard'; keep the key so a fixed
    //  retry of the same intent still dedupes.)
    if (data?.meta?.tool === 'order_create') _orderIdempotencyKey = null
    return data
  } catch (e) {
    console.warn('[createCampaignOrder] failed:', e.message)
    return null
  }
}


export const AgentAPI = {

  async boot() {
    const real = await callAgent({ session_id: SESSION_ID, step: -1, message: '' })
    return real ?? AGENT_SCENARIOS.boot()
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
    return real ?? AGENT_SCENARIOS.chat(text, currentStep, formState)
  },

  async approveBrief(briefData) {
    const real = await callAgent({
      session_id: SESSION_ID,
      step: 0,
      message: '',
      formData: { brief: briefData },
    })
    if (real) await this.getWorkspace()
    return real ?? AGENT_SCENARIOS.approveBrief(briefData)
  },

  async approveCreative(creativeData) {
    // Creative is now step 2 (Brief=0, Audience=1, Creative=2)
    const real = await callAgent({
      session_id: SESSION_ID,
      step: 2,
      message: '',
      formData: { creative: creativeData },
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
    if (real) await this.getWorkspace()
    return real ?? AGENT_SCENARIOS.approveAudience(segmentData)
  },

  async approveSetup(setupData) {
    const real = await callAgent({
      session_id: SESSION_ID,
      step: 3,
      message: '',
      formData: { setup: setupData },
    })
    return real ?? AGENT_SCENARIOS.approveSetup(setupData)
  },

  async getResult() {
    const real = await callAgent({
      session_id: SESSION_ID,
      step: 4,
      message: '',
      formData: {},
    })
    return real ?? AGENT_SCENARIOS.showResult()
  },

  /** Probe health — called on app mount to decide badge status */
  async isOnline() {
    return probeAgent()
  },

  /** Generate a fresh session ID — call before newChat() to get a clean backend context. */
  newSession() {
    SESSION_ID = _genSessionId()
    WORKSPACE_REVISION = null
    _workspaceMutationKeys.clear()
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

  /**
   * Commit a workspace field directly to backend session (MongoDB).
   * Called when user clicks 'Đồng ý' proposal button or footer 'Đồng ý & Tiếp tục',
   * bypassing the chat confirm round-trip. Also clears any pending_proposal for the field.
   * @param {string} field - e.g. 'brief', 'segment'
   * @param {any} value - The value to persist
   */
  async commitWorkspace(field, value) {
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

  async setWorkspacePreferences(experienceMode, approvalPolicy = null) {
    try {
      if (WORKSPACE_REVISION == null) await this.getWorkspace()
      const res = await agentFetch(`${AGENT_URL}/api/agent/workspace/preferences`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: SESSION_ID,
          experience_mode: experienceMode,
          approval_policy: approvalPolicy,
          base_revision: WORKSPACE_REVISION,
          actor: 'campaign_operator',
          idempotency_key: `experience:${SESSION_ID}:${experienceMode}:${approvalPolicy || ''}`,
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

  async startAutopilot(approvalPolicy = 'critical_only') {
    try {
      const res = await agentFetch(`${AGENT_URL}/api/agent/autopilot/runs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: SESSION_ID,
          approval_policy: approvalPolicy,
          actor: 'campaign_operator',
          idempotency_key: `autopilot-start:${SESSION_ID}`,
        }),
        signal: AbortSignal.timeout(10000),
      })
      const data = await res.json().catch(() => ({}))
      return res.ok ? data : { ok: false, status: res.status, ...(data.detail || data) }
    } catch (e) {
      return { ok: false, detail: e.message }
    }
  },

  async getAutopilotRun(runId) {
    try {
      const res = await agentFetch(`${AGENT_URL}/api/agent/autopilot/runs/${encodeURIComponent(runId)}`, {
        signal: AbortSignal.timeout(5000),
      })
      return res.ok ? await res.json() : null
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
      return res.ok ? data : { ok: false, status: res.status, ...(data.detail || data) }
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
      return res.ok ? data : { ok: false, status: res.status, ...(data.detail || data) }
    } catch (e) {
      return { ok: false, detail: e.message }
    }
  },

  subscribeAutopilot(runId, onEvent) {
    if (typeof EventSource === 'undefined' || AGENT_API_KEY) return () => {}
    const source = new EventSource(`${AGENT_URL}/api/agent/autopilot/runs/${encodeURIComponent(runId)}/events`)
    const handler = () => onEvent?.()
    ;['run_created', 'task_started', 'task_completed', 'task_waiting_review', 'task_approved', 'task_rejected', 'task_retry_scheduled', 'task_failed', 'run_paused', 'run_resumed', 'run_cancelled'].forEach(type => source.addEventListener(type, handler))
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
      if (!res.ok) return null
      return await res.json()
    } catch (e) {
      console.warn('[reportEntry] failed:', e.message)
      return null
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
   * Generate an ad image using gpt-image-1 via VNG Cloud.
   * @param {Object} briefObj   - formState.brief
   * @param {string} formatId   - one of the AD_FORMATS ids
   * @returns {Promise<{ok, imageB64, formatId, width, height, remaining} | {ok: false, error}>}
   */
  async generateAdImage(briefObj, formatId, customPrompt = '') {
    try {
      const res = await agentFetch(`${AGENT_URL}/api/agent/generate-image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: SESSION_ID,
          brief: briefObj || {},
          format_id: formatId,
          custom_prompt: customPrompt || '',
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
   * Returns { remaining: N, max: 10 }
   */
  async getImageGenStatus() {
    try {
      const res = await agentFetch(
        `${AGENT_URL}/api/agent/image-gen-status?session_id=${SESSION_ID}`,
        { signal: AbortSignal.timeout(5000) }
      )
      if (!res.ok) return { remaining: 10, max: 10 }
      return await res.json()
    } catch {
      return { remaining: 10, max: 10 }
    }
  },

  /**
   * Capture a full-page screenshot of a live test-site URL via Playwright.
   * Only works for whitelisted staging domains (znews-stg, baomoi-stg, zingmp3-stg).
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
