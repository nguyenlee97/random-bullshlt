import {
  ArrowRight, ArrowUpRight, Bot, Check, Copy, FileText, Image, Layers3,
  MessageCircle, MousePointer2, Play, Radar, Route, ShieldCheck,
  Sparkles, Target, TrendingUp, TriangleAlert, Unplug,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

const orbitNodes = [
  { label: 'Audience', meta: 'Intent matched', icon: Radar, className: 'campaign-node-a' },
  { label: 'Creative', meta: 'VLM reviewed', icon: Image, className: 'campaign-node-b' },
  { label: 'Placement', meta: 'Inventory fit', icon: Target, className: 'campaign-node-c' },
  { label: 'Report', meta: 'Decision ready', icon: TrendingUp, className: 'campaign-node-d' },
]

const signalWords = ['BRIEF', 'STRATEGY', 'AUDIENCE', 'CREATIVE', 'MEDIA', 'LAUNCH', 'REPORTING', 'ZALO']

// Ba nỗi đau vận hành mà workspace hợp nhất + order guard giải quyết trực tiếp.
const painPoints = [
  {
    icon: Unplug, title: 'Công cụ rời rạc, quy trình chậm',
    text: 'Brief, audience, creative, placement và báo cáo nằm ở năm nơi khác nhau. Mỗi lần đổi brief là một vòng copy-paste lại từ đầu.',
  },
  {
    icon: TriangleAlert, title: 'Sai sót khó phát hiện kịp',
    text: 'Creative lệch kích thước placement, targeting không khớp brief, quyết định dựa trên dữ liệu đã cũ — thường chỉ lộ ra khi campaign đã chạy.',
  },
  {
    icon: Copy, title: 'Launch thiếu kiểm soát',
    text: 'Đặt trùng order, chạy chiến dịch chưa qua duyệt — những lỗi trả giá bằng ngân sách thật và niềm tin của khách hàng.',
  },
]

// Số liệu từ bộ đánh giá nội bộ của dự án (80 golden briefs + test tự động).
const proofStats = [
  { value: '0.819', label: 'Recall@15 gợi ý audience', note: 'trên bộ 80 brief chuẩn' },
  { value: '17', label: 'bước trong một run Autopilot', note: 'mỗi bước kèm bằng chứng' },
  { value: '0', label: 'order trùng lặp', note: 'nhờ khóa idempotency' },
  { value: '100%', label: 'launch qua phê duyệt của bạn', note: 'không có ngoại lệ' },
]

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

      <div className="campaign-agent-core">
        <div className="campaign-agent-aura" />
        <img src="/brand/advertising-agent-mascot.png" alt="Robot đại diện cho Advertising Agent" width="720" height="1014" decoding="async" />
        <div className="campaign-agent-status"><i /> ADVERTISING AGENT <small>ONLINE</small></div>
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

function PainSection() {
  return (
    <section className="landing-pain-section" aria-labelledby="pain-title">
      <div className="landing-pain-heading scroll-reveal" data-scroll-reveal>
        <div className="landing-section-label"><span>01</span> VÌ SAO CẦN AGENT</div>
        <h2 id="pain-title">Chạy một campaign display<br /><em>không nên vất vả thế này.</em></h2>
      </div>
      <div className="landing-pain-grid">
        {painPoints.map(({ icon: Icon, title, text }, index) => (
          <article key={title} className="landing-pain-card scroll-reveal" data-scroll-reveal style={{ '--reveal-delay': `${index * 110}ms` }}>
            <span><Icon /></span>
            <h3>{title}</h3>
            <p>{text}</p>
          </article>
        ))}
      </div>
      <p className="landing-pain-bridge scroll-reveal" data-scroll-reveal>
        Advertising Agent gom tất cả về <b>một workspace duy nhất</b> — nơi AI đề xuất, hệ thống kiểm tra tự động, và bạn là người quyết định.
      </p>
    </section>
  )
}

function ProofSection() {
  return (
    <section className="landing-proof-section" aria-labelledby="proof-title">
      <div className="landing-pain-heading scroll-reveal" data-scroll-reveal>
        <div className="landing-section-label"><span>04</span> BẰNG CHỨNG</div>
        <h2 id="proof-title">Không chỉ là lời hứa.<br /><em>Là hệ thống đã đo được.</em></h2>
      </div>
      <div className="landing-proof-card scroll-reveal" data-scroll-reveal>
        <div className="landing-proof-stats">
          {proofStats.map(({ value, label, note }) => (
            <div key={label}><b>{value}</b><span>{label}</span><small>{note}</small></div>
          ))}
        </div>
        <figure className="landing-proof-shot">
          <img src="/landing/autopilot-strategy.png" alt="Màn hình Campaign Autopilot đang dừng tại điểm duyệt chiến lược" loading="lazy" decoding="async" />
          <figcaption>Màn hình thật: Autopilot dừng lại chờ bạn duyệt chiến lược trước khi đi tiếp.</figcaption>
        </figure>
        <p className="landing-proof-note">
          Số liệu từ bộ đánh giá nội bộ của dự án (80 golden briefs, test tự động) — không phải cam kết hiệu quả quảng cáo.
          <a href="/tech-docs.html">Đọc tài liệu kỹ thuật <ArrowUpRight /></a>
        </p>
      </div>
    </section>
  )
}

export default function PublicLanding({ onEnterAgent, onOpenDemo }) {
  const landingRef = useRef(null)
  const [stickyCta, setStickyCta] = useState(false)

  // Mobile: hiện CTA dính đáy sau khi người dùng cuộn qua hero (CTA hero khuất).
  useEffect(() => {
    const root = landingRef.current
    if (!root) return undefined
    const onScroll = () => setStickyCta(root.scrollTop > window.innerHeight * 0.85)
    root.addEventListener('scroll', onScroll, { passive: true })
    return () => root.removeEventListener('scroll', onScroll)
  }, [])

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
          <span><img src="/brand/advertising-agent-mascot.png" alt="" /></span>
          <div><b>ADVERTISING AGENT</b><small><i /> Agentic campaign system</small></div>
        </a>
        <div className="landing-nav-signal" aria-hidden="true"><span>BRIEF</span><i /><span>CAMPAIGN</span><i /><span>IMPACT</span></div>
        <nav aria-label="Điều hướng công khai">
          <a href="/tech-docs.html"><FileText /> <span>Tài liệu</span></a>
          <button type="button" onClick={onEnterAgent}>Vào Agent <ArrowRight /></button>
        </nav>
      </header>

      <section className="landing-hero-v2" aria-labelledby="landing-title">
        <div className="landing-hero-copy">
          <div className="landing-kicker"><span /> Trợ lý AI vận hành campaign <i>LIVE</i></div>
          <h1 id="landing-title">Một brief.<br /><em>Một campaign<br />hoàn chỉnh.</em></h1>
          <p>Advertising Agent biến brief thành chiến lược, audience, creative, media và báo cáo — một hệ thống AI biết lập kế hoạch, biết dừng lại để hỏi, và luôn để bạn giữ quyền quyết định cuối cùng.</p>
          <div className="landing-hero-actions">
            <button type="button" className="landing-cta-solid" onClick={onEnterAgent}>Tạo campaign đầu tiên <ArrowRight /></button>
            <button type="button" className="landing-cta-ghost" onClick={() => onOpenDemo('copilot')}><Play /> Xem tour 2 phút</button>
          </div>
          <div className="landing-trust-line">
            <span><ShieldCheck /> Không launch khi bạn chưa duyệt</span><span><Radar /> Audience từ catalog DMP thật</span><span><Check /> Retry không tạo order trùng</span>
          </div>
        </div>
        <CampaignConstellation />
        <div className="landing-scroll-cue"><span>SCROLL TO EXPLORE</span><i /></div>
      </section>

      <SignalRibbon />

      <PainSection />

      <section className="landing-manifesto" aria-labelledby="manifesto-title">
        <div className="landing-manifesto-card scroll-reveal" data-scroll-reveal>
          <div className="landing-manifesto-chapter">
            <span>02</span>
            <div><small>CÁCH HOẠT ĐỘNG</small><b>TỪ BRIEF ĐẾN CAMPAIGN SẴN SÀNG</b></div>
            <i />
            <em>LIVE SIGNAL</em>
          </div>
          <div className="landing-manifesto-copy">
            <p className="landing-manifesto-kicker"><Layers3 /> BỐN BƯỚC. MỘT DÒNG CHẢY DUY NHẤT.</p>
            <h2 id="manifesto-title">Bạn đưa brief và duyệt.<br /><em>Agent lo phần còn lại.</em></h2>
            <p>Mọi quyết định nằm trong một workspace có phiên bản: đổi brief là các bước phía sau tự tính lại, và không gì được launch khi chưa qua tay bạn.</p>
            <ol className="landing-how-steps">
              <li><b>01</b><span>Đưa brief: mục tiêu, ngân sách, thời gian chạy</span></li>
              <li><b>02</b><span>Agent xây plan: audience từ catalog DMP, creative được kiểm tra, placement khớp format</span></li>
              <li><b>03</b><span>Bạn duyệt tại các điểm chốt — thay đổi tự lan xuống các bước sau</span></li>
              <li><b>04</b><span>Launch sau phê duyệt cuối cùng, báo cáo sẵn sàng chia sẻ</span></li>
            </ol>
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
                <button type="button" onClick={onEnterAgent}>Vào workspace <ArrowRight /></button>
              </div>
            </article>
          ))}
        </div>
      </section>

      <ProofSection />

      <section className="landing-final-cta">
        <div className="landing-final-orbit" aria-hidden="true"><span /><span /><span /></div>
        <p>CAMPAIGN TIẾP THEO CỦA BẠN</p>
        <h2><span>Đưa ý tưởng vào</span><em>chuyển động.</em></h2>
        <button type="button" onClick={onEnterAgent}>Tạo campaign đầu tiên <ArrowRight /></button>
      </section>

      <footer className="landing-footer">
        <div className="landing-footer-brand">
          <b>ADVERTISING AGENT</b>
          <span>Hệ thống AI lập kế hoạch và vận hành campaign display — sản phẩm demo hackathon của team Pawgrammers. Dữ liệu báo cáo trong demo là dữ liệu mô phỏng có dán nhãn rõ ràng.</span>
        </div>
        <nav aria-label="Liên kết cuối trang">
          <a href="/tech-docs.html">Tài liệu kỹ thuật</a>
          <button type="button" onClick={onEnterAgent}>Vào Agent</button>
        </nav>
        <small>© 2026 Team Pawgrammers</small>
      </footer>

      <div className={`landing-sticky-cta${stickyCta ? ' is-visible' : ''}`} aria-hidden={!stickyCta}>
        <button type="button" onClick={onEnterAgent} tabIndex={stickyCta ? 0 : -1}>Tạo campaign đầu tiên <ArrowRight /></button>
      </div>
    </main>
  )
}
