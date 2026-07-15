// ─── Demo Scripts: Brief Pool + Step Sequences ──────────────────────────────
// Used by DemoEngine to drive the guided walkthrough.

// ─── Predefined Brief Pool (randomly selected per demo run) ─────────────────
export const DEMO_BRIEFS = [
  // 1. Mixi — Social networking app
  {
    id: 'mixi',
    chatMessage:
      'Brief chiến dịch:\n' +
      '- Brand: Mixi\n' +
      '- Objective: awareness\n' +
      '- KPI: Reach\n' +
      '- Budget: 150 triệu VND\n' +
      '- Thời gian: 30/6/2026 đến 7/7/2026\n' +
      '- Ghi chú: Đối tượng Nam 18–30 tuổi, quan tâm mạng xã hội và gaming',
    briefPatch: { brand: 'Mixi', objective: 'awareness', kpi: 'Reach', budget: 150, startDate: '2026-06-30', endDate: '2026-07-07', notes: 'Nam 18–30, mạng xã hội & gaming' },
    budgetEdit: 180,
  },
  // 2. Café 24 — F&B chain
  {
    id: 'cafe24',
    chatMessage:
      'Brief chiến dịch:\n' +
      '- Brand: Café 24\n' +
      '- Objective: awareness\n' +
      '- KPI: CTR\n' +
      '- Budget: 250 triệu VND\n' +
      '- Thời gian: 30/6/2026 đến 7/7/2026\n' +
      '- Ghi chú: Đối tượng Nữ 22–35, thích cà phê và lifestyle',
    briefPatch: { brand: 'Café 24', objective: 'awareness', kpi: 'CTR', budget: 250, startDate: '2026-06-30', endDate: '2026-07-07', notes: 'Nữ 22–35, café & lifestyle' },
    budgetEdit: 300,
  },
  // 3. ZPlay — Mobile gaming
  {
    id: 'zplay',
    chatMessage:
      'Brief chiến dịch:\n' +
      '- Brand: ZPlay\n' +
      '- Objective: awareness\n' +
      '- KPI: Reach, VTR\n' +
      '- Budget: 200 triệu VND\n' +
      '- Thời gian: 30/6/2026 đến 7/7/2026\n' +
      '- Ghi chú: Đối tượng Nam 15–28, gaming và esports',
    briefPatch: { brand: 'ZPlay', objective: 'awareness', kpi: 'Reach, VTR', budget: 200, startDate: '2026-06-30', endDate: '2026-07-07', notes: 'Nam 15–28, gaming & esports' },
    budgetEdit: 220,
  },
  // 4. VPBank Neo — Digital banking / Fintech
  {
    id: 'vpbank-neo',
    chatMessage:
      'Brief chiến dịch:\n' +
      '- Brand: VPBank Neo\n' +
      '- Objective: awareness\n' +
      '- KPI: CTR, Reach\n' +
      '- Budget: 400 triệu VND\n' +
      '- Thời gian: 30/6/2026 đến 7/7/2026\n' +
      '- Ghi chú: Đối tượng 22–40 tuổi, quan tâm tài chính số và đầu tư',
    briefPatch: { brand: 'VPBank Neo', objective: 'awareness', kpi: 'CTR, Reach', budget: 400, startDate: '2026-06-30', endDate: '2026-07-07', notes: '22–40, tài chính số & đầu tư' },
    budgetEdit: 450,
  },
  // 5. Tiki — E-commerce
  {
    id: 'tiki',
    chatMessage:
      'Brief chiến dịch:\n' +
      '- Brand: Tiki\n' +
      '- Objective: awareness\n' +
      '- KPI: CTR\n' +
      '- Budget: 350 triệu VND\n' +
      '- Thời gian: 30/6/2026 đến 7/7/2026\n' +
      '- Ghi chú: Đối tượng 20–45 tuổi, thích mua sắm online và deals',
    briefPatch: { brand: 'Tiki', objective: 'awareness', kpi: 'CTR', budget: 350, startDate: '2026-06-30', endDate: '2026-07-07', notes: '20–45, mua sắm online & deals' },
    budgetEdit: 400,
  },
  // 6. Gentis — Healthcare / DNA testing
  {
    id: 'gentis',
    chatMessage:
      'Brief chiến dịch:\n' +
      '- Brand: Gentis\n' +
      '- Objective: awareness\n' +
      '- KPI: Reach, VTR\n' +
      '- Budget: 180 triệu VND\n' +
      '- Thời gian: 30/6/2026 đến 7/7/2026\n' +
      '- Ghi chú: Đối tượng 28–50 tuổi, quan tâm sức khỏe và y tế gia đình',
    briefPatch: { brand: 'Gentis', objective: 'awareness', kpi: 'Reach, VTR', budget: 180, startDate: '2026-06-30', endDate: '2026-07-07', notes: '28–50, sức khỏe & y tế gia đình' },
    budgetEdit: 200,
  },
  // 7. ELSA Speak — EdTech / English learning
  {
    id: 'elsa',
    chatMessage:
      'Brief chiến dịch:\n' +
      '- Brand: ELSA Speak\n' +
      '- Objective: awareness\n' +
      '- KPI: CTR, Reach\n' +
      '- Budget: 220 triệu VND\n' +
      '- Thời gian: 30/6/2026 đến 7/7/2026\n' +
      '- Ghi chú: Đối tượng 16–35 tuổi, sinh viên và đi làm muốn học tiếng Anh',
    briefPatch: { brand: 'ELSA Speak', objective: 'awareness', kpi: 'CTR, Reach', budget: 220, startDate: '2026-06-30', endDate: '2026-07-07', notes: '16–35, sinh viên & đi làm học tiếng Anh' },
    budgetEdit: 250,
  },
  // 8. Vietjet Air — Low-cost travel
  {
    id: 'vietjet',
    chatMessage:
      'Brief chiến dịch:\n' +
      '- Brand: Vietjet Air\n' +
      '- Objective: awareness\n' +
      '- KPI: Reach, VTR\n' +
      '- Budget: 500 triệu VND\n' +
      '- Thời gian: 30/6/2026 đến 7/7/2026\n' +
      '- Ghi chú: Đối tượng 20–45 tuổi, thích du lịch và săn vé giá rẻ',
    briefPatch: { brand: 'Vietjet Air', objective: 'awareness', kpi: 'Reach, VTR', budget: 500, startDate: '2026-06-30', endDate: '2026-07-07', notes: '20–45, du lịch & săn vé rẻ' },
    budgetEdit: 550,
  },
  // 9. Cocoon — Vietnamese beauty / skincare
  {
    id: 'cocoon',
    chatMessage:
      'Brief chiến dịch:\n' +
      '- Brand: Cocoon\n' +
      '- Objective: awareness\n' +
      '- KPI: CTR, Reach\n' +
      '- Budget: 160 triệu VND\n' +
      '- Thời gian: 30/6/2026 đến 7/7/2026\n' +
      '- Ghi chú: Đối tượng Nữ 18–35, quan tâm làm đẹp và skincare thuần Việt',
    briefPatch: { brand: 'Cocoon', objective: 'awareness', kpi: 'CTR, Reach', budget: 160, startDate: '2026-06-30', endDate: '2026-07-07', notes: 'Nữ 18–35, làm đẹp & skincare thuần Việt' },
    budgetEdit: 200,
  },
  // 10. VinFast — EV automotive
  {
    id: 'vinfast',
    chatMessage:
      'Brief chiến dịch:\n' +
      '- Brand: VinFast\n' +
      '- Objective: awareness\n' +
      '- KPI: Reach, VTR\n' +
      '- Budget: 800 triệu VND\n' +
      '- Thời gian: 30/6/2026 đến 7/7/2026\n' +
      '- Ghi chú: Đối tượng 30–55 tuổi, thu nhập khá, quan tâm xe điện và công nghệ',
    briefPatch: { brand: 'VinFast', objective: 'awareness', kpi: 'Reach, VTR', budget: 800, startDate: '2026-06-30', endDate: '2026-07-07', notes: '30–55, thu nhập khá, xe điện & công nghệ' },
    budgetEdit: 900,
  },
]



// Pick a random brief, never repeating the last one
let _lastBriefId = null
export function pickRandomBrief() {
  const pool = _lastBriefId
    ? DEMO_BRIEFS.filter(b => b.id !== _lastBriefId)
    : DEMO_BRIEFS
  const pick = pool[Math.floor(Math.random() * pool.length)]
  _lastBriefId = pick.id
  return pick
}

// ─── Pre-generated creative format metadata ──────────────────────────────────
// These formats are injected automatically after the Box AI generation step.
// Images are served from /public/demo-creatives/{briefId}/{formatId}.png
export const DEMO_AD_FORMAT_META = {
  'zmp3-top-banner':      { width: 2032, height: 528,  label: 'ZMP3 Top Banner Panoramic' },
  'znews-Background':     { width: 1504, height: 704,  label: 'ZNews Desktop Background' },
  'znews-middle-banner':  { width: 2048, height: 512,  label: 'ZNews Mid-page Banner' },
  'znews-side-banner':    { width: 736,  height: 1456, label: 'ZNews Side Skyscraper' },
  'znews-top-banner':     { width: 2224, height: 480,  label: 'ZNews Top Banner Ultra-wide' },
  'zuma-baomoi-masthead': { width: 1160, height: 280,  label: 'Baomoi Masthead Strip' },
  'zuma-Left':            { width: 465,  height: 1200, label: 'Sticky Side Slider Left' },
  'zuma-Right':           { width: 465,  height: 1200, label: 'Sticky Side Slider Right' },
}
export const DEMO_NON_BOX_FORMAT_IDS = Object.keys(DEMO_AD_FORMAT_META)

// ─── Zone → creative format mapping ──────────────────────────────────────────
// null = use the AI-generated box creative (name matches /^ai-zuma-box/)
export const ZONE_FORMAT_MAP = {
  // BaoMoi sticky sidebars (465×1200)
  'BaoMoi_StickyLeft':             'zuma-Left',
  'BaoMoi_StickyRight':            'zuma-Right',
  // Backgrounds (1504×704)
  'BaoMoi_Background':             'znews-Background',
  'Znews_CongNghe_Background':     'znews-Background',
  'Znews_TheThao_Background':      'znews-Background',
  'Znews_GiaiTri_Background':      'znews-Background',
  'Znews_DoiSong_Background':      'znews-Background',
  'Znews_SucKhoe_Background':      'znews-Background',
  'Znews_KinhDoanh_Background':    'znews-Background',
  // ZMP3 masthead (2032×528)
  'ZingMP3_Masthead':              'zmp3-top-banner',
  // ZNews top mastheads (2224×480)
  'ZingNews_Masthead':             'znews-top-banner',
  // Mid-page / inline (2048×512)
  'ZingNews_Masthead_Inline_1':    'znews-middle-banner',
  'ZingNews_Halfpage':             'znews-middle-banner',
  // Skyscrapers / side banners (736×1456)
  'Znews_CongNghe_SideLeft':      'znews-side-banner',
  'Znews_CongNghe_SideRight':     'znews-side-banner',
  'Znews_TheThao_SideLeft':       'znews-side-banner',
  'Znews_TheThao_SideRight':      'znews-side-banner',
  'Znews_GiaiTri_SideLeft':       'znews-side-banner',
  'Znews_GiaiTri_SideRight':      'znews-side-banner',
  'Znews_DoiSong_SideLeft':       'znews-side-banner',
  'Znews_DoiSong_SideRight':      'znews-side-banner',
  'Znews_SucKhoe_SideLeft':       'znews-side-banner',
  'Znews_SucKhoe_SideRight':      'znews-side-banner',
  'Znews_KinhDoanh_SideLeft':     'znews-side-banner',
  'Znews_KinhDoanh_SideRight':    'znews-side-banner',
  // Box zones → null = AI-generated box
  'ZingNews_PrBox_2':              null,
  'Znews_KinhDoanh_SidebarBox':   null,
  'Znews_DoiSong_SidebarBox':     null,
  'Znews_TheThao_SidebarBox':     null,
  'Znews_GiaiTri_SidebarBox':     null,
  'Znews_SucKhoe_SidebarBox':     null,
  'BaoMoi_Box1':                  null,
  'BaoMoi_Box2':                  null,
}


// TYPE_AND_SEND    — type text into chat input and send it (real API call)
// WAIT_FOR_RESPONSE— pause until busy=false & new assistant message arrives
// HIGHLIGHT_MSG    — scroll to & spotlight last assistant message
// HIGHLIGHT_EL     — spotlight a DOM element + tooltip
// EDIT_FIELD       — programmatically change a form field
// CLICK_EL         — programmatically click a DOM element
// WAIT_FOR_EVENT   — wait for a CustomEvent before advancing
// POPUP            — show a confirmation/info popup
// PAUSE            — wait N ms then auto-advance

// ─── Stage 1: UI Tour ────────────────────────────────────────────────────────
export const STAGE1_STEPS = [
  {
    type: 'TOOLTIP',
    target: '[data-demo="chat-pane"]',
    position: 'right',
    title: '💬 Chat Zone',
    text: 'Đây là **Chat Zone** — nơi bạn trò chuyện với AI Agent. Bạn có thể nhập brief, hỏi đáp, điều chỉnh chiến dịch — tất cả qua chat tự nhiên bằng tiếng Việt.',
  },
  {
    type: 'TOOLTIP',
    target: '[data-demo="chat-thread"]',
    position: 'right',
    title: '🤖 Chat Bubble',
    text: 'Agent sẽ trả lời ở đây — bao gồm text, bảng dữ liệu, và các nút hành động. Mỗi tin nhắn hiển thị tool đã dùng và model AI.',
  },
  {
    type: 'TOOLTIP',
    target: '[data-demo="chat-chips"]',
    position: 'top',
    title: '⚡ Gợi ý nhanh',
    text: 'Các chip gợi ý giúp bạn trả lời nhanh mà không cần gõ. Thay đổi theo từng bước để phù hợp ngữ cảnh.',
  },
  {
    type: 'TOOLTIP',
    target: '#chat-input',
    position: 'top',
    title: '⌨️ Ô nhập chat',
    text: 'Hoặc gõ trực tiếp — agent hiểu tiếng Việt tự nhiên. Nhấn Enter để gửi.',
  },
  {
    type: 'TOOLTIP',
    target: '[data-demo="workspace-pane"]',
    position: 'left',
    title: '📋 Workspace',
    text: 'Đây là **Workspace** — nơi hiển thị form dữ liệu chiến dịch theo từng bước. Dữ liệu sẽ tự động được điền khi bạn chat với agent.',
  },
  {
    type: 'TOOLTIP',
    target: '[data-demo="stepper"]',
    position: 'bottom',
    title: '🔢 Thanh tiến trình',
    text: '7 bước tạo chiến dịch: **Brief → Audience → Creative → Setup → Kết quả → Report → Email**. Click vào từng bước để xem chi tiết.',
  },
  {
    type: 'TOOLTIP',
    target: '[data-demo="step-body"]',
    position: 'left',
    title: '📝 Form từng bước',
    text: 'Mỗi bước có form tương ứng. Bạn có thể điền trực tiếp hoặc để agent tự điền qua chat. Workspace và Chat luôn đồng bộ hai chiều.',
  },
  {
    type: 'TOOLTIP',
    target: '[data-demo="approve-btn"]',
    position: 'top',
    title: '✅ Đồng ý & Tiếp tục',
    text: 'Xác nhận dữ liệu bước hiện tại và chuyển sang bước tiếp theo. Hoặc bạn có thể xác nhận qua chat bằng cách nói "Duyệt nhé" hay "Oke nhé".',
  },
  {
    type: 'TOOLTIP',
    target: '#new-chat-btn',
    position: 'bottom',
    title: '🆕 New Chat',
    text: '**New Chat** — tạo chiến dịch mới hoàn toàn. Xóa toàn bộ chat và workspace hiện tại.',
  },
  {
    type: 'TOOLTIP',
    target: '[data-demo="reset-btn"]',
    position: 'bottom',
    title: '🔄 Đặt lại',
    text: '**Đặt lại** — reset workspace về trạng thái ban đầu mà không xóa chat. Hữu ích khi muốn sửa lại từ đầu.',
  },
]

// ─── Stage 2: Live Run (Brief → Audience) ────────────────────────────────────
// `brief` is a placeholder replaced at runtime with the randomly picked brief.
export function buildStage2Steps(brief) {
  return [
    // ── Brief submission ──────────────────────────────────────────────────
    {
      type: 'TOOLTIP',
      target: '#chat-input',
      position: 'top',
      title: '📨 Gửi Brief',
      text: 'Demo sẽ nhập brief chiến dịch vào chat. Đây là cách tự nhiên nhất để bắt đầu — agent sẽ tự động phân tích và điền form.',
    },
    {
      type: 'TYPE_AND_SEND',
      text: brief.chatMessage,
      tooltip: {
        target: '#chat-input',
        position: 'top',
        title: '⏳ Đang gửi...',
        text: 'Agent đang xử lý brief. Thông thường mất 5–15 giây tùy độ dài brief.',
      },
    },
    {
      type: 'WAIT_FOR_RESPONSE',
      tooltip: {
        target: '[data-demo="chat-thread"]',
        position: 'right',
        title: '⏳ Chờ phản hồi...',
        text: 'Agent đang phân tích brief và chuẩn bị workspace...',
      },
    },
    {
      type: 'HIGHLIGHT_MSG',
      position: 'right',
      title: '📋 Agent phản hồi',
      text: 'Agent trả về yêu cầu xác nhận — bao gồm bảng tóm tắt brief. Workspace bên phải đã được tự động điền dữ liệu.',
    },
    // ── Workspace populated — show & edit ─────────────────────────────────
    {
      type: 'HIGHLIGHT_EL',
      target: '[data-demo="step-body"]',
      position: 'left',
      title: '📝 Brief đã điền',
      text: `Workspace đã nhận dữ liệu từ brief: **${brief.briefPatch.brand}**, ngân sách **${brief.briefPatch.budget} triệu**. Bạn có thể chỉnh sửa trực tiếp tại đây hoặc qua chat.`,
    },
    {
      type: 'EDIT_FIELD',
      path: 'brief.budget',
      value: brief.budgetEdit,
      tooltip: {
        target: '#brief-budget',
        position: 'left',
        title: '✏️ Chỉnh sửa',
        text: `Ví dụ: mình đổi ngân sách từ **${brief.briefPatch.budget} triệu** → **${brief.budgetEdit} triệu**. Agent sẽ cập nhật khi bạn xác nhận.`,
      },
    },
    {
      type: 'TOOLTIP',
      target: '[data-demo="approve-btn"]',
      position: 'top',
      title: '✅ Xác nhận Brief',
      text: 'Nhấn **Đồng ý & Tiếp tục** để xác nhận brief và chuyển sang bước Audience.',
    },
    {
      type: 'CLICK_EL',
      target: '[data-demo="approve-btn"]',
      tooltip: {
        target: '[data-demo="approve-btn"]',
        position: 'top',
        title: '⏳ Đang xác nhận...',
        text: 'Đang gửi brief đến hệ thống...',
      },
    },
    // ── Brief confirmed — two messages appear ─────────────────────────────
    {
      type: 'HIGHLIGHT_MSG',
      position: 'right',
      title: '✅ Brief xác nhận!',
      text: 'Agent xác nhận brief thành công! Tin nhắn tóm tắt toàn bộ brief xuất hiện ở đây.',
    },
    {
      type: 'WAIT_FOR_MSG',
      metaTool: 'audience_entry',
      timeout: 30000,
      tooltip: {
        target: '[data-demo="chat-thread"]',
        position: 'right',
        title: '⏳ Chờ Audience Entry...',
        text: 'Agent đang phân tích brief để đề xuất audience segments phù hợp. Nếu đã sẵn, demo sẽ tiếp tục ngay.',
      },
    },
    {
      type: 'HIGHLIGHT_MSG',
      position: 'right',
      title: '👥 Audience Entry',
      text: 'Đây là **Audience Entry** — agent phân tích brief và đề xuất DMP segments phù hợp, cùng targeting parameters (tuổi, giới tính, địa lý). Bạn có thể chấp nhận hoặc chỉnh sửa.',
    },
    // ── Audience step explanation ──────────────────────────────────────────
    {
      type: 'HIGHLIGHT_EL',
      target: '[data-demo="step-body"]',
      position: 'left',
      title: '🎯 Bước Audience',
      text: 'Workspace chuyển sang bước **Audience**. Tại đây bạn chọn targeting parameters và DMP segments cho chiến dịch.',
    },
    {
      type: 'CLICK_EL',
      target: '[data-demo="targeting-panel-toggle"]',
      tooltip: {
        target: '[data-demo="targeting-panel-toggle"]',
        position: 'left',
        title: '📊 Targeting Parameters',
        text: 'Mở phần **Targeting Parameters** để xem tuổi, giới tính, địa lý, device...',
      },
      delay: 1000,
    },
    {
      type: 'HIGHLIGHT_EL',
      target: '[data-demo="step-body"]',
      position: 'left',
      title: '📊 Targeting đã mở',
      text: 'Agent đã tự điền các thông số targeting phù hợp với brief: **tuổi, giới tính, địa lý, device OS**. Bạn có thể chỉnh sửa bất kỳ trường nào.',
    },
    {
      type: 'CLICK_EL',
      target: '[data-demo="advanced-targeting-toggle"]',
      tooltip: {
        target: '[data-demo="advanced-targeting-toggle"]',
        position: 'left',
        title: '⚙️ Advanced Targeting',
        text: 'Mở rộng **Advanced Targeting** để xem thêm các trường nâng cao...',
      },
      delay: 800,
    },
    {
      type: 'HIGHLIGHT_EL',
      target: '[data-demo="advanced-targeting-toggle"]',
      position: 'left',
      title: '⚙️ Targeting nâng cao',
      text: 'Các trường **Advanced**: hôn nhân, thu nhập, nghề nghiệp, sở thích, thời tiết. Phù hợp cho các chiến dịch cần nhắm mục tiêu chi tiết hơn.',
    },
    {
      type: 'HIGHLIGHT_EL',
      target: '[data-demo="ai-reco-section"]',
      position: 'left',
      title: '🧠 AI Gợi ý Segments',
      text: 'Phần **AI Gợi ý** — các DMP Audience Segments đã được tự động chọn dựa theo brief. Mỗi segment có lý do được gợi ý. Bạn có thể bỏ chọn hoặc thêm segment khác.',
    },
    {
      type: 'CLICK_EL',
      target: '[data-demo="expand-segments-btn"]',
      tooltip: {
        target: '[data-demo="expand-segments-btn"]',
        position: 'left',
        title: '📋 Xem tất cả Segments',
        text: 'Click để xem toàn bộ danh sách DMP segments hiện có trong hệ thống.',
      },
      delay: 600,
    },
    {
      type: 'HIGHLIGHT_EL',
      target: '[data-demo="expand-segments-btn"]',
      position: 'left',
      title: '📋 Danh sách đầy đủ',
      text: 'Toàn bộ danh sách DMP segments. Bạn có thể sửa qua workspace hoặc qua chat — cả 2 đều được. Xác nhận cũng vậy: nút bên workspace hoặc chat.',
    },
    {
      type: 'TOOLTIP',
      target: '[data-demo="chat-thread"]',
      position: 'right',
      title: '✅ Xác nhận Audience',
      text: 'Để xác nhận audience, bạn có thể: nhấn nút **"✅ Áp dụng tất cả segments"** trong tin nhắn chat, hoặc nút **Đồng ý & Tiếp tục** bên workspace, hoặc gõ chat "Oke nhé".',
    },
    {
      type: 'CLICK_EL',
      target: '[data-demo="approve-btn"]',
      tooltip: {
        target: '[data-demo="approve-btn"]',
        position: 'top',
        title: '⏳ Đang xác nhận Audience...',
        text: 'Đang gửi audience segments đến hệ thống...',
      },
    },
    // audience approve → triggers creative_entry (separate GET, not busy cycle)
    // Skip WAIT_FOR_RESPONSE — go straight to next step
    {
      type: 'HIGHLIGHT_MSG',
      position: 'right',
      title: '🎉 Audience xác nhận!',
      text: '✅ Audience đã xác nhận! Agent chuyển sang bước **Creative** tiếp theo. Demo của 2 bước đầu đã hoàn thành.',
    },
    // ── Transition into Creative step ─────────────────────────────────────
    {
      type: 'HIGHLIGHT_MSG',
      position: 'right',
      title: '🎨 Audience xác nhận — bước Creative!',
      text: 'Audience đã xác nhận thành công! 🎉 Agent chuyển sang bước **Creative**.\n\nBây giờ mình sẽ cùng xem qua 2 cách thêm creative: **Upload** thủ công và **AI Tạo Ảnh** tự động.',
    },

    // ── Creative Step: Upload tab introduction ──────────────────────────────
    {
      type: 'HIGHLIGHT_EL',
      target: '#creative-tab-upload',
      position: 'bottom',
      title: '📎 Tab Upload',
      text: 'Cách đầu tiên: **kéo thả** hoặc chọn file ảnh/video từ máy tính.\n\nHỗ trợ PNG, JPG, MP4 — hệ thống tự đọc độ phân giải và kích thước.',
    },
    {
      type: 'HIGHLIGHT_EL',
      target: '#creative-drop-zone',
      position: 'top',
      title: '📂 Kéo thả file vào đây',
      text: 'Vùng **kéo thả** — chấp nhận nhiều file cùng lúc. Thông tin kích thước và độ phân giải sẽ được đọc tự động sau khi upload.',
    },

    // ── Switch to AI tab ────────────────────────────────────────────────────
    {
      type: 'CLICK_EL',
      target: '#creative-tab-ai',
      tooltip: {
        target: '#creative-tab-ai',
        position: 'bottom',
        title: '🤖 Chuyển sang AI Tạo Ảnh',
        text: 'Cách thứ hai: dùng **AI sinh ảnh** trực tiếp từ brief. Chọn định dạng, thêm prompt tuỳ chỉnh, rồi để AI lo phần còn lại.',
      },
      delay: 400,
    },

    // ── Brief pause so panel renders before highlighting ────────────────────
    {
      type: 'PAUSE',
      ms: 500,
    },

    // ── Introduce the AI panel layout ───────────────────────────────────────
    {
      type: 'TOOLTIP',
      target: '#btn-ai-generate',
      position: 'top',
      title: '🎨 Bảng điều khiển AI Tạo Ảnh',
      text: 'Panel AI có **3 phần chính**:\n① **Chọn định dạng** — kích thước & tỉ lệ ảnh đầu ra\n② **Prompt tuỳ chỉnh** — hướng dẫn thêm về phong cách, màu sắc (tùy chọn)\n③ **Tạo ảnh** — AI sinh ảnh theo brief + prompt, kết quả hiện ngay bên dưới',
    },

    // ── Explain the format picker ───────────────────────────────────────────
    {
      type: 'HIGHLIGHT_EL',
      target: '#format-zuma-box',
      position: 'right',
      title: '📐 Định dạng ảnh — nhiều lựa chọn',
      text: 'Hệ thống hỗ trợ **nhiều định dạng quảng cáo** khác nhau: banner ngang, skin toàn trang, skyscraper, box...\n\nMỗi định dạng phù hợp với một vị trí hiển thị cụ thể trên các trang Zing.\n\n👉 Trong demo này, chúng ta thử với **Display Box 300×250** — kích thước IAB phổ biến nhất trên desktop.',
    },

    // ── Select the format ───────────────────────────────────────────────────
    {
      type: 'CLICK_EL',
      target: '#format-zuma-box',
      tooltip: {
        target: '#format-zuma-box',
        position: 'right',
        title: '✅ Chọn Display Box 300×250',
        text: 'Đang chọn định dạng **Display Box** cho ví dụ này...',
      },
      delay: 400,
    },

    // ── Open custom prompt accordion ─────────────────────────────────────
    {
      type: 'HIGHLIGHT_EL',
      target: '#btn-toggle-custom-prompt',
      position: 'top',
      title: '✏️ Prompt tùy chỉnh (không bắt buộc)',
      text: 'Ngoài brief, bạn có thể thêm **yêu cầu sáng tạo** cụ thể: phong cách thiết kế, màu sắc, bố cục, vibe...\n\nAI sẽ kết hợp cả brief gốc và prompt này khi sinh ảnh.',
    },
    {
      type: 'CLICK_EL',
      target: '#btn-toggle-custom-prompt',
      tooltip: {
        target: '#btn-toggle-custom-prompt',
        position: 'top',
        title: '📝 Mở phần nhập Prompt',
        text: 'Mở phần nhập prompt tùy chỉnh...',
      },
      delay: 300,
    },

    // ── Type the custom prompt ────────────────────────────────────────────
    {
      type: 'TYPE_INPUT',
      target: '#custom-prompt-input',
      inputText: 'Thiết kế tối giản, hạn chế tối đa chữ (chỉ làm rõ tên thương hiệu), tập trung vào hình ảnh trực quan bắt mắt và các chi tiết cuốn hút phù hợp với sở thích của đối tượng mục tiêu.',
      charDelay: 14,
      title: '⌨️ Nhập Prompt tùy chỉnh',
      text: 'Đang nhập yêu cầu sáng tạo...\n\nPrompt này hướng AI tập trung vào **hình ảnh thương hiệu** rõ nét, tối giản chữ và phù hợp với đối tượng mục tiêu đã xác định ở bước Audience.',
    },

    // ── Click generate ─────────────────────────────────────────────────────
    {
      type: 'HIGHLIGHT_EL',
      target: '#btn-ai-generate',
      position: 'top',
      title: '🚀 Tạo ảnh AI',
      text: 'Nhấn **Tạo ảnh AI** để bắt đầu. AI sẽ mất khoảng **30–60 giây** để sinh ảnh.\n\nSau khi hoàn thành, bạn sẽ được chọn giữa **Crop** (cắt chính xác) hoặc **Scale** (co giãn toàn ảnh).',
    },
    {
      type: 'CLICK_EL',
      target: '#btn-ai-generate',
      tooltip: {
        target: '#btn-ai-generate',
        position: 'top',
        title: '⏳ Đang tạo ảnh AI...',
        text: 'AI đang xử lý yêu cầu. Quá trình này mất khoảng 30–60 giây — hãy đợi một chút ☕',
      },
      delay: 300,
    },

    // ── Wait for crop modal to appear ──────────────────────────────────────
    {
      type: 'WAIT_FOR_SELECTOR',
      target: '#btn-crop-scale',
      timeout: 90000,
      title: '⏳ Đang chờ AI sinh ảnh...',
      text: 'AI đang tạo ảnh theo brief và prompt. Quá trình thường mất **30–60 giây**.\n\nSau khi xong, cửa sổ crop sẽ xuất hiện để bạn tinh chỉnh khung ảnh.',
    },

    // ── Explain crop vs scale ───────────────────────────────────────────────
    {
      type: 'HIGHLIGHT_EL',
      target: '#btn-crop-confirm',
      position: 'bottom',
      title: '✂️ Crop & Dùng',
      text: '**Crop**: kéo thả khung để cắt chính xác vùng ảnh muốn giữ. Tỉ lệ khung được khóa theo định dạng đã chọn.\n\nDùng khi bạn muốn chọn vùng nội dung cụ thể từ ảnh AI.',
    },
    {
      type: 'HIGHLIGHT_EL',
      target: '#btn-crop-scale',
      position: 'bottom',
      title: '↔️ Giữ nguyên & Scale',
      text: '**Scale**: co giãn toàn bộ ảnh AI vào đúng kích thước định dạng mà không cắt bỏ vùng nào.\n\nLý tưởng khi ảnh AI đã có bố cục tốt và bạn muốn giữ nguyên toàn cảnh. Chúng ta sẽ dùng tùy chọn này cho demo!',
    },

    // ── Click Scale ─────────────────────────────────────────────────────────
    {
      type: 'CLICK_EL',
      target: '#btn-crop-scale',
      tooltip: {
        target: '#btn-crop-scale',
        position: 'bottom',
        title: '↔️ Áp dụng Scale...',
        text: 'Đang scale ảnh về đúng tỉ lệ 300×250px...',
      },
      delay: 300,
    },

    // ── Wait for image to appear in gallery, then select it ─────────────────
    {
      type: 'WAIT_FOR_SELECTOR',
      target: '[id^="gen-img-ai-zuma-box"]',
      timeout: 10000,
      title: '⏳ Xử lý ảnh...',
      text: 'Đang xử lý và hiển thị ảnh vào thư viện...',
    },
    {
      type: 'HIGHLIGHT_EL',
      target: '[id^="gen-img-ai-zuma-box"]',
      position: 'top',
      title: '🖼️ Ảnh đã được tạo!',
      text: 'Ảnh AI vừa sinh xong hiển thị trong **thư viện**. Bạn có thể **chọn nhiều ảnh** rồi thêm tất cả vào creative cùng lúc.\n\nNhấn vào ô chọn để đánh dấu ảnh muốn dùng.',
    },
    {
      type: 'CLICK_EL',
      target: '[data-demo="gen-img-footer"]',
      tooltip: {
        target: '[id^="gen-img-ai-zuma-box"]',
        position: 'top',
        title: '✅ Chọn ảnh để thêm vào Creative',
        text: 'Đang chọn ảnh vừa tạo...',
      },
      delay: 400,
    },

    // ── Add to Creative ──────────────────────────────────────────────────────
    {
      type: 'HIGHLIGHT_EL',
      target: '#btn-add-to-creative',
      position: 'top',
      title: '➕ Thêm vào Creative',
      text: 'Nút **Thêm ảnh vào Creative** sẽ chuyển ảnh AI sang tab Upload và đưa vào pool creative của chiến dịch.\n\nSau đó bạn có thể xác nhận và chuyển sang bước Setup!',
    },
    {
      type: 'CLICK_EL',
      target: '#btn-add-to-creative',
      tooltip: {
        target: '#btn-add-to-creative',
        position: 'top',
        title: '✅ Thêm vào Creative pool...',
        text: 'Đang thêm ảnh AI vào creative...',
      },
      delay: 300,
    },

    // ── Inject all pre-generated creatives (silent loader) ──────────────────
    {
      type: 'INJECT_DEMO_CREATIVES',
      briefId: brief.id,
      title: '⏳ Đang tải creative...',
      text: 'Đang chuẩn bị creative cho tất cả định dạng quảng cáo...',
    },

    // ── Explain injection — user reads and clicks Tiếp theo ────────────────
    {
      type: 'TOOLTIP',
      target: '[data-demo="approve-btn"]',
      position: 'top',
      title: '🖼️ Demo đã thêm creative cho bạn!',
      text: 'Để tiết kiệm thời gian, demo đã tự động thêm **creative cho tất cả 8 định dạng quảng cáo** phù hợp với brief của bạn.\n\nGiờ creative workspace có đầy đủ:\n- **Box 300×250** — vừa tạo bằng AI\n- **8 định dạng còn lại** — được chuẩn bị sẵn\n\nỠ bước Setup, AI sẽ gợi ý các vị trí còn trống và chúng ta đã có creative phù hợp cho mọi vị trí!\n\nTrong thực tế, bạn có thể upload thêm hoặc dùng AI tạo ảnh cho từng định dạng.',
    },

    // ── Short pause for state to settle ──────────────────────────────────────
    {
      type: 'PAUSE',
      ms: 400,
    },

    // ── Highlight approve button ──────────────────────────────────────────────
    {
      type: 'HIGHLIGHT_EL',
      target: '[data-demo="approve-btn"]',
      position: 'top',
      title: '✅ Creative đã sẵn sàng!',
      text: 'Creative workspace giờ có đầy đủ: **Box 300×250** (vừa tạo bằng AI) và **8 định dạng** được chuẩn bị sẵn cho tất cả vị trí quảng cáo. 🎉\n\nỞ bước Setup, AI sẽ gợi ý các vị trí quảng cáo còn trống — và chúng ta đã có creative phù hợp cho mọi vị trí được đề xuất!\n\nNhấn **Đồng ý & Tiếp tục** để xác nhận và chuyển sang bước **Setup Campaign**.',
    },
    {
      type: 'CLICK_EL',
      target: '[data-demo="approve-btn"]',
      tooltip: {
        target: '[data-demo="approve-btn"]',
        position: 'top',
        title: '⏳ Xác nhận Creative...',
        text: 'Đang xác nhận creative và chuyển sang bước Setup...',
      },
    },

    // ── Wait for setup_entry message ────────────────────────────────────────
    {
      type: 'WAIT_FOR_MSG',
      metaTool: 'setup_entry',
      timeout: 30000,
      title: '⏳ Agent đang phân tích zones...',
      text: 'Agent đang phân tích brief, audience và creative để **gợi ý ad zones** phù hợp nhất cho chiến dịch.\n\nBước Setup sẽ xuất hiện ngay sau đây...',
    },

    // ── Highlight setup_entry message ───────────────────────────────────────
    {
      type: 'HIGHLIGHT_MSG',
      position: 'right',
      title: '📍 Setup Campaign — Agent đề xuất Zones!',
      text: 'Agent đã phân tích toàn bộ brief + audience + creative và đề xuất **ad zones** phù hợp nhất trên các trang Zing.\n\nBạn có thể chỉnh sửa zones qua workspace hoặc chat tự nhiên với agent.',
    },


    // ── Intro: Recommended zones section ─────────────────────────────
    {
      type: 'HIGHLIGHT_EL',
      target: '[data-demo="reco-zones-section"]',
      position: 'right',
      title: '🗺️ Zones được AI đề xuất',
      text: 'AI phân tích brief + audience + creative và gợi ý **ad zones phù hợp nhất**.\n\nMỗi zone hiển thị: Reach (lượt tiếp cận), VI (Viewability Index), CTR và CPM.\n\n**Quan trọng**: Các zone này đã được lọc — không bị chiếm bởi chiến dịch nào khác trong khuông thời gian của bạn.',
    },
    {
      type: 'CLICK_EL',
      target: '[data-demo="expand-zones-btn"]',
      tooltip: {
        target: '[data-demo="expand-zones-btn"]',
        position: 'top',
        title: '📋 Xem thêm zones khác',
        text: 'Ngoài các zones được đề xuất, bạn có thể xem toàn bộ danh sách và tự chọn thêm...',
      },
      delay: 400,
    },
    { type: 'PAUSE', ms: 700 },
    {
      type: 'HIGHLIGHT_MSG',
      position: 'right',
      title: '💬 Lý do Agent đề xuất',
      text: 'Bubble chat trên giải thích chi tiết **tại sao** AI chọn những zones này — dựa trên objective, budget, audience profile và lịch sử xung đột.',
    },
    {
      type: 'SELECT_RECO_ZONES',
      count: 2,
      title: '⏳ Đang chọn zones...',
      text: 'Demo đang chọn ngẫu nhiên 2 zones từ danh sách đề xuất...',
    },
    {
      type: 'TOOLTIP',
      target: '[data-demo="reco-zones-section"]',
      position: 'right',
      title: '🎯 Demo chọn 2 zones ngẫu nhiên',
      text: 'Vì AI đã lọc sẵn các zones không xung đột, demo chọn ngẫu nhiên **2 zones** để tiến hành.\n\nTrong thực tế, bạn có thể chọn nhiều zones hơn tùy budget.',
    },
    { type: 'PAUSE', ms: 400 },
    {
      type: 'TOOLTIP',
      target: '#confirm-zones-btn',
      position: 'top',
      title: '➡️ Tiếp tục gắn Creative',
      text: '2 zones đã được chọn. Nhấn **Tiếp tục** để sang bước gắn creative vào từng zone.',
    },
    { type: 'CLICK_EL', target: '#confirm-zones-btn', delay: 300 },
    {
      type: 'WAIT_FOR_SELECTOR',
      target: '[data-demo="auto-assign-btn"]',
      timeout: 8000,
      title: '⏳ Đang chuyển sang gắn creative...',
      text: '',
    },
    {
      type: 'HIGHLIGHT_EL',
      target: '[data-demo="auto-assign-btn"]',
      position: 'bottom',
      title: '🎨 Gắn Creative vào Ad Zone',
      text: 'Mỗi ad zone cần creative phù hợp về **tỷ lệ khung hình**.\n\n- **Tự động gắn**: AI tự chọn creative tốt nhất theo tỷ lệ\n- **Tỷ lệ lệch** (⚠️): cảnh báo nếu creative không khớp kích thước zone\n\nDemo đã chuẩn bị creative cho mọi định dạng — ta chỉ cần gắn đúng file vào đúng zone.',
    },
    {
      type: 'ASSIGN_CREATIVES',
      title: '⏳ Đang gắn creative...',
      text: 'Đang khớp creative với từng ad zone...',
    },
    { type: 'PAUSE', ms: 500 },
    {
      type: 'TOOLTIP',
      target: '#proceed-to-confirm-btn',
      position: 'top',
      title: '📋 Xem Tổng Kết',
      text: 'Creative đã được gắn cho cả 2 zones. Nhấn để **xem tổng kết** và xác nhận tạo chiến dịch.',
    },
    { type: 'CLICK_EL', target: '#proceed-to-confirm-btn', delay: 300 },
    {
      type: 'WAIT_FOR_SELECTOR',
      target: '#create-campaign-btn',
      timeout: 8000,
      title: '⏳ Đang tải tổng kết...',
      text: '',
    },
    {
      type: 'HIGHLIGHT_EL',
      target: '#create-campaign-btn',
      position: 'top',
      title: '✅ Xác nhận & Tạo Chiến Dịch',
      text: 'Workspace tóm tắt đầy đủ: Brief, Audience, Zones với creative đã gắn, budget phân bổ và est. impressions.\n\nKiểm tra lại rồi nhấn **Tiếp theo** để xác nhận và tạo chiến dịch thật trên hệ thống!',
    },
    { type: 'CLICK_EL', target: '#create-campaign-btn', delay: 400 },
    {
      type: 'WAIT_FOR_SELECTOR',
      target: '[data-demo="result-hero"]',
      timeout: 90000,
      title: '⏳ Đang tạo chiến dịch...',
      text: 'Hệ thống đang gửi order đến nền tảng quảng cáo và tạo chiến dịch thật. Vui lòng chờ...',
    },
    {
      type: 'HIGHLIGHT_EL',
      target: '[data-demo="result-hero"]',
      position: 'bottom',
      title: '🎉 Chiến dịch đã được tạo!',
      text: 'Chiến dịch đã chạy thành công trên **nền tảng quảng cáo**. Bước Kết quả tổng hợp thông tin về chiến dịch vừa tạo — từ zones, creative, budget đến các chỉ số dự kiến.',
    },
    {
      type: 'HIGHLIGHT_EL',
      target: '[data-demo="quick-links-card"]',
      position: 'top',
      title: '🔗 Liên Kết Nhanh',
      text: '**Trình quản lý quảng cáo**: Mở trực tiếp trang quản lý chiến dịch để kiểm tra, pause hoặc chỉnh sửa.\n\n**Test Site**: Mở trang web thực tế chứa ad zone để xác nhận quảng cáo đang hiển thị đúng vị trí.',
    },
    {
      type: 'HIGHLIGHT_EL',
      target: '[data-demo="ad-live-card"]',
      position: 'top',
      title: '📸 Ảnh Chụp Ad Live',
      text: 'Khi chiến dịch đang **live**, hệ thống triển khai một **sub-agent** tự động điều hướng đến trang web, chụp ảnh màn hình và cắt chính xác từng ad zone.\n\nKết quả trả về ảnh crop của từng zone kèm toàn cảnh trang có đánh dấu — xác nhận quảng cáo đang chạy đúng vị trí và đúng creative.',
    },
    {
      type: 'HIGHLIGHT_EL',
      target: '[data-demo="kpi-grid"]',
      position: 'top',
      title: '📊 Chỉ Số Dự Kiến',
      text: 'Dựa trên dữ liệu lịch sử của từng zone, hệ thống ước tính:\n- **Impressions**: tổng lượt hiển thị\n- **Avg CTR**: tỷ lệ nhấp trung bình\n- **Avg Viewability**: % quảng cáo thực sự được nhìn thấy\n\nCác con số giúp đánh giá hiệu quả dự kiến ngay sau khi chiến dịch được tạo.',
    },
    {
      type: 'POPUP',
      title: '🎉 Demo hoàn thành!',
      text: 'Bạn đã trải nghiệm toàn bộ luồng:\n**Brief → Audience → Creative → Setup → Kết quả**\n\nAgent đã tự động:\n- ✅ Phân tích brief và điền workspace\n- ✅ Gợi ý DMP audience segments\n- ✅ Sinh ảnh AI và thêm creative pool\n- ✅ Đề xuất ad zones không xung đột\n- ✅ Gắn creative phù hợp và tạo chiến dịch\n- ✅ Hiển thị kết quả và liên kết live\n\nTừ đây, bạn có thể tự khám phá bước **Report** và **Email**!',
      buttons: [
        { label: '🚀 Tiếp tục tự khám phá', variant: 'primary', action: 'skip' },
      ],
    },
  ]
}
