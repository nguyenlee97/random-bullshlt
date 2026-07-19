import { useEffect, useMemo, useReducer } from 'react'
import {
  ArrowLeft, ArrowRight, Bot, Check, FileBarChart, LayoutDashboard,
  MessageCircle, Pause, Play, RefreshCcw, ShieldCheck, SkipForward, Sparkles, X,
} from 'lucide-react'
import { createDemoState, DEMO_JOURNEYS, demoTransition } from '@/demo/demoJourneys'

const surfaceLabels = {
  chat: ['Chat', MessageCircle], workspace: ['Workspace', LayoutDashboard],
  autopilot: ['Autopilot', Sparkles], timeline: ['Timeline', ShieldCheck],
  result: ['Result', Check], reports: ['Reports', FileBarChart], zalo: ['Zalo', MessageCircle],
}

function DemoVisual({ step }) {
  const activeSurface = surfaceLabels[step.surface] || surfaceLabels.workspace
  return (
    <div className="relative min-h-[340px] overflow-hidden rounded-[28px] border border-white/10 bg-[#071225] shadow-2xl sm:min-h-[430px]">
      <div className="flex items-center gap-2 border-b border-white/10 px-4 py-3 text-[11px] font-bold text-slate-500 sm:px-5">
        <span className="h-2.5 w-2.5 rounded-full bg-red-400/80" />
        <span className="h-2.5 w-2.5 rounded-full bg-amber-300/80" />
        <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/80" />
        <span className="ml-auto tracking-[0.16em]">DEMO SANDBOX · NO EXTERNAL ACTIONS</span>
      </div>
      <div className="grid min-h-[295px] grid-cols-1 sm:min-h-[385px] sm:grid-cols-[150px_1fr]">
        <aside className="hidden border-r border-white/10 p-3 sm:block">
          {Object.entries(surfaceLabels).map(([key, [label, Icon]]) => (
            <div key={key} className={`mb-1 flex items-center gap-2 rounded-xl px-3 py-2.5 text-xs font-bold ${key === step.surface ? 'bg-blue-500/15 text-blue-300' : 'text-slate-600'}`}>
              <Icon className="h-3.5 w-3.5" /> {label}
            </div>
          ))}
        </aside>
        <div className="p-4 sm:p-6">
          <div className="mb-5 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-xs font-bold text-blue-300">
              {(() => { const Icon = activeSurface[1]; return <Icon className="h-4 w-4" /> })()}
              {activeSurface[0]}
            </div>
            <span className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2.5 py-1 text-[10px] font-black text-emerald-300">SAFE FIXTURE</span>
          </div>

          {step.chat && (
            <div className="mb-4 max-w-[88%] rounded-2xl rounded-bl-sm border border-blue-400/15 bg-blue-500/10 p-4 text-sm leading-6 text-blue-50">
              <span className="mb-2 flex items-center gap-2 text-[10px] font-black uppercase tracking-wider text-blue-300"><Bot className="h-3.5 w-3.5" /> Conversation</span>
              {step.chat}
            </div>
          )}

          {step.reports ? (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {step.reports.map((report, index) => (
                <div key={report} className="rounded-xl border border-white/10 bg-white/[0.04] p-3">
                  <div className="mb-3 h-1.5 overflow-hidden rounded-full bg-slate-800"><div className="h-full bg-gradient-to-r from-blue-400 to-cyan-300" style={{ width: `${72 + index * 4}%` }} /></div>
                  <p className="text-xs font-bold text-slate-200">{report}</p>
                  <p className="mt-1 text-[10px] text-emerald-300">Ready · synthetic</p>
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-2.5">
              {step.signals?.map((signal, index) => (
                <div key={signal} className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-3.5">
                  <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${index === step.signals.length - 1 ? 'bg-emerald-400/10 text-emerald-300' : 'bg-blue-400/10 text-blue-300'}`}>
                    {index === step.signals.length - 1 ? <ShieldCheck className="h-4 w-4" /> : <Check className="h-4 w-4" />}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-bold text-slate-200">{signal}</p>
                    <div className="mt-1.5 h-1 rounded-full bg-slate-800"><div className="h-full rounded-full bg-gradient-to-r from-blue-500 to-cyan-300" style={{ width: `${68 + index * 11}%` }} /></div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default function ProductDemo({ mode = 'copilot', onClose }) {
  const [state, dispatch] = useReducer(demoTransition, mode, createDemoState)
  const journey = DEMO_JOURNEYS[state.mode]
  const step = journey.steps[state.index]
  const progress = ((state.index + 1) / journey.steps.length) * 100
  const stepKey = useMemo(() => `${state.mode}:${state.index}`, [state.index, state.mode])

  useEffect(() => {
    if (state.paused || state.completed) return undefined
    const timer = window.setTimeout(() => dispatch({ type: 'NEXT' }), 5200)
    return () => window.clearTimeout(timer)
  }, [state.completed, state.paused, stepKey])

  useEffect(() => {
    const onKey = event => {
      if (event.key === 'Escape') onClose()
      if (event.key === 'ArrowRight') dispatch({ type: 'NEXT' })
      if (event.key === 'ArrowLeft') dispatch({ type: 'PREVIOUS' })
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-[200] overflow-y-auto bg-[#020713]/95 p-3 text-white backdrop-blur-xl sm:p-6" role="dialog" aria-modal="true" aria-label={`Demo ${journey.label}`} data-demo-sandbox="true">
      <div className="mx-auto flex min-h-full max-w-7xl flex-col">
        <header className="flex flex-wrap items-center gap-3 py-2">
          <div className="flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-cyan-300 shadow-lg shadow-blue-500/20"><Bot className="h-5 w-5" /></div>
            <div><p className="text-xs font-black uppercase tracking-[0.18em] text-blue-300">Advertising Agent</p><p className="text-xs text-slate-500">Interactive product demo</p></div>
          </div>
          <div className="order-3 flex w-full rounded-xl border border-white/10 bg-white/5 p-1 sm:order-none sm:ml-5 sm:w-auto">
            {Object.entries(DEMO_JOURNEYS).map(([key, item]) => (
              <button key={key} type="button" onClick={() => dispatch({ type: 'SET_MODE', mode: key })} className={`flex-1 rounded-lg px-3 py-2 text-xs font-bold transition sm:flex-none ${state.mode === key ? 'bg-white text-slate-950' : 'text-slate-400 hover:text-white'}`} aria-pressed={state.mode === key}>{item.shortLabel}</button>
            ))}
          </div>
          <button type="button" onClick={onClose} className="ml-auto flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 text-slate-400 hover:bg-white/10 hover:text-white" aria-label="Thoát demo"><X className="h-5 w-5" /></button>
        </header>

        <div className="mt-4 h-1 overflow-hidden rounded-full bg-white/10"><div className="h-full rounded-full bg-gradient-to-r from-blue-500 via-cyan-300 to-emerald-300 transition-all duration-700 motion-reduce:transition-none" style={{ width: `${progress}%` }} /></div>

        <main key={stepKey} className="demo-stage-enter grid flex-1 items-center gap-6 py-7 lg:grid-cols-[0.82fr_1.18fr] lg:gap-10">
          <section>
            <p className="text-xs font-black uppercase tracking-[0.2em] text-blue-300">{step.eyebrow}</p>
            <h1 className="mt-4 text-3xl font-black leading-tight tracking-[-0.04em] text-white sm:text-5xl">{step.title}</h1>
            <p className="mt-5 max-w-xl text-sm leading-7 text-slate-400 sm:text-base">{step.description}</p>
            <div className="mt-7 flex flex-wrap gap-2">
              {step.signals?.map(item => <span key={item} className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-[11px] font-bold text-slate-300">{item}</span>)}
            </div>
          </section>
          <DemoVisual step={step} />
        </main>

        <footer className="sticky bottom-0 flex flex-wrap items-center gap-2 border-t border-white/10 bg-[#020713]/95 py-3 backdrop-blur-xl">
          <p className="mr-auto text-xs font-bold text-slate-500">{state.index + 1} / {journey.steps.length} · {journey.label}</p>
          <button type="button" onClick={() => dispatch({ type: 'RESTART' })} className="demo-control" aria-label="Khởi động lại demo"><RefreshCcw className="h-4 w-4" /><span className="hidden sm:inline">Restart</span></button>
          <button type="button" onClick={() => dispatch({ type: 'SKIP' })} className="demo-control" aria-label="Bỏ qua đến cuối demo"><SkipForward className="h-4 w-4" /><span className="hidden sm:inline">Skip</span></button>
          <button type="button" onClick={() => dispatch({ type: 'TOGGLE_PAUSE' })} className="demo-control" aria-label={state.paused ? 'Tiếp tục demo' : 'Tạm dừng demo'}>{state.paused ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}<span className="hidden sm:inline">{state.paused ? 'Resume' : 'Pause'}</span></button>
          <button type="button" disabled={state.index === 0} onClick={() => dispatch({ type: 'PREVIOUS' })} className="demo-control" aria-label="Bước demo trước"><ArrowLeft className="h-4 w-4" /></button>
          <button type="button" onClick={state.completed ? onClose : () => dispatch({ type: 'NEXT' })} className="inline-flex h-10 items-center gap-2 rounded-xl bg-white px-4 text-xs font-black text-slate-950 hover:bg-blue-100" aria-label={state.completed ? 'Kết thúc demo' : 'Bước demo tiếp theo'}>{state.completed ? 'Khám phá Agent' : 'Tiếp theo'}<ArrowRight className="h-4 w-4" /></button>
        </footer>
      </div>
    </div>
  )
}
