import {
  ArrowRight, Bot, Check, FileText, Image, MessageCircle, MousePointer2,
  Play, Radar, ShieldCheck, Sparkles, Target, TrendingUp,
} from 'lucide-react'

const orbitNodes = [
  { label: 'Audience', meta: '310 segments', icon: Radar, className: 'campaign-node-a' },
  { label: 'Creative', meta: 'VLM reviewed', icon: Image, className: 'campaign-node-b' },
  { label: 'Placement', meta: 'Inventory fit', icon: Target, className: 'campaign-node-c' },
  { label: 'Report', meta: '6 live views', icon: TrendingUp, className: 'campaign-node-d' },
]

const modes = [
  {
    number: '01', title: 'Campaign Copilot', icon: MousePointer2,
    text: 'Bạn dẫn dắt từng quyết định. Agent kết nối brief, audience, creative và media ngay trên một workspace.',
    mode: 'copilot', tour: 'Bắt đầu tour Copilot',
  },
  {
    number: '02', title: 'Campaign Autopilot', icon: Sparkles,
    text: 'Bạn đặt mục tiêu và review policy. Agent vận hành một durable plan, dừng đúng điểm cần con người quyết định.',
    mode: 'autopilot', tour: 'Bắt đầu tour Autopilot',
  },
]

function CampaignConstellation() {
  return (
    <div className="campaign-stage" aria-label="Mô phỏng hệ thống campaign agentic">
      <div className="campaign-stage-grid" />
      <div className="campaign-signal campaign-signal-one" />
      <div className="campaign-signal campaign-signal-two" />
      <div className="campaign-orbit campaign-orbit-outer" />
      <div className="campaign-orbit campaign-orbit-inner" />

      <div className="campaign-core">
        <div className="campaign-core-halo" />
        <div className="campaign-core-mark"><Bot /></div>
        <p>AGENT CORE</p>
        <span>Campaign reasoning live</span>
      </div>

      {orbitNodes.map(({ label, meta, icon: Icon, className }) => (
        <div key={label} className={`campaign-node ${className}`}>
          <span><Icon /></span><div><b>{label}</b><small>{meta}</small></div><Check />
        </div>
      ))}

      <div className="campaign-creative campaign-creative-main">
        <div className="campaign-ad-sky"><span>MOVE<br />THE CITY</span><i /></div>
        <div className="campaign-ad-caption"><b>Urban EV launch</b><span>9:16 · Social video</span></div>
      </div>
      <div className="campaign-creative campaign-creative-side">
        <div className="campaign-ad-product" />
        <span>CREATIVE 04</span>
      </div>
      <div className="campaign-chat-bubble"><MessageCircle /><span>Launch chỉ sau khi<br /><b>bạn duyệt</b></span></div>
      <div className="campaign-cursor"><MousePointer2 /></div>
    </div>
  )
}

export default function PublicLanding({ onEnterAgent, onOpenDemo }) {
  const moveLight = event => {
    const box = event.currentTarget.getBoundingClientRect()
    event.currentTarget.style.setProperty('--pointer-x', `${event.clientX - box.left}px`)
    event.currentTarget.style.setProperty('--pointer-y', `${event.clientY - box.top}px`)
  }

  return (
    <main className="public-landing-v2 h-screen h-[100dvh] overflow-y-auto overflow-x-hidden bg-[#020817] text-white" onPointerMove={moveLight}>
      <div className="landing-pointer-light" aria-hidden="true" />
      <header className="landing-nav">
        <a href="/" className="landing-brand" aria-label="Advertising Agent">
          <span><Bot /></span><div><b>ADVERTISING AGENT</b><small>Agentic campaign system</small></div>
        </a>
        <nav aria-label="Điều hướng công khai">
          <a href="/tech-docs.html"><FileText /> <span>Tài liệu</span></a>
          <button type="button" onClick={onEnterAgent}>Mở Agent <ArrowRight /></button>
        </nav>
      </header>

      <section className="landing-hero-v2" aria-labelledby="landing-title">
        <div className="landing-hero-copy">
          <div className="landing-kicker"><span /> AI campaign operating system <i>LIVE</i></div>
          <h1 id="landing-title">Make your<br /><em>campaign move.</em></h1>
          <p>Biến một brief thành chiến lược, audience, creative, media và báo cáo—trong một hệ thống AI biết lập kế hoạch, biết dừng để hỏi, và luôn để bạn giữ quyền quyết định cuối cùng.</p>
          <div className="landing-hero-actions">
            <button type="button" className="landing-cta-solid" onClick={onEnterAgent}>Bắt đầu campaign <ArrowRight /></button>
            <button type="button" className="landing-cta-ghost" onClick={() => onOpenDemo('copilot')}><Play /> Xem guided tour</button>
          </div>
          <div className="landing-trust-line">
            <span><ShieldCheck /> Human launch gate</span><span><Radar /> Catalog-grounded</span><span><MessageCircle /> Zalo continuity</span>
          </div>
        </div>
        <CampaignConstellation />
        <div className="landing-scroll-cue"><span>SCROLL TO EXPLORE</span><i /></div>
      </section>

      <div className="landing-marquee" aria-hidden="true">
        <div>BRIEF <i /> STRATEGY <i /> AUDIENCE <i /> CREATIVE <i /> MEDIA <i /> LAUNCH <i /> REPORTING <i /> ZALO <i /></div>
        <div>BRIEF <i /> STRATEGY <i /> AUDIENCE <i /> CREATIVE <i /> MEDIA <i /> LAUNCH <i /> REPORTING <i /> ZALO <i /></div>
      </div>

      <section className="landing-manifesto">
        <div className="landing-section-label"><span>02</span> ONE CAMPAIGN TRUTH</div>
        <div className="landing-manifesto-grid">
          <h2>Không phải thêm một chatbot.<br /><em>Một cách mới để campaign thành hình.</em></h2>
          <div>
            <p>Agent nhìn campaign như một hệ thống liên kết. Khi brief đổi, nó biết audience, creative hay placement nào cần tính lại—và phần nào nên giữ nguyên.</p>
            <div className="landing-proof-row"><span><b>310+</b> audience signals</span><span><b>18</b> durable tasks</span><span><b>6</b> report views</span></div>
          </div>
        </div>
      </section>

      <section className="landing-mode-section" aria-labelledby="mode-title">
        <div className="landing-section-label"><span>03</span> CHOOSE YOUR CONTROL</div>
        <h2 id="mode-title">Hai cách làm việc.<br />Cùng một Agent.</h2>
        <div className="landing-mode-grid">
          {modes.map(({ number, title, icon: Icon, text, mode, tour }) => (
            <article key={mode} className={`landing-mode-card landing-mode-${mode}`}>
              <div className="landing-mode-top"><span>{number}</span><Icon /></div>
              <div className="landing-mode-visual">
                <div className="mode-thread"><i /><i /><i /></div>
                <div className="mode-panel"><span /><span /><span /></div>
                <div className="mode-pulse" />
              </div>
              <h3>{title}</h3><p>{text}</p>
              <div className="landing-mode-actions">
                <button type="button" onClick={() => onOpenDemo(mode)}><Play /> {tour}</button>
                <button type="button" onClick={onEnterAgent} aria-label={`Mở ${title}`}><ArrowRight /></button>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-final-cta">
        <div className="landing-final-orbit" aria-hidden="true"><span /><span /><span /></div>
        <p>YOUR NEXT CAMPAIGN</p>
        <h2>Đưa ý tưởng vào chuyển động.</h2>
        <button type="button" onClick={onEnterAgent}>Mở Advertising Agent <ArrowRight /></button>
      </section>
    </main>
  )
}
