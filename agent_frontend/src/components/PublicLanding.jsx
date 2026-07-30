import {
  AlertTriangle, ArrowDown, ArrowRight, ArrowUpRight, Brain,
  Check, Clock3, FileText, Image, Layers3, MessageCircle, MousePointer2,
  Menu, Play, Radar, Route, ShieldCheck, Sparkles, Target, TrendingUp, X,
} from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'

import mascotImageUrl from '../../public/brand/advertising-agent-mascot.png'

const ecosystemLinks = [
  { label: 'Ad Server', href: 'https://adspilot.pawgrammers.io.vn' },
  { label: 'Analytics', href: 'https://analytics.pawgrammers.io.vn' },
]

const orbitNodes = [
  { label: 'Audience', meta: 'Intent matched', icon: Radar, className: 'campaign-node-a' },
  { label: 'Creative', meta: 'Quality reviewed', icon: Image, className: 'campaign-node-b' },
  { label: 'Placement', meta: 'Inventory fit', icon: Target, className: 'campaign-node-c' },
  { label: 'Report', meta: 'Decision ready', icon: TrendingUp, className: 'campaign-node-d' },
]

const painPoints = [
  {
    id: 'tools',
    icon: Layers3,
    title: 'Quá nhiều công việc cho một campaign',
    solution: 'Chỉ cần gửi brief, Advertising Agent tự bóc tách mục tiêu, chuẩn hóa yêu cầu và dựng toàn bộ campaign setup.',
  },
  {
    id: 'experience',
    icon: Brain,
    title: 'Tối ưu phụ thuộc vào kinh nghiệm cá nhân',
    solution: 'Agent chấm điểm ad zone theo mục tiêu, giá, reach và format fit. Knowledge RAG truy xuất dữ liệu campaign trước đó để đề xuất tối ưu dựa trên bằng chứng, không chỉ cảm tính.',
  },
  {
    id: 'error',
    icon: AlertTriangle,
    title: 'Một sai lệch nhỏ kéo hỏng cả campaign',
    solution: 'Mọi rủi ro được gắn cờ ở review gate để Operator duyệt trước khi launch. Agent kiểm tra chéo budget, bid, targeting, schedule, ad format trong suốt quá trình setup.',
  },
  {
    id: 'slow',
    icon: Clock3,
    title: 'Phản ứng chậm khi hiệu suất có vấn đề',
    solution: 'Agent phân tích performance theo good / watch / bad, tạo cảnh báo hành động và soạn sẵn email update cho Account, Sales hoặc Marketing Manager.',
  },
]

const personas = [
  {
    image: '/landing/personas/card-marketer-scene.png',
    width: 1255,
    height: 941,
    eyebrow: 'Marketer & Ad Operations',
    title: 'Đêm canh launch campaign, ngày nghỉ vẫn sửa setup.',
    text: 'Advertising Agent giúp họ giảm thao tác lặp lại, chuẩn hóa quy trình setup và phát hiện lỗi trước khi campaign bắt đầu tiêu ngân sách thật.',
  },
  {
    image: '/landing/personas/card-sales-scene.png',
    width: 1255,
    height: 941,
    eyebrow: 'Account & Sales',
    title: 'Khách gọi hỏi vì sao performance rớt, report thì chưa kịp có.',
    text: 'Thay vì chờ team vận hành tổng hợp thủ công, Advertising Agent phân tích hiệu suất, tóm tắt vấn đề, gợi ý hành động và soạn sẵn email update để Sales phản hồi client chủ động hơn.',
  },
  {
    image: '/landing/personas/card-manager-scene2.png',
    width: 1000,
    height: 750,
    eyebrow: 'Marketing Manager',
    title: 'Báo cáo đỏ lòm mà vẫn chưa tìm được nguyên nhân.',
    text: 'Nhanh chóng xác định campaign nào đang hoạt động tốt, campaign nào cần theo dõi và campaign nào cần được can thiệp giúp manager ra quyết định nhanh hơn.',
  },
]

const workflowSteps = [
  ['01', 'Strategy', 'Biến brief thành chiến lược', 'Agent chuẩn hóa mục tiêu, KPI, ngân sách và thời gian chạy thành một campaign plan rõ ràng.', 'Reframed'],
  ['02', 'Audience', 'Tìm đúng audience', 'Agent map yêu cầu trong brief với DMP catalog, đánh giá độ phù hợp và phát hiện khoảng trống targeting.', 'Re-ranked'],
  ['03', 'Creative', 'Kiểm tra creative', 'Creative được đối chiếu về format, kích thước, nội dung và mức độ phù hợp với mục tiêu campaign.', 'Re-checked'],
  ['04', 'Placement', 'Chọn đúng ad zone', 'Agent chấm điểm placement theo objective, CPM, reach, inventory và creative fit để đề xuất phương án phù hợp.', 'Re-scored'],
  ['05', 'Budget & Bid', 'Phân bổ ngân sách', 'Budget được chia theo từng ad zone; bid được tính dựa trên mục tiêu, inventory và giới hạn tổng chi tiêu.', 'Re-allocated'],
  ['06', 'Performance', 'Theo dõi và đề xuất hành động', 'Sau launch, Agent phân loại hiệu suất theo Good, Watch và Bad, chỉ ra vấn đề và đề xuất bước xử lý tiếp theo.', 'Re-evaluated'],
]

const modes = [
  {
    number: '01',
    title: 'Campaign Copilot',
    icon: MousePointer2,
    mode: 'copilot',
    eyebrow: 'You decide · Agent assists',
    tour: 'Bắt đầu tour Copilot',
    text: 'Dành cho brief còn đang mở. Bạn hỏi, chỉnh, so sánh từng quyết định; Agent biến mỗi ý tưởng thành audience, creative, placement và lý do chọn ngay trên canvas.',
  },
  {
    number: '02',
    title: 'Campaign Autopilot',
    icon: Sparkles,
    mode: 'autopilot',
    eyebrow: 'Goal in · Campaign plan out',
    tour: 'Bắt đầu tour Autopilot',
    text: 'Dành cho brief đã rõ. Bạn giao mục tiêu, KPI, ngân sách và guardrail; Agent tự dựng plan, tự kiểm tra rủi ro, rồi dừng ở review gate để bạn quyết.',
  },
]

const technologies = [
  {
    number: '01', layer: 'LỚP NGƯỜI DÙNG', title: 'Dual-Surface Experience', art: 'surfaces',
    text: 'Chat để trao đổi và làm rõ, Workspace để soi kế hoạch và bằng chứng. Hai bề mặt, một trạng thái campaign — bạn vẫn là người duyệt.',
  },
  {
    number: '02', layer: 'ENGINE', title: 'Hybrid Agent Orchestration', art: 'orchestration',
    text: 'Copilot chạy trên LangGraph; Autopilot chạy theo state machine 18 task. Mỗi task có worker sở hữu, có lease, retry và cơ chế phục hồi.',
  },
  {
    number: '03', layer: 'ENGINE', title: 'Grounded Recommendation Intelligence', art: 'grounded',
    text: 'Tri thức nội bộ và ngữ cảnh campaign được truy xuất, chấm điểm và đối chiếu độ phù hợp trước khi thành đề xuất audience, placement, creative.',
  },
  {
    number: '04', layer: 'ENGINE', title: 'Durable Agent Runtime', art: 'runtime',
    text: 'Workflow chạy dài vẫn giữ được trạng thái: checkpoint, pause & resume, retry, và chỉnh sửa của người dùng đều được ghi lại để xem lại.',
  },
  {
    number: '05', layer: 'KẾT QUẢ', title: 'Creative Intelligence', art: 'creative',
    text: 'Từ brief hoặc một câu prompt, Agent dựng concept banner theo nhiều định dạng đặt sẵn để bạn review trước khi đưa vào campaign.',
  },
  {
    number: '06', layer: 'KẾT QUẢ', title: 'Campaign Visibility, Reports & Zalo Continuity', art: 'reports',
    text: 'Campaign Result, Setup Report, bằng chứng screenshot và 6 góc nhìn báo cáo. Zalo OA đọc cùng một trạng thái campaign với web workspace.',
  },
]

function useStandaloneReveal() {
  const ref = useRef(null)
  useEffect(() => {
    const node = ref.current
    if (!node || node.closest('.public-landing-v3')) return
    node.querySelectorAll('[data-scroll-reveal]').forEach(element => element.classList.add('is-visible'))
  }, [])
  return ref
}

function ChapterHeader({ number, title, subtitle, trailing, light = false }) {
  return (
    <div className={`v3-chapter${light ? ' is-light landing-manifesto-chapter' : ''}`} data-chapter>
      <span>{number}</span>
      <div>
        <b>{title}</b>
        {subtitle && <small>{subtitle}</small>}
      </div>
      <i aria-hidden="true" />
      {trailing}
    </div>
  )
}

function CampaignConstellation() {
  return (
    <div className="campaign-stage" role="img" aria-label="Advertising Agent kết nối audience, creative, placement và report">
      <div className="campaign-stage-grid" />
      <div className="campaign-signal campaign-signal-one" />
      <div className="campaign-signal campaign-signal-two" />
      <div className="campaign-orbit campaign-orbit-outer" />
      <div className="campaign-orbit campaign-orbit-inner" />
      <div className="campaign-agent-core">
        <div className="campaign-agent-aura" />
        <img src={mascotImageUrl} alt="" width="720" height="1014" decoding="async" />
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
        <div className="campaign-ad-product" /><span>CREATIVE 04</span>
      </div>
      <div className="campaign-chat-bubble"><MessageCircle /><span>Launch chỉ sau khi<br /><b>bạn duyệt</b></span></div>
      <div className="campaign-cursor"><MousePointer2 /></div>
    </div>
  )
}

function PainVisual({ type }) {
  if (type === 'tools') {
    return (
      <div className="v3-pain-art v3-pain-tools" aria-hidden="true">
        <div className="v3-art-inner">
          <div className="v3-file-row"><FileText /><span><b>Client brief</b><small>.docx</small></span><Check /></div>
          <ArrowDown className="v3-art-arrow" />
          <div className="v3-agent-pill"><Sparkles /> AD AGENT</div>
          <div className="v3-chip-grid">{['Audience', 'Ad Zone', 'Creative', 'Budget', 'Tracking', 'Report'].map(item => <span key={item}>{item}</span>)}</div>
        </div>
      </div>
    )
  }
  if (type === 'experience') {
    const rows = [['Zone A', 91], ['Zone B', 72], ['Zone C', 58]]
    return (
      <div className="v3-pain-art v3-pain-experience" aria-hidden="true">
        <div className="v3-art-inner">
          <div className="v3-score-head"><span>Ad zone</span><span>O R C F</span><b>Pt</b></div>
          {rows.map(([zone, score], index) => (
            <div className={`v3-score-row${index === 0 ? ' is-best' : ''}`} key={zone}>
              <span>{zone}</span><i><em style={{ width: `${score}%` }} /></i><b>{score}</b>
            </div>
          ))}
          <div className="v3-rag-chip"><Brain /> KNOWLEDGE RAG</div>
        </div>
      </div>
    )
  }
  if (type === 'error') {
    const checks = [['Budget & bid', 'bad'], ['Targeting', 'good'], ['Schedule', 'watch'], ['Naming / tracking', 'good']]
    return (
      <div className="v3-pain-art v3-pain-error" aria-hidden="true">
        <div className="v3-art-inner">
          <div className="v3-qa-title"><ShieldCheck /> Launch QA <small>4 checks</small></div>
          {checks.map(([label, state]) => <div className={`v3-qa-row is-${state}`} key={label}><span>{label}</span><i>{state === 'bad' ? '!' : state === 'watch' ? '•' : '✓'}</i></div>)}
          <div className="v3-review-bar">REVIEW GATE · OPERATOR</div>
        </div>
      </div>
    )
  }
  return (
    <div className="v3-pain-art v3-pain-slow" aria-hidden="true">
      <div className="v3-art-inner">
        <div className="v3-status-chips"><span>GOOD 12</span><span>WATCH 03</span><span>BAD 01</span></div>
        <div className="v3-mini-chart">{[34, 52, 46, 68, 40, 24, 30].map((height, index) => <i key={index} className={index === 5 ? 'is-bad' : index === 4 ? 'is-watch' : ''} style={{ height: `${height}%` }} />)}</div>
        <div className="v3-email-row"><MessageCircle /><span><b>Update email</b><small>Account & client</small></span><em>READY</em></div>
      </div>
    </div>
  )
}

function CampaignTruthVisual() {
  return (
    <div className="truth-visual v3-truth-visual" aria-label="Sáu bước campaign phản ứng cùng một dòng tín hiệu">
      <div className="truth-noise" aria-hidden="true" />
      <div className="truth-change-card">
        <span><Route /></span>
        <div><small>BRIEF SIGNAL CHANGED</small><b>Objective → Conversion</b></div>
        <i>LIVE</i>
      </div>
      <div className="truth-flow">
        {workflowSteps.map(([number, name, , , state], index) => (
          <div key={number} className="truth-flow-node" style={{ '--truth-index': index }}>
            <small>{number}</small><b>{name}</b><span>{state}</span><Check />
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
          <p>Launch a summer campaign</p><p>Let’s sharpen the audience first.</p>
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
        {[['Brief', 'Normalized'], ['Plan', 'Building'], ['Assets', 'Checking'], ['Forecast', 'Ready']].map(([label, state], index) => (
          <div key={label} className="autopilot-run-node" style={{ '--run-index': index }}><span>{index + 1}</span><b>{label}</b><small>{state}</small></div>
        ))}
      </div>
      <div className="autopilot-approval-gate"><ShieldCheck /><span><small>FINAL CONTROL POINT</small><b>Waiting for your approval</b></span></div>
      <div className="mode-visual-caption"><i /> AGENT BUILDS <span /> YOU APPROVE</div>
    </div>
  )
}

function TechArtwork({ type }) {
  if (type === 'surfaces') {
    return (
      <div className="v3-tech-art is-surfaces" data-tech-art aria-hidden="true">
        <div className="v3-surface-card is-chat"><small>CHAT</small><b>Làm rõ brief</b><span /><span /><em>Agent is thinking…</em></div>
        <div className="v3-surface-card is-workspace"><small>WORKSPACE</small><b>Campaign plan</b><div>{[1, 2, 3, 4, 5].map(value => <i key={value} className={value < 4 ? 'is-done' : ''} />)}</div><em>Cần bạn review</em></div>
        <div className="v3-shared-state">MỘT TRẠNG THÁI CAMPAIGN</div>
      </div>
    )
  }
  if (type === 'orchestration') {
    return (
      <div className="v3-tech-art is-orchestration" data-tech-art aria-hidden="true">
        <div className="v3-engine-panel"><small>COPILOT · LANGGRAPH</small><div className="v3-graph-nodes">{[1, 2, 3, 4].map(value => <i key={value}>{value}</i>)}</div></div>
        <div className="v3-engine-panel is-auto"><small>AUTOPILOT · STATE MACHINE</small><b>18 TASK · 7/18</b><div className="v3-task-strip">{Array.from({ length: 18 }, (_, index) => <i key={index} className={index < 6 ? 'is-done' : index === 6 ? 'is-live' : ''} />)}</div><p><span>lease</span><span>retry 1/3</span><span>recovered</span></p></div>
      </div>
    )
  }
  if (type === 'grounded') {
    return (
      <div className="v3-tech-art is-grounded" data-tech-art aria-hidden="true">
        <div className="v3-knowledge-stack"><span>TRI THỨC & NGỮ CẢNH</span><span>RETRIEVAL</span><span>CAMPAIGN MEMORY</span></div>
        <div className="v3-scoring-node"><Check /> SCORING & COMPATIBILITY</div>
        <div className="v3-output-list">{['Audience', 'Placement', 'Creative'].map((label, index) => <div key={label}><span>{label}</span><i><em style={{ width: `${88 - index * 13}%` }} /></i><b>{93 - index * 7}</b></div>)}</div>
        <small>KÈM BẰNG CHỨNG ĐỂ ĐỐI CHIẾU</small>
      </div>
    )
  }
  if (type === 'runtime') {
    return (
      <div className="v3-tech-art is-runtime" data-tech-art aria-hidden="true">
        <div className="v3-runtime-head"><small>CAMPAIGN STATE · TIMELINE</small><b>state v3 · đã lưu</b></div>
        <div className="v3-timeline"><span /><i /><span /><i /><em>PAUSED</em><span /><b>RESUME</b><i className="is-end" /></div>
        <div className="v3-runtime-chips"><span>Retry</span><span>Recovery</span><span>Người dùng chỉnh sửa</span></div>
      </div>
    )
  }
  if (type === 'creative') {
    return (
      <div className="v3-tech-art is-creative" data-tech-art aria-hidden="true">
        <div className="v3-prompt-card"><small>BRIEF / PROMPT</small><span /><span /><span /></div>
        <ArrowRight />
        <div className="v3-creative-stack"><i /><i /><i /><em>CHỜ DUYỆT</em></div>
        <div className="v3-review-chip"><Check /> REVIEW TRƯỚC KHI DÙNG</div>
      </div>
    )
  }
  return (
    <div className="v3-tech-art is-reports" data-tech-art aria-hidden="true">
      <div className="v3-report-card"><small>CAMPAIGN RESULT <em>Setup report</em></small><svg viewBox="0 0 254 34" preserveAspectRatio="none"><path d="M0 27 C 30 24, 46 9, 78 13 C 108 17, 126 5, 156 8 C 188 11, 210 3, 254 6" /></svg><div>{['Daily Ops', 'Awareness', 'Consideration', 'Conversion', 'Retention', 'Executive'].map(item => <span key={item} className={item === 'Executive' ? 'is-active' : ''}>{item}</span>)}</div></div>
      <div className="v3-evidence-card"><small>evidence</small><span /><span /><i /></div>
      <div className="v3-zalo-tile">Zalo<small>KÊNH TÙY CHỌN</small></div>
      <em>cùng một campaign state</em>
    </div>
  )
}

export function LandingNav({ onEnterAgent, links = ecosystemLinks }) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const headerRef = useRef(null)
  const menuButtonRef = useRef(null)

  const closeMobileMenu = useCallback(() => setMobileMenuOpen(false), [])

  useEffect(() => {
    if (!mobileMenuOpen) return undefined

    const closeOnOutsidePress = event => {
      if (!headerRef.current?.contains(event.target)) closeMobileMenu()
    }
    const closeOnEscape = event => {
      if (event.key !== 'Escape') return
      closeMobileMenu()
      menuButtonRef.current?.focus()
    }
    const closeOnFocusOutside = event => {
      if (!headerRef.current?.contains(event.target)) closeMobileMenu()
    }
    const closeOnDesktop = event => {
      if (!event.matches) closeMobileMenu()
    }
    const mobileQuery = window.matchMedia('(max-width: 700px)')

    document.addEventListener('pointerdown', closeOnOutsidePress)
    document.addEventListener('keydown', closeOnEscape)
    document.addEventListener('focusin', closeOnFocusOutside)
    mobileQuery.addEventListener('change', closeOnDesktop)
    return () => {
      document.removeEventListener('pointerdown', closeOnOutsidePress)
      document.removeEventListener('keydown', closeOnEscape)
      document.removeEventListener('focusin', closeOnFocusOutside)
      mobileQuery.removeEventListener('change', closeOnDesktop)
    }
  }, [closeMobileMenu, mobileMenuOpen])

  const enterAgent = useCallback(() => {
    closeMobileMenu()
    onEnterAgent()
  }, [closeMobileMenu, onEnterAgent])

  return (
    <header ref={headerRef} className="landing-nav" data-mobile-menu-open={mobileMenuOpen ? 'true' : 'false'}>
      <a href="#landing-main" className="landing-brand" aria-label="Advertising Agent" onClick={closeMobileMenu}>
        <span><img src={mascotImageUrl} alt="" width="720" height="1014" /></span>
        <div><b>ADVERTISING AGENT</b><small><i /> Agentic Campaign Operation System</small></div>
      </a>
      <nav aria-label="Điều hướng hệ sinh thái">
        <div className="landing-desktop-nav-links">
          {links.map(({ label, href }, index) => <a key={label} href={href} data-ecosystem-index={index}><span>{label}</span></a>)}
          <a href="/tech-docs.html"><FileText /> <span>Tài liệu</span></a>
        </div>
        <button
          ref={menuButtonRef}
          type="button"
          className="landing-menu-toggle"
          aria-label={mobileMenuOpen ? 'Đóng menu điều hướng' : 'Mở menu điều hướng'}
          aria-controls="landing-mobile-menu"
          aria-expanded={mobileMenuOpen}
          onClick={() => setMobileMenuOpen(open => !open)}
        >
          {mobileMenuOpen ? <X /> : <Menu />}
        </button>
        <div
          id="landing-mobile-menu"
          className="landing-mobile-nav-panel"
          role="group"
          aria-label="Điều hướng trên thiết bị di động"
          hidden={!mobileMenuOpen}
        >
          {links.map(({ label, href }) => (
            <a key={label} href={href} onClick={closeMobileMenu}><span>{label}</span><ArrowUpRight /></a>
          ))}
          <a href="/tech-docs.html" onClick={closeMobileMenu}><span>Tài liệu</span><FileText /></a>
        </div>
        <button type="button" className="landing-agent-cta" onClick={enterAgent}>Vào Agent <ArrowRight /></button>
      </nav>
    </header>
  )
}

export function LandingHero({ onEnterAgent, onOpenDemo, title }) {
  return (
    <section className="landing-hero-v2" aria-labelledby="landing-title">
      <div className="landing-hero-copy">
        <div className="landing-kicker"><span /> Trợ lý AI vận hành campaign <i>LIVE</i></div>
        <h1 id="landing-title">{title ?? <>Make your<br /><em>campaign move.</em></>}</h1>
        <p>Advertising Agent giúp Marketer và Ad Operations biến một business brief thành campaign có thể vận hành — từ phân tích ad strategy, chọn audience, tạo creative, đề xuất placement, phân tích report. Tất cả All-In-One.</p>
        <div className="landing-hero-actions">
          <button type="button" className="landing-cta-solid" onClick={onEnterAgent}>Tạo campaign đầu tiên <ArrowRight /></button>
          <button type="button" className="landing-cta-ghost" onClick={() => onOpenDemo('copilot')}><Play /> Xem bản hướng dẫn</button>
        </div>
        <div className="landing-trust-line">
          <span><ShieldCheck /> Human approval required</span>
          <span><Radar /> Smart audience and placement</span>
          <span><AlertTriangle /> Campaign issue alerts</span>
        </div>
      </div>
      <CampaignConstellation />
      <div className="landing-scroll-cue"><span>SCROLL TO EXPLORE</span><i /></div>
    </section>
  )
}

export function LandingPain() {
  const sectionRef = useStandaloneReveal()
  return (
    <section ref={sectionRef} className="landing-pain-section v3-pain-section" aria-labelledby="pain-title" data-section="01">
      <ChapterHeader
        light
        number="01"
        title={<><em>WHAT PROBLEMS</em> DOES ADVERTISING AGENT SOLVE?</>}
        subtitle="THE OPERATIONAL BOTTLENECK"
        trailing={<em className="v3-chapter-pill"><span className="v3-chapter-pill-muted">PAIN POINTS</span> <ArrowRight /> AGENT SOLUTIONS</em>}
      />
      <div className="landing-pain-heading scroll-reveal" data-scroll-reveal>
        <h2 id="pain-title">Quá trình setup campaign vẫn nặng tính <em>thủ công và lặp lại.</em></h2>
      </div>
      <div className="landing-pain-grid" data-pain-carousel>
        {painPoints.map(({ id, icon: Icon, title, solution }, index) => (
          <article key={id} className="landing-pain-card scroll-reveal" data-scroll-reveal data-pain-card={id} style={{ '--reveal-delay': `${index * 90}ms` }}>
            <span><Icon /></span>
            <h3>{title}</h3>
            <PainVisual type={id} />
            <div className="v3-solution-box"><small><Check /> AGENT SOLUTION</small><p>{solution}</p></div>
          </article>
        ))}
      </div>
    </section>
  )
}

export function LandingAudience() {
  const sectionRef = useStandaloneReveal()
  return (
    <section ref={sectionRef} className="v3-who-section" aria-labelledby="who-title" data-section="02">
      <div className="v3-section-inner is-narrow">
        <ChapterHeader number="02" title="WHO ADVERTISING AGENT HELPS" trailing={<em className="v3-chapter-pill is-dark"><i /> USER TARGETING</em>} />
        <h2 id="who-title">Advertising Agent giúp mọi đội ngũ đứng sau chiến dịch <em>bứt tốc.</em></h2>
        <div className="v3-persona-grid" data-who-grid data-persona-carousel>
          {personas.map((persona, index) => (
            <article key={persona.eyebrow} className="v3-persona-card scroll-reveal" data-scroll-reveal style={{ '--reveal-delay': `${index * 100}ms` }}>
              <div className="v3-persona-media"><img src={persona.image} alt="" width={persona.width} height={persona.height} loading={index === 0 ? 'eager' : 'lazy'} decoding="async" /></div>
              <div className="v3-persona-body"><small>{persona.eyebrow}</small><h3>{persona.title}</h3><p>{persona.text}</p></div>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}

export function LandingHowItWorks() {
  const sectionRef = useStandaloneReveal()
  return (
    <section ref={sectionRef} className="landing-manifesto v3-how-section" aria-labelledby="manifesto-title" data-section="03">
      <div className="landing-manifesto-card scroll-reveal" data-scroll-reveal>
        <ChapterHeader
          light
          number="03"
          title={<>HOW THE AGENT WORKS<small className="v3-how-kicker">SÁU BƯỚC - MỘT DÒNG CHẢY DUY NHẤT</small></>}
        />
        <div className="landing-manifesto-copy">
          <h2 id="manifesto-title">Bạn đưa brief và duyệt.<br /><em>Agent lo phần còn lại.</em></h2>
          <ol className="landing-how-steps">
            {workflowSteps.map(([number, name, title, description]) => (
              <li key={number}><b>{number}</b><span><strong>{name} — {title}</strong><small>{description}</small></span></li>
            ))}
          </ol>
        </div>
        <CampaignTruthVisual />
      </div>
    </section>
  )
}

export function LandingModes({ onEnterAgent, onOpenDemo }) {
  const sectionRef = useStandaloneReveal()
  return (
    <section ref={sectionRef} className="landing-mode-section v3-mode-section" aria-labelledby="mode-title" data-section="04">
      <div className="landing-mode-heading scroll-reveal" data-scroll-reveal>
        <div>
          <div className="landing-section-label"><span>04</span> CHOOSE YOUR CONTROL</div>
          <h2 id="mode-title">Bạn chọn cách làm việc.<br /><em>Agent thích ứng theo bạn.</em></h2>
        </div>
      </div>
      <div className="landing-mode-grid">
        {modes.map(({ number, title, icon: Icon, text, mode, tour, eyebrow }) => (
          <article key={mode} className={`landing-mode-card landing-mode-${mode} scroll-reveal`} data-scroll-reveal data-mode={mode}>
            <div className="landing-mode-top"><span>{number} · {eyebrow}</span><Icon /></div>
            <ModeVisual mode={mode} />
            <h3>{title}</h3><p>{text}</p>
            <div className="landing-mode-actions">
              <button type="button" onClick={event => onOpenDemo(mode, event.currentTarget)}><Play /> {tour}</button>
              <button type="button" onClick={() => onEnterAgent(mode)}>Vào workspace <ArrowRight /></button>
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}

export function LandingTechnology() {
  return (
    <section className="v3-tech-section" aria-labelledby="technology-title" data-section="05">
      <div className="v3-section-inner">
        <ChapterHeader
          number="05"
          title="TECHNOLOGY BEHIND THE AGENT"
          subtitle="LỚP NGƯỜI DÙNG · ENGINE · KẾT QUẢ · RANH GIỚI KIỂM SOÁT"
          trailing={<a className="v3-tech-doc-link" href="/tech-docs.html">Đọc tài liệu kỹ thuật <ArrowUpRight /></a>}
        />
        <div className="v3-tech-heading">
          <h2 id="technology-title"><strong>Không phải “AI Chat”.</strong><br />Đây là Campaign Operating System.</h2>
          <p>Bảy năng lực kỹ thuật, hỗ trợ làm việc với nhau từ bề mặt người dùng, qua engine điều phối, đến kết quả campaign tạo thành một Agentic Campaign Operation System.</p>
        </div>
        <div className="v3-tech-row" data-tech-row>
          <div className="v3-tech-line" data-tech-line><i /></div>
          {technologies.slice(0, 3).map(item => <TechnologyItem key={item.number} item={item} />)}
        </div>
        <div className="v3-tech-flowline" data-tech-flowline><span>HÀNH TRÌNH TIẾP TỤC <ArrowDown /></span></div>
        <div className="v3-tech-row" data-tech-row>
          <div className="v3-tech-line" data-tech-line><i /></div>
          {technologies.slice(3).map(item => <TechnologyItem key={item.number} item={item} />)}
        </div>
        <TechnologySafety />
      </div>
    </section>
  )
}

function TechnologyItem({ item }) {
  return (
    <article className="v3-tech-item">
      <TechArtwork type={item.art} />
      <span className="v3-tech-node" data-tech-node />
      <div className="v3-tech-copy"><small>{item.number} · {item.layer}</small><h3>{item.title}</h3><p>{item.text}</p></div>
    </article>
  )
}

function TechnologySafety() {
  const gates = [
    ['CHẶN PROMPT INJECTION', 'Các mẫu tấn công đã định nghĩa bị phát hiện và chặn ngay ở đầu vào.'],
    ['REVIEW GATE BẮT BUỘC', 'Autopilot dừng lại chờ người duyệt trước khi tạo order.'],
    ['MASK PII & CREDENTIAL', <>Các mẫu PII và credential phổ biến được che trước khi ghi log <code>0912•••••</code></>],
  ]
  return (
    <article className="v3-tech-safety" data-tech-safety>
      <span className="v3-safety-tab">RANH GIỚI KIỂM SOÁT</span>
      <div className="v3-safety-intro"><small>07 · SAFETY & PRIVACY</small><h3>Safety & Privacy by Design</h3><p><strong>An toàn và riêng tư được kiểm soát tại từng điểm quan trọng của quy trình — từ dữ liệu đầu vào, bước phê duyệt đến log hệ thống</strong></p></div>
      <div className="v3-safety-flow">
        <div className="v3-safety-path">{['Prompt người dùng', 'Kế hoạch campaign', 'Tạo order', 'Log & trace'].map((label, index) => <span key={label} className={index === 2 ? 'is-live' : ''}>{label}{index < 3 && <i />}</span>)}</div>
        <div className="v3-safety-gates" data-tech-gates>{gates.map(([title, text]) => <div key={title}><b>{title}</b><span>{text}</span></div>)}</div>
      </div>
    </article>
  )
}

// Kept as a named no-op export for design-system consumers. Landing v3 intentionally
// does not render the retired proof block.
export function LandingProof() {
  return null
}

export function LandingFinalCta({ onEnterAgent }) {
  return (
    <section className="landing-final-cta">
      <div className="landing-final-orbit" aria-hidden="true"><span /><span /><span /></div>
      <p>CAMPAIGN TIẾP THEO CỦA BẠN</p>
      <h2><span>Đưa ý tưởng vào</span><em>chuyển động.</em></h2>
      <button type="button" onClick={onEnterAgent}>Tạo campaign đầu tiên <ArrowRight /></button>
    </section>
  )
}

export function LandingFooter({ onEnterAgent }) {
  return (
    <footer className="landing-footer">
      <div className="landing-footer-brand">
        <b>ADVERTISING AGENT</b>
        <span>Advertising Agent là workspace AI cho đội campaign: biến brief thành plan, audience, creative, placement, launch review và report có thể theo dõi. Sản phẩm demo hackathon của team Pawgrammers; dữ liệu báo cáo trong demo là dữ liệu mô phỏng có dán nhãn rõ ràng.</span>
      </div>
      <nav aria-label="Liên kết cuối trang">
        <a href="/tech-docs.html">Tài liệu kỹ thuật</a>
        <button type="button" onClick={onEnterAgent}>Vào Agent</button>
      </nav>
      <small>© 2026 Team Pawgrammers</small>
    </footer>
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
      entries.forEach(entry => {
        if (entry.isIntersecting) entry.target.classList.add('is-visible')
      })
    }, { threshold: 0.12, rootMargin: '-4% 0px -6%' })
    reveals.forEach(element => observer.observe(element))
    const revealFallback = window.setTimeout(() => {
      reveals.forEach(element => element.classList.add('is-visible'))
    }, 1600)
    return () => {
      window.clearTimeout(revealFallback)
      observer.disconnect()
    }
  }, [])

  const enterMode = useCallback(mode => {
    onEnterAgent(mode === 'autopilot' ? 'autopilot' : 'copilot')
  }, [onEnterAgent])

  return (
    <div ref={landingRef} className="public-landing-v3">
      <a className="v3-skip-link" href="#landing-main">Bỏ qua đến nội dung chính</a>
      <div className="public-landing-v2 v3-hero-plane">
        <LandingNav onEnterAgent={onEnterAgent} />
        <LandingHero onEnterAgent={onEnterAgent} onOpenDemo={onOpenDemo} />
      </div>
      <main id="landing-main">
        <LandingPain />
        <LandingAudience />
        <LandingHowItWorks />
        <div id="modes-anchor" className="v3-modes-plane">
          <LandingModes onEnterAgent={enterMode} onOpenDemo={onOpenDemo} />
        </div>
        <LandingTechnology />
        <LandingFinalCta onEnterAgent={onEnterAgent} />
      </main>
      <LandingFooter onEnterAgent={onEnterAgent} />
    </div>
  )
}
