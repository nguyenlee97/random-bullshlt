import {
  ArrowRight, Bot, CheckCircle2, FileText, Gauge, Layers3, MessageCircle,
  Play, Radio, ShieldCheck, Sparkles, Zap,
} from 'lucide-react'

const capabilities = [
  ['Campaign Copilot', 'AI đồng hành qua Brief, Audience, Creative Intelligence, Setup, launch và sáu báo cáo.', Layers3],
  ['Campaign Autopilot', 'Durable run tự xây strategy, audience, creative và placement; dừng đúng review gate.', Sparkles],
  ['Zalo continuity', 'Theo dõi campaign, xem report/live view và trở lại đúng canonical workspace trên mọi thiết bị.', MessageCircle],
]

const reliability = [
  ['310', 'audience segments được catalog-grounding'],
  ['18', 'capability tasks trong Autopilot plan'],
  ['6', 'góc nhìn báo cáo + PDF đầy đủ'],
  ['0', 'launch không có human approval'],
]

export default function PublicLanding({ onEnterAgent, onOpenDemo }) {
  return (
    <main className="public-landing h-screen h-[100dvh] overflow-y-auto overflow-x-hidden bg-[#030916] text-white">
      <div className="pointer-events-none fixed inset-0 overflow-hidden" aria-hidden="true">
        <div className="landing-orb landing-orb-one" />
        <div className="landing-orb landing-orb-two" />
        <div className="landing-grid" />
      </div>

      <div className="relative mx-auto max-w-7xl px-5 sm:px-8">
        <header className="flex items-center gap-3 py-6">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-cyan-300 shadow-lg shadow-blue-500/25"><Bot className="h-5 w-5" /></div>
          <div><p className="text-xs font-black uppercase tracking-[0.2em] text-blue-300">Advertising Agent</p><p className="text-[11px] text-slate-500">AI campaign operating system</p></div>
          <nav className="ml-auto flex items-center gap-2" aria-label="Điều hướng công khai">
            <a href="/tech-docs.html" className="hidden rounded-xl px-3 py-2 text-xs font-bold text-slate-400 hover:bg-white/5 hover:text-white sm:inline-flex"><FileText className="mr-2 h-4 w-4" />Tài liệu</a>
            <button type="button" onClick={onEnterAgent} className="rounded-xl border border-white/15 bg-white/5 px-3.5 py-2 text-xs font-black text-white hover:bg-white/10">Vào Agent</button>
          </nav>
        </header>

        <section className="grid min-h-[calc(100vh-88px)] items-center gap-12 py-14 lg:grid-cols-[1.05fr_0.95fr] lg:py-20" aria-labelledby="landing-title">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-blue-300/20 bg-blue-400/10 px-3 py-1.5 text-[11px] font-black uppercase tracking-[0.16em] text-blue-200"><Radio className="h-3.5 w-3.5 animate-pulse motion-reduce:animate-none" /> One brief · one canonical campaign</div>
            <h1 id="landing-title" className="mt-6 max-w-4xl text-5xl font-black leading-[0.96] tracking-[-0.06em] sm:text-7xl lg:text-[82px]">
              Từ ý tưởng đến<br /><span className="landing-gradient-text">campaign sống động.</span>
            </h1>
            <p className="mt-7 max-w-2xl text-base leading-8 text-slate-400 sm:text-lg">Advertising Agent kết nối chiến lược, audience, creative, media, launch và reporting trong một workspace AI duy nhất — để đội ngũ đi nhanh hơn mà không đánh đổi quyền kiểm soát.</p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
              <button type="button" onClick={onEnterAgent} className="landing-primary-cta">Bắt đầu với Agent <ArrowRight className="h-4 w-4" /></button>
              <button type="button" onClick={() => onOpenDemo('copilot')} className="landing-secondary-cta"><Play className="h-4 w-4" /> Xem Copilot demo</button>
              <button type="button" onClick={() => onOpenDemo('autopilot')} className="landing-secondary-cta"><Sparkles className="h-4 w-4" /> Xem Autopilot demo</button>
              <a href="/tech-docs.html" className="landing-secondary-cta sm:hidden"><FileText className="h-4 w-4" /> Tài liệu kỹ thuật</a>
            </div>
            <div className="mt-7 flex flex-wrap gap-x-5 gap-y-2 text-[11px] font-bold text-slate-500">
              <span className="flex items-center gap-1.5"><CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /> Dùng ẩn danh ngay</span>
              <span className="flex items-center gap-1.5"><ShieldCheck className="h-3.5 w-3.5 text-emerald-400" /> Human launch gate</span>
              <span className="flex items-center gap-1.5"><Gauge className="h-3.5 w-3.5 text-emerald-400" /> Durable & observable</span>
            </div>
          </div>

          <div className="relative mx-auto w-full max-w-xl">
            <div className="landing-console relative overflow-hidden rounded-[32px] border border-white/10 bg-white/[0.045] p-4 shadow-2xl backdrop-blur-xl sm:p-6">
              <div className="flex items-center gap-2 border-b border-white/10 pb-4 text-[10px] font-black uppercase tracking-[0.16em] text-slate-500"><span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_15px_rgba(52,211,153,.8)]" /> Campaign system online <span className="ml-auto text-blue-300">Plan v2</span></div>
              <div className="mt-5 space-y-3">
                {['Strategy & budget simulation', 'Audience RAG · 310 grounded segments', 'Creative Intelligence · VLM review', 'Placement compatibility & order guard'].map((item, index) => (
                  <div key={item} className="landing-pipeline-row" style={{ animationDelay: `${index * 140}ms` }}>
                    <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-500/10 text-xs font-black text-blue-300">0{index + 1}</span>
                    <div className="min-w-0 flex-1"><p className="truncate text-xs font-bold text-slate-200">{item}</p><div className="mt-2 h-1 overflow-hidden rounded-full bg-slate-800"><div className="landing-progress h-full rounded-full bg-gradient-to-r from-blue-500 to-cyan-300" style={{ width: `${76 + index * 6}%`, animationDelay: `${index * 180}ms` }} /></div></div>
                    <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                  </div>
                ))}
              </div>
              <div className="mt-4 grid grid-cols-3 gap-2">
                {['COPILOT', 'AUTOPILOT', 'ZALO'].map((item, index) => <div key={item} className={`rounded-xl border p-3 text-center text-[10px] font-black tracking-wider ${index === 1 ? 'border-blue-400/30 bg-blue-400/10 text-blue-200' : 'border-white/10 bg-white/[0.03] text-slate-500'}`}>{item}</div>)}
              </div>
              <div className="absolute -right-10 top-16 h-32 w-32 rounded-full bg-blue-500/20 blur-3xl" />
            </div>
            <div className="absolute -bottom-7 -left-4 flex items-center gap-3 rounded-2xl border border-emerald-300/15 bg-[#081426]/90 px-4 py-3 shadow-xl backdrop-blur-lg sm:-left-8"><ShieldCheck className="h-5 w-5 text-emerald-300" /><div><p className="text-[10px] font-black uppercase tracking-widest text-emerald-300">Safety boundary</p><p className="text-xs font-bold text-slate-200">Launch chỉ sau khi bạn duyệt</p></div></div>
          </div>
        </section>

        <section className="border-t border-white/10 py-20" aria-labelledby="capabilities-title">
          <p className="text-xs font-black uppercase tracking-[0.2em] text-blue-300">One connected experience</p>
          <h2 id="capabilities-title" className="mt-3 max-w-3xl text-3xl font-black tracking-tight sm:text-5xl">AI không chỉ trả lời. AI cùng bạn vận hành campaign.</h2>
          <div className="mt-10 grid gap-4 lg:grid-cols-3">
            {capabilities.map(([title, description, Icon]) => <article key={title} className="rounded-3xl border border-white/10 bg-white/[0.035] p-6 transition hover:-translate-y-1 hover:border-blue-300/25 hover:bg-white/[0.055] motion-reduce:transform-none"><Icon className="h-7 w-7 text-blue-300" /><h3 className="mt-6 text-xl font-black">{title}</h3><p className="mt-3 text-sm leading-7 text-slate-400">{description}</p></article>)}
          </div>
        </section>

        <section className="grid gap-4 border-y border-white/10 py-12 sm:grid-cols-2 lg:grid-cols-4" aria-label="Điểm nổi bật kiến trúc">
          {reliability.map(([value, label]) => <div key={label} className="rounded-2xl border border-white/10 bg-white/[0.03] p-5"><p className="text-4xl font-black tracking-tight text-white">{value}<span className="text-blue-300">+</span></p><p className="mt-2 text-xs leading-5 text-slate-500">{label}</p></div>)}
        </section>

        <section className="py-20 text-center">
          <Zap className="mx-auto h-8 w-8 text-blue-300" />
          <h2 className="mx-auto mt-5 max-w-3xl text-3xl font-black tracking-tight sm:text-5xl">Một campaign tốt bắt đầu bằng một quyết định rõ ràng.</h2>
          <p className="mx-auto mt-4 max-w-xl text-sm leading-7 text-slate-500">Chọn Copilot để cùng AI dẫn dắt từng chặng, hoặc Autopilot để quan sát một kế hoạch bền vững tự thực thi trong giới hạn bạn đặt ra.</p>
          <button type="button" onClick={onEnterAgent} className="landing-primary-cta mt-8">Vào Advertising Agent <ArrowRight className="h-4 w-4" /></button>
        </section>
      </div>
    </main>
  )
}
