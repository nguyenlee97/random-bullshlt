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
      '- Thời gian: 1/7/2026 đến 19/8/2026\n' +
      '- Ghi chú: Đối tượng Nam 18–30 tuổi, quan tâm mạng xã hội và gaming',
    briefPatch: { brand: 'Mixi', objective: 'awareness', kpi: 'Reach', budget: 15, startDate: '2026-07-01', endDate: '2026-08-19', notes: 'Nam 18–30, mạng xã hội & gaming' },
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
      '- Thời gian: 15/7/2026 đến 26/8/2026\n' +
      '- Ghi chú: Đối tượng Nữ 22–35, thích cà phê và lifestyle',
    briefPatch: { brand: 'Café 24', objective: 'awareness', kpi: 'CTR', budget: 25, startDate: '2026-07-15', endDate: '2026-08-26', notes: 'Nữ 22–35, café & lifestyle' },
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
      '- Thời gian: 10/8/2026 đến 14/9/2026\n' +
      '- Ghi chú: Đối tượng Nam 15–28, gaming và esports',
    briefPatch: { brand: 'ZPlay', objective: 'awareness', kpi: 'Reach, VTR', budget: 20, startDate: '2026-08-10', endDate: '2026-09-14', notes: 'Nam 15–28, gaming & esports' },
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
      '- Thời gian: 1/8/2026 đến 30/9/2026\n' +
      '- Ghi chú: Đối tượng 22–40 tuổi, quan tâm tài chính số và đầu tư',
    briefPatch: { brand: 'VPBank Neo', objective: 'awareness', kpi: 'CTR, Reach', budget: 40, startDate: '2026-08-01', endDate: '2026-09-30', notes: '22–40, tài chính số & đầu tư' },
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
      '- Thời gian: 20/7/2026 đến 20/8/2026\n' +
      '- Ghi chú: Đối tượng 20–45 tuổi, thích mua sắm online và deals',
    briefPatch: { brand: 'Tiki', objective: 'awareness', kpi: 'CTR', budget: 35, startDate: '2026-07-20', endDate: '2026-08-20', notes: '20–45, mua sắm online & deals' },
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
      '- Thời gian: 5/8/2026 đến 5/9/2026\n' +
      '- Ghi chú: Đối tượng 28–50 tuổi, quan tâm sức khỏe và y tế gia đình',
    briefPatch: { brand: 'Gentis', objective: 'awareness', kpi: 'Reach, VTR', budget: 18, startDate: '2026-08-05', endDate: '2026-09-05', notes: '28–50, sức khỏe & y tế gia đình' },
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
      '- Thời gian: 1/9/2026 đến 30/9/2026\n' +
      '- Ghi chú: Đối tượng 16–35 tuổi, sinh viên và đi làm muốn học tiếng Anh',
    briefPatch: { brand: 'ELSA Speak', objective: 'awareness', kpi: 'CTR, Reach', budget: 22, startDate: '2026-09-01', endDate: '2026-09-30', notes: '16–35, sinh viên & đi làm học tiếng Anh' },
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
      '- Thời gian: 15/8/2026 đến 15/9/2026\n' +
      '- Ghi chú: Đối tượng 20–45 tuổi, thích du lịch và săn vé giá rẻ',
    briefPatch: { brand: 'Vietjet Air', objective: 'awareness', kpi: 'Reach, VTR', budget: 50, startDate: '2026-08-15', endDate: '2026-09-15', notes: '20–45, du lịch & săn vé rẻ' },
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
      '- Thời gian: 1/7/2026 đến 31/7/2026\n' +
      '- Ghi chú: Đối tượng Nữ 18–35, quan tâm làm đẹp và skincare thuần Việt',
    briefPatch: { brand: 'Cocoon', objective: 'awareness', kpi: 'CTR, Reach', budget: 16, startDate: '2026-07-01', endDate: '2026-07-31', notes: 'Nữ 18–35, làm đẹp & skincare thuần Việt' },
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
      '- Thời gian: 10/9/2026 đến 10/10/2026\n' +
      '- Ghi chú: Đối tượng 30–55 tuổi, thu nhập khá, quan tâm xe điện và công nghệ',
    briefPatch: { brand: 'VinFast', objective: 'awareness', kpi: 'Reach, VTR', budget: 80, startDate: '2026-09-10', endDate: '2026-10-10', notes: '30–55, thu nhập khá, xe điện & công nghệ' },
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


// ─── Step Types ──────────────────────────────────────────────────────────────
// TOOLTIP          — show tooltip on element, wait for user "Tiếp theo" click
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
    // ── End of Stage 2 demo ───────────────────────────────────────────────
    {
      type: 'POPUP',
      title: '🎉 Demo hoàn thành!',
      text: 'Bạn đã trải nghiệm 2 bước đầu tiên: **Brief** và **Audience**. Từ đây bạn có thể tiếp tục tự khám phá các bước **Creative → Setup → Kết quả** với AI Agent!',
      buttons: [
        { label: '🚀 Tiếp tục tự khám phá', variant: 'primary', action: 'skip' },
      ],
    },
  ]
}
