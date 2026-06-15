import { useState, useCallback, useEffect, useRef } from 'react'
import { useChat } from '@/hooks/useChat'
import TopBar from '@/components/TopBar'
import ChatPane from '@/components/ChatPane'
import WorkspacePane from '@/components/WorkspacePane'

// ─── Steps meta ───────────────────────────────────────────────────────────────
export const STEPS = [
  { id: 'brief',    title: 'Brief',      tool: 'brief_parse',    heroLabel: null },
  { id: 'creative', title: 'Creative',   tool: 'creative_upload',heroLabel: null },
  { id: 'segment',  title: 'Audience',   tool: 'dmp_match',      heroLabel: null },
  { id: 'setup',    title: 'Setup Camp', tool: 'camp_create',    heroLabel: null },
  { id: 'success',  title: 'Kết quả',    tool: 'notify',         heroLabel: null },
  { id: 'report',   title: 'Report',     tool: 'report_extract', heroLabel: null },
  { id: 'email',    title: 'Email',      tool: 'email_send',     heroLabel: null },
]

const initialBrief = {
  brand: '',
  objective: 'awareness',
  kpi: '',
  budget: '',
  startDate: '',
  endDate: '',
  notes: '',
}

// Creative now supports multiple files
const initialCreative = {
  uploaded: false,
  files: [],          // [{ id, name, type, size, dataUrl }]
}

const initialState = {
  brief: initialBrief,
  creative: initialCreative,
  segment: { attrs: [], size: 0 },
  setup: { initialized: false, recoZones: [], selectedZoneIds: [], created: false },
  report: { analyzed: false },
  email: { sent: false },
}

export default function App() {
  const [currentStep, setCurrentStep] = useState(0)
  const [stepStatuses, setStepStatuses] = useState(STEPS.map(() => 'pending'))
  const [formState, setFormState] = useState(initialState)
  const workspaceRef = useRef(null)

  const markStepDone = useCallback((stepIndex) => {
    setStepStatuses(prev => {
      const next = [...prev]
      next[stepIndex] = 'done'
      return next
    })
    // Auto-advance
    if (stepIndex < STEPS.length - 1) {
      setTimeout(() => {
        setCurrentStep(stepIndex + 1)
        workspaceRef.current?.flash?.()
      }, 400)
    }
  }, [])

  const handleAutoSelectAudience = useCallback((matchedSegments, targetingMap = {}) => {
    setFormState(prev => {
      const existing = prev.segment?.attrs || []
      const existingUids = new Set(existing.map(a => a._uid || a.code))
      const toAdd = matchedSegments.filter(a => !existingUids.has(a._uid || a.code))
      const merged = [...existing, ...toAdd]
      const sizes = merged.map(a => a.est_size || 0)
      const size = sizes.filter(s => s > 0).length
        ? (() => {
            const known = sizes.filter(s => s > 0).sort((a, b) => b - a)
            let t = 0; known.forEach((s, i) => { t += s * Math.pow(0.7, i) }); return Math.round(t)
          })()
        : 0
      // Normalize targeting keys: AI may return mixed-case, API expects lowercase
      const normalizedTargeting = {}
      for (const [k, v] of Object.entries(targetingMap)) {
        normalizedTargeting[k.toLowerCase()] = Array.isArray(v) ? v : [v]
      }
      return {
        ...prev,
        segment: {
          ...prev.segment,
          attrs: merged,
          size,
          targeting: { ...(prev.segment?.targeting || {}), ...normalizedTargeting },
        },
      }
    })
  }, [setFormState])

  const { messages, busy, boot, newChat, sendMessage, approveStep } = useChat({
    currentStep,
    formState,
    onStepApproved: markStepDone,
    onAutoSelectAudience: handleAutoSelectAudience,
  })

  useEffect(() => { boot() }, [boot])


  // Auto-advance when setup Phase 3 confirms — skip manual "Đồng ý" click
  useEffect(() => {
    if (currentStep === 3 && formState.setup.submitted && stepStatuses[3] !== 'done') {
      const data = {
        brief: formState.brief,
        creative: formState.creative,
        attrs: formState.segment.attrs,
        size: formState.segment.size,
        selectedZoneIds: formState.setup.selectedZoneIds,
        recoZones: formState.setup.recoZones,
        campaigns: formState.setup.campaigns || [],
      }
      approveStep(3, data)
    }
  }, [formState.setup.submitted])

  const handleApprove = useCallback(() => {
    const data = {
      brief: formState.brief,
      creative: formState.creative,
      attrs: formState.segment.attrs,
      size: formState.segment.size,
      // Pass zones data for step 3
      selectedZoneIds: formState.setup.selectedZoneIds,
      recoZones: formState.setup.recoZones,
      campaigns: formState.setup.campaigns || [],
    }
    approveStep(currentStep, data)
  }, [currentStep, formState, approveStep])

  // Max step the user has ever reached — allows forward navigation after going back
  const maxReached = stepStatuses.reduce((max, s, i) => s === 'done' ? i + 1 : max, 0)

  const handleStepJump = useCallback((i) => {
    if (busy) return
    // Allow: going back (i <= currentStep), any done step, or the step right after all done steps
    if (i <= currentStep || stepStatuses[i] === 'done' || i <= maxReached) {
      setCurrentStep(i)
      workspaceRef.current?.flash?.()
    }
  }, [busy, currentStep, stepStatuses, maxReached])

  // Partial reset: wipe form data + statuses from `fromStep` onward, go back to that step
  const handlePartialReset = useCallback((fromStep) => {
    const STEP_KEYS = ['brief', 'creative', 'segment', 'setup', 'success', 'report', 'email']
    const STEP_DEFAULTS = [
      initialBrief,
      initialCreative,
      { attrs: [], size: 0 },
      { initialized: false, recoZones: [], selectedZoneIds: [], created: false, submitted: false, phase: 'zones', assignments: {} },
      {},
      { analyzed: false },
      { sent: false },
    ]
    setFormState(prev => {
      const next = { ...prev }
      STEP_KEYS.forEach((key, i) => {
        if (i >= fromStep) next[key] = STEP_DEFAULTS[i]
      })
      return next
    })
    setStepStatuses(prev => prev.map((s, i) => i >= fromStep ? 'pending' : s))
    setCurrentStep(fromStep)
  }, [])

  const handleReset = useCallback(() => handlePartialReset(0), [handlePartialReset])

  // New Chat: clears workspace AND chat history, then re-boots agent greeting
  const handleNewChat = useCallback(() => {
    handlePartialReset(0)
    newChat()
  }, [handlePartialReset, newChat])

  // Listen for agent:reset event fired by BlockRenderer's ActionResetBlock
  useEffect(() => {
    const handler = () => handleReset()
    window.addEventListener('agent:reset', handler)
    return () => window.removeEventListener('agent:reset', handler)
  }, [handleReset])

  const canApprove = (() => {
    if (stepStatuses[currentStep] === 'done') return false
    switch (currentStep) {
      case 1: return (formState.creative.files || []).length > 0
      case 2: return formState.segment.attrs.length > 0
      // Step 3: handled by internal "Tạo chiến dịch" button — WorkFoot button hidden
      case 3: return false
      case 5: return formState.report.analyzed
      case 6: return formState.email.sent
      default: return true
    }
  })()

  return (
    <div className="flex flex-col h-screen bg-gradient-to-br from-slate-50 to-brand-50/30 overflow-hidden">
      <TopBar onReset={handleReset} onNewChat={handleNewChat} />

      <main className="flex flex-1 min-h-0 overflow-hidden">
        {/* Chat Pane — 40% */}
        <div className="flex-[0_0_42%] min-w-0 border-r border-border bg-white/60 backdrop-blur-sm">
          <ChatPane
            messages={messages}
            busy={busy}
            currentStep={currentStep}
            onSend={sendMessage}
            onBack={() => !busy && currentStep > 0 && setCurrentStep(prev => prev - 1)}
          />
        </div>

        {/* Workspace Pane — 58% */}
        <div className="flex-1 min-w-0 bg-white">
          <WorkspacePane
            ref={workspaceRef}
            steps={STEPS}
            currentStep={currentStep}
            stepStatuses={stepStatuses}
            formState={formState}
            setFormState={setFormState}
            onStepJump={handleStepJump}
            onApprove={handleApprove}
            canApprove={canApprove}
            busy={busy}
            onPartialReset={handlePartialReset}
          />
        </div>
      </main>
    </div>
  )
}
