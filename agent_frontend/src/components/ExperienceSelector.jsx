import { Bot, Route, Sparkles, ShieldCheck, ArrowRight, Check } from 'lucide-react'

const modes = [
  {
    id: 'guided',
    title: 'Quy trình từng bước',
    eyebrow: 'Guided Workflow',
    description: 'Bạn kiểm soát từng bước. Agent hỗ trợ phân tích, đề xuất và cập nhật workspace qua chat.',
    icon: Route,
    features: ['Brief → Audience → Creative → Setup', 'Duyệt từng thay đổi quan trọng', 'Có thể chỉnh sửa không theo thứ tự'],
  },
  {
    id: 'autopilot',
    title: 'Campaign Autopilot',
    eyebrow: 'Agentic Workflow',
    description: 'Giao brief, chọn chính sách duyệt và theo dõi Agent tự xây dựng campaign đến bản sẵn sàng launch.',
    icon: Sparkles,
    features: ['Kế hoạch và tiến độ hiển thị rõ', 'Tạm dừng, tiếp tục và review bất kỳ lúc nào', 'Luôn hỏi lại trước khi tạo order'],
  },
]

export default function ExperienceSelector({ onSelect, busy, error }) {
  return (
    <main className="min-h-screen overflow-auto bg-[radial-gradient(circle_at_top_left,_#dcebff_0,_#f4f7fb_38%,_#eef4fb_100%)] px-5 py-8 sm:px-8 sm:py-12">
      <div className="mx-auto flex min-h-[calc(100vh-6rem)] max-w-5xl flex-col justify-center">
        <div className="mb-8 flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-brand-500 shadow-[0_12px_30px_rgba(0,104,255,0.28)]">
            <Bot className="h-6 w-6 text-white" strokeWidth={2.3} />
          </div>
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-brand-600">Advertising Agent</p>
            <p className="text-sm text-slate-600">Campaign workspace thông minh</p>
          </div>
        </div>

        <div className="max-w-3xl">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-brand-200 bg-white/80 px-3 py-1 text-xs font-semibold text-brand-700 shadow-sm">
            <ShieldCheck className="h-3.5 w-3.5" />
            Agent tự động, bạn giữ quyền quyết định
          </span>
          <h1 className="mt-4 text-3xl font-black tracking-tight text-slate-900 sm:text-5xl">
            Bạn muốn xây dựng campaign theo cách nào?
          </h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600 sm:text-lg">
            Chọn cách làm việc cho campaign này. Dù chọn chế độ nào, mọi hành động tạo order đều cần bạn xác nhận.
          </p>
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-2">
          {modes.map(mode => {
            const Icon = mode.icon
            return (
              <button
                key={mode.id}
                type="button"
                disabled={busy}
                onClick={() => onSelect(mode.id)}
                aria-label={`Chọn ${mode.title}: ${mode.description}`}
                className="group flex min-h-[300px] flex-col rounded-3xl border border-slate-200 bg-white p-6 text-left shadow-[0_12px_40px_rgba(28,62,104,0.08)] transition-all hover:-translate-y-1 hover:border-brand-300 hover:shadow-[0_20px_50px_rgba(0,104,255,0.16)] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-brand-200 disabled:cursor-wait disabled:opacity-70"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-50 text-brand-600 transition-colors group-hover:bg-brand-500 group-hover:text-white">
                    <Icon className="h-6 w-6" />
                  </div>
                  <ArrowRight className="h-5 w-5 text-slate-300 transition-transform group-hover:translate-x-1 group-hover:text-brand-500" />
                </div>
                <p className="mt-6 text-xs font-bold uppercase tracking-[0.16em] text-brand-600">{mode.eyebrow}</p>
                <h2 className="mt-2 text-2xl font-extrabold text-slate-900">{mode.title}</h2>
                <p className="mt-3 text-sm leading-6 text-slate-600">{mode.description}</p>
                <ul className="mt-5 space-y-2.5">
                  {mode.features.map(feature => (
                    <li key={feature} className="flex items-start gap-2 text-sm text-slate-600">
                      <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-600">
                        <Check className="h-3 w-3" strokeWidth={3} />
                      </span>
                      {feature}
                    </li>
                  ))}
                </ul>
              </button>
            )
          })}
        </div>

        {error && <p className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
        <p className="mt-6 text-center text-xs text-slate-600">Khi bắt đầu campaign mới, bạn có thể chọn lại chế độ làm việc.</p>
      </div>
    </main>
  )
}
