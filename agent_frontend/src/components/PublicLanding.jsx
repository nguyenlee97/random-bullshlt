import {
  ArrowRight, ArrowUpRight, Bot, Check, FileText, Image, Layers3,
  MessageCircle, MousePointer2, Play, Radar, Route, ShieldCheck,
  Sparkles, Target, TrendingUp,
} from 'lucide-react'
import { useEffect, useRef } from 'react'

const orbitNodes = [
  { label: 'Audience', meta: 'Intent matched', icon: Radar, className: 'campaign-node-a' },
  { label: 'Creative', meta: 'VLM reviewed', icon: Image, className: 'campaign-node-b' },
  { label: 'Placement', meta: 'Inventory fit', icon: Target, className: 'campaign-node-c' },
  { label: 'Report', meta: 'Decision ready', icon: TrendingUp, className: 'campaign-node-d' },
]

const signalWords = ['BRIEF', 'STRATEGY', 'AUDIENCE', 'CREATIVE', 'MEDIA', 'LAUNCH', 'REPORTING', 'ZALO']

const modes = [
  {
    number: '01', title: 'Campaign Copilot', icon: MousePointer2,
    text: 'Bạn giữ tay lái. Agent mở rộng từng quyết định, nối ý tưởng với audience, creative và media ngay khi bạn làm việc.',
    mode: 'copilot', tour: 'Bắt đầu tour Copilot', eyebrow: 'Human directs · Agent amplifies',
  },
  {
    number: '02', title: 'Campaign Autopilot', icon: Sparkles,
    text: 'Bạn giao mục tiêu và giới hạn. Agent tự xây dựng campaign theo một plan có thể theo dõi, rồi dừng đúng nơi cần bạn quyết định.',
    mode: 'autopilot', tour: 'Bắt đầu tour Autopilot', eyebrow: 'Goal in · Campaign plan out',
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

function SignalRibbon() {
  return (
    <div className="landing-signal-ribbon" aria-hidden="true">
      <div className="signal-ribbon-beam" />
      <div className="signal-ribbon-track">
        {[0, 1, 2].map(copy => (
          <div key={copy} className="signal-ribbon-sequence">
            {signalWords.map((word, index) => (
              <span key={`${copy}-${word}`} className={index === 0 ? 'is-active' : ''}>
                <small>{String(index + 1).padStart(2, '0')}</small>{word}<ArrowUpRight />
              </span>
            ))}
          </div>
        ))}
      </div>
      <div className="signal-ribbon-caption"><i /> CAMPAIGN SIGNALS MOVING AS ONE <i /></div>
    </div>
  )
}

function CampaignTruthVisual() {
  return (
    <div className="truth-visual" aria-hidden="true">
      <div className="truth-noise" />
      <div className="truth-change-card">
        <span><Route /></span>
        <div><small>BRIEF SIGNAL CHANGED</small><b>Objective → Conversion</b></div>
        <i>LIVE</i>
      </div>
      <div className="truth-flow">
        <div className="truth-flow-line"><span /><span /><span /></div>
        {[
          ['01', 'Strategy', 'Reframed'],
          ['02', 'Audience', 'Re-ranked'],
          ['03', 'Creative', 'Re-checked'],
          ['04', 'Placement', 'Re-scored'],
        ].map(([number, label, state], index) => (
          <div key={label} className="truth-flow-node" style={{ '--truth-index': index }}>
            <small>{number}</small><b>{label}</b><span>{state}</span><Check />
          </div>
        ))}
      </div>
      <div className="truth-review-gate"><ShieldCheck /><span><small>HUMAN GATE PRESERVED</small><b>Nothing launches without you</b></span></div>
    </div>
  )
}

function ModeVisual({ mode }) {
  if (mode === 'copilot') {
    return (
      <div className="landing-mode-visual mode-visual-copilot" aria-hidden="true">
        <div className="copilot-chat-window">
          <div className="mode-window-bar"><i /><i /><i /><span>CHAT</span></div>
          <p>Launch a summer campaign</p>
          <p>Let’s sharpen the audience first.</p>
          <div className="copilot-thinking"><span /><span /><span /></div>
        </div>
        <div className="copilot-workspace-window">
          <div className="mode-window-bar"><i /><i /><i /><span>WORKSPACE</span></div>
          {['Brief', 'Audience', 'Creative'].map((label, index) => (
            <div key={label} className={index === 1 ? 'is-current' : ''}><small>0{index + 1}</small><b>{label}</b><span>{index === 0 ? 'Ready' : index === 1 ? 'In focus' : 'Next'}</span></div>
          ))}
        </div>
        <div className="copilot-control-path"><MousePointer2 /><span /></div>
        <div className="mode-visual-caption"><i /> YOU DIRECT <span /> AGENT AMPLIFIES</div>
      </div>
    )
  }

  return (
    <div className="landing-mode-visual mode-visual-autopilot" aria-hidden="true">
      <div className="autopilot-goal-chip"><Target /><span><small>GOAL RECEIVED</small><b>Grow qualified reach</b></span><Check /></div>
      <div className="autopilot-runway">
        <div className="autopilot-run-line" />
        {[
          ['Brief', 'Normalized'], ['Plan', 'Building'], ['Assets', 'Checking'], ['Forecast', 'Ready'],
        ].map(([label, state], index) => (
          <div key={label} className="autopilot-run-node" style={{ '--run-index': index }}>
            <span>{index + 1}</span><b>{label}</b><small>{state}</small>
          </div>
        ))}
      </div>
      <div className="autopilot-approval-gate"><ShieldCheck /><span><small>FINAL CONTROL POINT</small><b>Waiting for your approval</b></span></div>
      <div className="mode-visual-caption"><i /> AGENT BUILDS <span /> YOU APPROVE</div>
    </div>
  )
}

export default function PublicLanding({ onEnterAgent, onOpenDemo }) {
  const landingRef = useRef(null)

  useEffect(() => {
    const root = landingRef.current
    if (!root) return undefined

    const reveals = [...root.querySelectorAll('[data-scroll-reveal]')]
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reducedMotion || !('IntersectionObserver' in window)) {
      reveals.forEach(element => element.classList.add('is-visible'))
      return undefined
    }

    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => entry.target.classList.toggle('is-visible', entry.isIntersecting))
    }, {
      root,
      threshold: 0.14,
      rootMargin: '-5% 0px -7%',
    })

    reveals.forEach(element => observer.observe(element))
    return () => observer.disconnect()
  }, [])

  const moveLight = event => {
    const box = event.currentTarget.getBoundingClientRect()
    event.currentTarget.style.setProperty('--pointer-x', `${event.clientX - box.left}px`)
    event.currentTarget.style.setProperty('--pointer-y', `${event.clientY - box.top}px`)
  }

  return (
    <main ref={landingRef} className="public-landing-v2 h-screen h-[100dvh] overflow-y-auto overflow-x-hidden bg-[#020817] text-white" onPointerMove={moveLight}>
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

      <SignalRibbon />

      <section className="landing-manifesto" aria-labelledby="manifesto-title">
        <div className="landing-manifesto-card scroll-reveal" data-scroll-reveal>
          <div className="landing-manifesto-chapter">
            <span>02</span>
            <div><small>CONNECTED CAMPAIGN SYSTEM</small><b>ONE CAMPAIGN TRUTH</b></div>
            <i />
            <em>LIVE SIGNAL</em>
          </div>
          <div className="landing-manifesto-copy">
            <p className="landing-manifesto-kicker"><Layers3 /> ONE INTENT. EVERY DECISION CONNECTED.</p>
            <h2 id="manifesto-title">Không phải thêm một chatbot.<br /><em>Một cách mới để campaign thành hình.</em></h2>
            <p>Một thay đổi trong brief không nên biến thành năm lần sửa rời rạc. Agent mang cùng một ý định xuyên suốt chiến lược, audience, creative và placement—đồng thời chỉ rõ điều gì vừa thay đổi và vì sao.</p>
            <div className="landing-manifesto-proof"><span><b>01</b> campaign truth</span><i /><span><b>04</b> linked decisions</span><i /><span><b>YOU</b> keep final control</span></div>
          </div>
          <CampaignTruthVisual />
        </div>
      </section>

      <section className="landing-mode-section" aria-labelledby="mode-title">
        <div className="landing-mode-heading scroll-reveal" data-scroll-reveal>
          <div><div className="landing-section-label"><span>03</span> CHOOSE YOUR CONTROL</div><h2 id="mode-title">Hai cách làm việc.<br /><em>Cùng một Agent.</em></h2></div>
          <p>Chọn Copilot để cùng Agent xây từng quyết định. Chọn Autopilot để giao brief, nhận một bản campaign hoàn chỉnh và duyệt trước khi launch.</p>
        </div>
        <div className="landing-mode-grid">
          {modes.map(({ number, title, icon: Icon, text, mode, tour, eyebrow }) => (
            <article key={mode} className={`landing-mode-card landing-mode-${mode} scroll-reveal`} data-scroll-reveal style={{ '--reveal-delay': `${number === '01' ? 0 : 120}ms` }}>
              <div className="landing-mode-top"><span>{number} · {eyebrow}</span><Icon /></div>
              <ModeVisual mode={mode} />
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
        <h2><span>Đưa ý tưởng vào</span><em>chuyển động.</em></h2>
        <button type="button" onClick={onEnterAgent}>Mở Advertising Agent <ArrowRight /></button>
      </section>
    </main>
  )
}
