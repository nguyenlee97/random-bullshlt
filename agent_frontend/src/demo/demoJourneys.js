export const REPORT_VIEWS = [
  'Daily Ops', 'Awareness', 'Consideration', 'Conversion', 'Retention', 'Executive',
]

const commonResult = {
  surface: 'result',
  eyebrow: 'Kết quả đã xác minh',
  title: 'Một campaign hoàn chỉnh, vẫn thuộc quyền kiểm soát của bạn',
  description: 'Order, placement, creative mapping và forecast cùng đọc từ canonical workspace. Demo chỉ hiển thị fixture và không gọi API tạo campaign.',
  signals: ['Launch gate đã duyệt', 'Order demo DEMO-2026-001', 'Không có side effect bên ngoài'],
}

export const DEMO_JOURNEYS = {
  copilot: {
    label: 'Campaign Copilot',
    shortLabel: 'Copilot',
    accent: 'sky',
    steps: [
      {
        id: 'copilot-request', surface: 'chat', eyebrow: '01 · Trao đổi cùng AI',
        title: 'Bắt đầu bằng một brief tự nhiên',
        description: 'Bạn mô tả mục tiêu, ngân sách và bối cảnh. Copilot bóc tách dữ liệu nhưng chỉ đề xuất thay đổi vào workspace.',
        chat: 'Ra mắt dòng xe điện đô thị, mục tiêu awareness, ngân sách 600 triệu trong 6 tuần.',
        signals: ['Brand & objective', 'KPI & ngân sách', 'Thời gian & ràng buộc'],
      },
      {
        id: 'copilot-brief', surface: 'workspace', eyebrow: '02 · Brief',
        title: 'Brief rõ ràng, có thể sửa và duyệt',
        description: 'Các trường campaign được điền có cấu trúc. Mọi chỉnh sửa từ chat xuất hiện dưới dạng proposal trước khi commit.',
        signals: ['Workspace revision 3', 'Proposal chưa tự ghi', 'Human approval'],
      },
      {
        id: 'copilot-audience', surface: 'workspace', eyebrow: '03 · Audience Intelligence',
        title: 'RAG tìm đúng audience từ catalog thật',
        description: 'Hybrid dense + sparse retrieval, exclusion guard và selector chỉ được chọn trong candidate IDs đã grounding.',
        signals: ['310 catalog segments', 'Top-25 grounded pool', '6 segments được chọn'],
      },
      {
        id: 'copilot-creative-review', surface: 'workspace', eyebrow: '04 · Creative Intelligence · Review bắt buộc',
        title: 'Creative phải qua phân tích và xác nhận rõ ràng',
        description: 'Deterministic checks và VLM đánh giá format, semantic fit, brand safety. Copilot không đi tiếp cho đến khi verdict hoàn tất và người dùng xác nhận review.',
        signals: ['1160×250 · PASS', '300×600 · PASS', 'Review checkpoint · REQUIRED'],
      },
      {
        id: 'copilot-setup', surface: 'workspace', eyebrow: '05 · Setup',
        title: 'Placement và creative mapping có thể kiểm tra',
        description: 'Copilot xếp hạng zone theo mục tiêu, inventory và creative compatibility rồi trình bày mapping trước khi launch.',
        signals: ['6 placement candidates', 'Exact-size compatibility', 'Order guard ready'],
      },
      {
        id: 'copilot-launch', surface: 'workspace', eyebrow: '06 · Launch gate',
        title: 'Không có campaign nào được tạo ngầm',
        description: 'Nút duyệt cuối là ranh giới side effect. Trong tour này nó chỉ chuyển fixture demo, tuyệt đối không gọi endpoint tạo order.',
        signals: ['Explicit approval', 'Idempotency key', 'Demo sandbox ON'],
      },
      { id: 'copilot-result', ...commonResult },
      {
        id: 'copilot-reports', surface: 'reports', eyebrow: '08 · Sáu báo cáo',
        title: 'Từ vận hành hằng ngày đến góc nhìn điều hành',
        description: 'Cùng một report module cho Copilot và Autopilot, có KPI, chart, câu hỏi gợi ý và PDF đầy đủ. Dữ liệu delivery hiện được gắn nhãn synthetic showcase.',
        reports: REPORT_VIEWS,
        signals: ['6/6 analyses ready', 'Report Q&A cache', 'Full PDF export'],
      },
    ],
  },
  autopilot: {
    label: 'Campaign Autopilot',
    shortLabel: 'Autopilot',
    accent: 'violet',
    steps: [
      {
        id: 'autopilot-request', surface: 'chat', eyebrow: '01 · Campaign request',
        title: 'Một yêu cầu, một kế hoạch capability có thể quan sát',
        description: 'Autopilot chuyển brief đã duyệt thành run bền vững gồm task, artifact, evidence và review boundary.',
        chat: 'Tạo campaign ra mắt sản phẩm trên Zalo, ưu tiên awareness và chỉ launch sau khi tôi duyệt.',
        signals: ['Canonical conversation', 'Durable run', '18 capability tasks'],
      },
      {
        id: 'autopilot-policy', surface: 'autopilot', eyebrow: '02 · Nguồn creative & policy',
        title: 'Chọn cách AI làm việc trước khi run bắt đầu',
        description: 'Upload hoặc AI generation là lựa chọn rõ ràng. Policy quyết định review nào có thể tự qua; final launch luôn cần người dùng.',
        signals: ['AI generate · tối đa 3 asset', 'Critical-only policy', 'Final approval luôn bắt buộc'],
      },
      {
        id: 'autopilot-strategy', surface: 'autopilot', eyebrow: '03 · Strategy',
        title: 'Agent xây strategy và mô phỏng phân bổ',
        description: 'Các phương án budget, reach, frequency và CPM được tạo thành artifact có version để người dùng so sánh hoặc sửa tại review gate.',
        signals: ['Plan v2', 'Budget 600M', 'Reach forecast 5.2M'],
      },
      {
        id: 'autopilot-audience', surface: 'autopilot', eyebrow: '04 · Audience RAG',
        title: 'Audience có catalog source và lý do chọn',
        description: 'Query rewrite giữ ý định gốc, hybrid retrieval hợp nhất nhiều tín hiệu và guard chặn segment ngoài catalog hoặc vi phạm exclusion.',
        signals: ['Grounded IDs only', 'Exclusion guard PASS', 'RAG evidence attached'],
      },
      {
        id: 'autopilot-creative', surface: 'autopilot', eyebrow: '05 · Creative generation & analysis',
        title: 'Tạo đúng format, rồi đi qua cùng Creative Intelligence',
        description: 'Placement intent sinh format plan, worker tạo song song có giới hạn và lưu provenance. AI generation không được bỏ qua VLM hoặc manual review.',
        signals: ['3 exact-size assets', 'Revision-idempotent', 'VLM verdict recorded'],
      },
      {
        id: 'autopilot-placement', surface: 'autopilot', eyebrow: '06 · Placement planning',
        title: 'Hai lượt planning để creative và media khớp thật',
        description: 'Shortlist sơ bộ tạo format intent; final placement chỉ giữ zone tương thích với creative đã được duyệt.',
        signals: ['Placement intent', 'Compatibility rerank', 'Assignment artifact'],
      },
      {
        id: 'autopilot-review', surface: 'autopilot', eyebrow: '07 · Safety review',
        title: 'Run dừng đúng nơi cần phán đoán của con người',
        description: 'Warning, timeout, low confidence hoặc thay đổi quan trọng mở review card với evidence và hành động sửa; không dùng review để ép qua lỗi provider.',
        signals: ['Run waiting_review', 'Evidence visible', 'Approve · Edit · Cancel'],
      },
      {
        id: 'autopilot-launch', surface: 'autopilot', eyebrow: '08 · Launch approval',
        title: 'Final gate ngăn side effect ngoài ý muốn',
        description: 'Order guard xác minh brief, creative, placement và revision. Demo xác nhận bằng fixture nội bộ, không gửi request tạo order.',
        signals: ['Order guard PASS', 'Explicit human decision', 'Demo sandbox ON'],
      },
      {
        id: 'autopilot-timeline', surface: 'timeline', eyebrow: '09 · Event timeline',
        title: 'Mọi task đều có trạng thái, retry và evidence',
        description: 'Task lease, heartbeat, bounded retry và idempotency giúp run tiếp tục sau lỗi mà không nhân đôi image generation hoặc order.',
        signals: ['18/18 tasks', '0 duplicate side effects', 'Stable run trace'],
      },
      { id: 'autopilot-result', ...commonResult },
      {
        id: 'autopilot-reports', surface: 'reports', eyebrow: '11 · Result & six reports',
        title: 'Kết quả, setup report và sáu góc nhìn phân tích',
        description: 'Autopilot tái sử dụng Result và ReportStep của Copilot. Báo cáo synthetic được ghi nhãn rõ cho đến khi live delivery thay thế.',
        reports: REPORT_VIEWS,
        signals: ['Canonical result', '6 report views', 'PDF & cached Q&A'],
      },
      {
        id: 'autopilot-zalo', surface: 'zalo', eyebrow: '12 · Zalo ↔ Web continuity',
        title: 'Cùng một campaign, tiếp tục trên Zalo hoặc trình duyệt',
        description: 'Zalo dùng server-owned campaign registry và canonical conversation: xem trạng thái, report, live view, approve review và nhận workspace link mà không tạo hệ thống thứ hai.',
        chat: 'Campaign đã hoàn tất. Xem báo cáo Executive hoặc mở workspace trên web?',
        signals: ['Owned campaigns only', 'Cross-device resume', 'One canonical workspace'],
      },
    ],
  },
}

export function createDemoState(mode = 'copilot') {
  const resolvedMode = DEMO_JOURNEYS[mode] ? mode : 'copilot'
  return { mode: resolvedMode, index: 0, paused: false, completed: false }
}

export function demoTransition(state, action) {
  const journey = DEMO_JOURNEYS[state.mode]
  const lastIndex = journey.steps.length - 1
  switch (action.type) {
    case 'NEXT': {
      const index = Math.min(state.index + 1, lastIndex)
      return { ...state, index, completed: index === lastIndex }
    }
    case 'PREVIOUS':
      return { ...state, index: Math.max(0, state.index - 1), completed: false }
    case 'TOGGLE_PAUSE':
      return { ...state, paused: !state.paused }
    case 'SKIP':
      return { ...state, index: lastIndex, paused: true, completed: true }
    case 'RESTART':
      return createDemoState(state.mode)
    case 'SET_MODE':
      return createDemoState(action.mode)
    default:
      return state
  }
}
