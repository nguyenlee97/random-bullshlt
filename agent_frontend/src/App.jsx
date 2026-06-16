import { useState, useCallback, useEffect, useRef } from 'react'
import { useChat } from '@/hooks/useChat'
import TopBar from '@/components/TopBar'
import ChatPane from '@/components/ChatPane'
import WorkspacePane from '@/components/WorkspacePane'
import { AgentAPI } from '@/api/agentApi'
import { generateId } from '@/lib/utils'
import log from '@/lib/logger'

// ─── Steps meta — NEW ORDER: Brief → Audience → Creative → Setup → Result ─────
export const STEPS = [
  { id: 'brief',    title: 'Brief',      tool: 'brief_parse',    heroLabel: null },
  { id: 'segment',  title: 'Audience',   tool: 'dmp_match',      heroLabel: null },
  { id: 'creative', title: 'Creative',   tool: 'creative_upload', heroLabel: null },
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

const initialCreative = {
  uploaded: false,
  files: [],          // [{ id, name, type, size, dataUrl }]
}

const initialState = {
  brief: initialBrief,
  segment: { attrs: [], size: 0 },
  creative: initialCreative,
  setup: { initialized: false, recoZones: [], selectedZoneIds: [], created: false },
  report: { analyzed: false },
  email: { sent: false },
}

// Step key order matches STEPS array
const STEP_KEYS = ['brief', 'segment', 'creative', 'setup', 'success', 'report', 'email']
const STEP_DEFAULTS = [
  initialBrief,
  { attrs: [], size: 0 },
  initialCreative,
  { initialized: false, recoZones: [], selectedZoneIds: [], created: false, submitted: false, phase: 'zones', assignments: {} },
  {},
  { analyzed: false },
  { sent: false },
]
const STEP_NAMES_VI = ['Brief', 'Audience', 'Creative', 'Setup Camp', 'Kết quả', 'Report', 'Email']

export default function App() {
  const [currentStep, setCurrentStep] = useState(0)
  const [stepStatuses, setStepStatuses] = useState(STEPS.map(() => 'pending'))
  const [formState, setFormState] = useState(initialState)
  const [workspaceEvents, setWorkspaceEvents] = useState([])
  const workspaceRef = useRef(null)

  // ── Workspace event queue ──────────────────────────────────────────────────
  const pushWorkspaceEvent = useCallback((description) => {
    log.workspace('event queued', description)
    setWorkspaceEvents(prev => [...prev, description])
  }, [])

  const clearWorkspaceEvents = useCallback(() => {
    log.workspace('events cleared (sent)')
    setWorkspaceEvents([])
  }, [])

  // ── setFormState wrapper that diffs and emits workspace events ─────────────
  // Use a ref to track the previous state for diffing
  const prevFormRef = useRef(formState)

  const setFormStateWithEvents = useCallback((updater) => {
    setFormState(prev => {
      const next = typeof updater === 'function' ? updater(prev) : updater

      // Diff brief fields
      if (prev.brief && next.brief) {
        if (prev.brief.brand !== next.brief.brand && next.brief.brand) {
          pushWorkspaceEvent(`Đã thay đổi Brand: "${prev.brief.brand || '(trống)'}" → "${next.brief.brand}"`)
        }
        if (prev.brief.objective !== next.brief.objective && next.brief.objective) {
          pushWorkspaceEvent(`Đã thay đổi Objective: ${prev.brief.objective} → ${next.brief.objective}`)
        }
        if (prev.brief.budget !== next.brief.budget && next.brief.budget) {
          pushWorkspaceEvent(`Đã thay đổi Budget: ${prev.brief.budget || 0} → ${next.brief.budget} triệu VND`)
        }
        if (prev.brief.kpi !== next.brief.kpi && next.brief.kpi) {
          pushWorkspaceEvent(`Đã thay đổi KPI: "${prev.brief.kpi || '(trống)'}" → "${next.brief.kpi}"`)
        }
        if (prev.brief.notes !== next.brief.notes && next.brief.notes) {
          pushWorkspaceEvent(`Đã thêm/cập nhật ghi chú Brief`)
        }
      }

      // Diff creative uploads
      const prevFiles = prev.creative?.files?.length || 0
      const nextFiles = next.creative?.files?.length || 0
      if (nextFiles > prevFiles) {
        const newFiles = (next.creative?.files || []).slice(prevFiles)
        pushWorkspaceEvent(`Đã upload ${newFiles.length} creative file: ${newFiles.map(f => f.name).join(', ')}`)
      }

      // Diff audience selection
      const prevAttrs = prev.segment?.attrs?.length || 0
      const nextAttrs = next.segment?.attrs?.length || 0
      if (nextAttrs !== prevAttrs) {
        if (nextAttrs > prevAttrs) {
          pushWorkspaceEvent(`Đã thêm ${nextAttrs - prevAttrs} DMP segment vào Audience (tổng: ${nextAttrs})`)
        } else if (nextAttrs < prevAttrs && nextAttrs > 0) {
          pushWorkspaceEvent(`Đã bỏ chọn ${prevAttrs - nextAttrs} DMP segment (còn: ${nextAttrs})`)
        }
      }

      prevFormRef.current = next
      return next
    })
  }, [pushWorkspaceEvent])

  // ── Step management ────────────────────────────────────────────────────────
  const markStepDone = useCallback((stepIndex) => {
    log.step(`markStepDone: step ${stepIndex} → done`)
    setStepStatuses(prev => {
      const next = [...prev]
      next[stepIndex] = 'done'
      return next
    })
    if (stepIndex < STEPS.length - 1) {
      setTimeout(() => {
        setCurrentStep(stepIndex + 1)
        log.step(`auto-advance to step ${stepIndex + 1}`)
        workspaceRef.current?.flash?.()
      }, 400)
    }
  }, [])

  // ── Workspace update from agent (after user confirms proposal) ─────────────
  const handleWorkspaceUpdate = useCallback((patch) => {
    // patch = { field, value, reason }
    if (!patch?.field) return
    const field = patch.field
    let value = patch.value

    // The model sometimes JSON-stringifies the value — parse it back
    if (typeof value === 'string') {
      try { value = JSON.parse(value) } catch {}
    }

    // Normalize segment attrs so AudienceStep getUid() can match them
    // audience-entry returns {fullLabel, _id} but AudienceStep needs {_uid, name, code}
    if (field === 'segment' && value?.attrs) {
      value = {
        ...value,
        attrs: value.attrs.map(a => ({
          ...a,
          _uid: a._uid || (a._id ? String(a._id) : null) || a.fullLabel || a.name || '',
          name: a.name || a.fullLabel || '',
          code: a.code || '',
          category: a.category || a.type || '',
          est_size: a.est_size ?? (
            a.sizeMin && a.sizeMax ? Math.round((a.sizeMin + a.sizeMax) / 2) : (a.sizeMin || a.sizeMax || 0)
          ),
        })),
      }
    }

    log.workspace('handleWorkspaceUpdate → applying', {
      field,
      value_type: typeof value,
      value_preview: typeof value === 'object' ? JSON.stringify(value).slice(0, 200) : String(value).slice(0, 100),
      reason: patch.reason,
    })

    setFormState(prev => {
      const next = { ...prev }
      const parts = field.split('.')

      if (parts.length === 2) {
        // Dotted path: e.g. "brief.brand" → update single key
        const [section, key] = parts
        if (section in next) {
          log.workspace(`  dotted-path update: ${section}.${key} =`, value)
          next[section] = { ...next[section], [key]: value }
        } else {
          log.error(`  unknown section "${section}" — no update applied`)
        }
      } else if (parts.length === 1) {
        // Whole section update: e.g. field="brief", value={brand: "ZUMA", budget: 600, ...}
        const section = parts[0]
        if (section in next && typeof value === 'object' && value !== null) {
          log.workspace(`  section merge: ${section} ← ${Object.keys(value).join(', ')}`)
          next[section] = { ...next[section], ...value }
        } else if (section in next) {
          next[section] = value
        } else {
          log.error(`  unknown section "${section}" — no update applied`)
        }
      }
      return next
    })
    pushWorkspaceEvent(`Agent đã cập nhật "${field}" (đã xác nhận bởi anh/chị)`)
  }, [pushWorkspaceEvent])


  // ── Auto-select audience from chat (targeting autopick) ───────────────────
  const handleAutoSelectAudience = useCallback((matchedSegments, targetingMap = {}) => {
    setFormStateWithEvents(prev => {
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
  }, [setFormStateWithEvents])

  const { messages, busy, boot, newChat, sendMessage, approveStep, retryLastMessage, canRetry } = useChat({
    currentStep,
    formState,
    stepStatuses,
    workspaceEvents,
    onClearWorkspaceEvents: clearWorkspaceEvents,
    onStepApproved: markStepDone,
    onAutoSelectAudience: handleAutoSelectAudience,
    onWorkspaceUpdate: handleWorkspaceUpdate,

    // Full state snapshot for retry — capture formState+step BEFORE each send
    onSnapshotRequest: useCallback(() => ({
      formState: JSON.parse(JSON.stringify({
        ...formState,
        creative: { ...formState.creative, files: formState.creative.files.map(f => ({ ...f, dataUrl: null })) },  // strip heavy base64
      })),
      stepStatuses: [...stepStatuses],
      currentStep,
    }), [formState, stepStatuses, currentStep]),

    // Full state restore for retry — revert formState+step to before the failed message
    onRestoreSnapshot: useCallback((snapshot) => {
      log.step('retryLastMessage → restoring snapshot', {
        currentStep: snapshot.currentStep,
        stepStatuses: snapshot.stepStatuses,
        formState_brief_brand: snapshot.formState?.brief?.brand,
      })
      // Revert creative files (dataUrl was stripped during snapshot, restore originals from current state)
      const restoredCreative = {
        ...snapshot.formState.creative,
        files: formState.creative.files.slice(0, snapshot.formState.creative.files.length),
      }
      setFormState({ ...snapshot.formState, creative: restoredCreative })
      setStepStatuses(snapshot.stepStatuses)
      setCurrentStep(snapshot.currentStep)
    }, [formState.creative.files]),
  })

  useEffect(() => { boot() }, [boot])

  // Audience-entry: when user reaches step 1 with brief done → proactive recommendation in chat
  const audienceEntryFiredRef = useRef(false)
  const [audienceRecommendation, setAudienceRecommendation] = useState(null)
  useEffect(() => {
    if (
      currentStep === 1 &&
      stepStatuses[0] === 'done' &&
      !audienceEntryFiredRef.current &&
      formState.segment.attrs.length === 0  // skip if already has segments
    ) {
      audienceEntryFiredRef.current = true
      ;(async () => {
        log.step('audience-entry triggered — fetching recommendation')
        try {
          const data = await AgentAPI.getAudienceEntry()
          if (data && !data.skip) {
            // Extract workspace_proposal block
            const proposalBlock = (data.blocks || []).find(b => b.type === 'workspace_proposal' && b.changes?.field === 'segment')
            if (proposalBlock?.changes?.value?.attrs?.length) {
              // Store for AudienceStep recoFromChat (shows in AI Gợi ý section)
              setAudienceRecommendation(proposalBlock.changes.value.attrs)
              log.step('audience-entry — stored recommendation', { count: proposalBlock.changes.value.attrs.length })
              // ── Auto-apply: pre-populate segment form (attrs + targeting + size) ──
              // Same as brief: audience is populated immediately so user can edit via
              // workspace panel or chat (bidirectional). Injected messages bypass
              // useChat.js sendMessage, so we explicitly apply the workspace update here.
              handleWorkspaceUpdate(proposalBlock.changes)
              log.workspace('audience-entry → auto-applied segment proposal to formState')
            }
            const msg = {
              id: generateId(),
              role: 'assistant',
              content: data.text || '',
              blocks: data.blocks || [],
              timestamp: new Date().toISOString(),
              metadata: data.meta || { tool: 'audience_entry', model: 'minimax', step: 1 },
            }
            window.dispatchEvent(new CustomEvent('agent:inject_message', { detail: msg }))
          }
        } catch (e) {
          log.error('audience-entry fetch failed', e.message)
        }
      })()
    }
    // NOTE: do NOT reset the flag here on currentStep !== 1.
    // Doing so causes a double-fire: stepStatuses[0] change fires the effect with currentStep=0
    // (resets flag), then currentStep=1 fires again and re-triggers the call.
    // Flag is reset only by handlePartialReset when the user explicitly resets the flow.
  }, [currentStep, stepStatuses[0], handleWorkspaceUpdate])

  // Auto-advance when setup Phase 3 confirms
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
      selectedZoneIds: formState.setup.selectedZoneIds,
      recoZones: formState.setup.recoZones,
      campaigns: formState.setup.campaigns || [],
    }
    approveStep(currentStep, data)
  }, [currentStep, formState, approveStep])

  const maxReached = stepStatuses.reduce((max, s, i) => s === 'done' ? i + 1 : max, 0)

  const handleStepJump = useCallback((i) => {
    if (busy) return
    if (i <= currentStep || stepStatuses[i] === 'done' || i <= maxReached) {
      log.step(`stepJump: ${currentStep} → ${i}`)
      setCurrentStep(i)
      workspaceRef.current?.flash?.()
    }
  }, [busy, currentStep, stepStatuses, maxReached])

  // Partial reset: wipe form data + statuses from fromStep onward
  const handlePartialReset = useCallback((fromStep) => {
    log.step(`handlePartialReset from step ${fromStep} (${STEP_NAMES_VI[fromStep]})`)
    // Allow audience-entry to re-trigger if the brief step is being reset
    if (fromStep <= 1) audienceEntryFiredRef.current = false
    // Emit a workspace event so the agent knows
    pushWorkspaceEvent(
      `Đã bấm 'Chỉnh sửa lại' ở bước ${STEP_NAMES_VI[fromStep]} — ` +
      `các bước ${STEP_NAMES_VI.slice(fromStep).join(', ')} đã được reset`
    )
    setFormState(prev => {
      const next = { ...prev }
      STEP_KEYS.forEach((key, i) => {
        if (i >= fromStep) next[key] = STEP_DEFAULTS[i]
      })
      return next
    })
    setStepStatuses(prev => prev.map((s, i) => i >= fromStep ? 'pending' : s))
    setCurrentStep(fromStep)
  }, [pushWorkspaceEvent])

  const handleReset = useCallback(() => handlePartialReset(0), [handlePartialReset])

  const handleNewChat = useCallback(() => {
    handlePartialReset(0)
    newChat()
  }, [handlePartialReset, newChat])

  // Listen for agent:reset event from BlockRenderer ActionResetBlock
  useEffect(() => {
    const handler = () => handleReset()
    window.addEventListener('agent:reset', handler)
    return () => window.removeEventListener('agent:reset', handler)
  }, [handleReset])

  // Listen for agent:workspace_confirm — user clicked Đồng ý on a proposal block
  useEffect(() => {
    const handler = (e) => {
      log.event('agent:workspace_confirm received', e.detail)
      if (e.detail?.patch) {
        handleWorkspaceUpdate(e.detail.patch)
      }
    }
    window.addEventListener('agent:workspace_confirm', handler)
    return () => window.removeEventListener('agent:workspace_confirm', handler)
  }, [handleWorkspaceUpdate])

  useEffect(() => {
    const handler = (e) => log.event('agent:workspace_cancel received', e.detail)
    window.addEventListener('agent:workspace_cancel', handler)
    return () => window.removeEventListener('agent:workspace_cancel', handler)
  }, [])

  const canApprove = (() => {
    if (stepStatuses[currentStep] === 'done') return false
    switch (currentStep) {
      case 1: return formState.segment.attrs.length > 0   // Audience is step 1
      case 2: return (formState.creative.files || []).length > 0  // Creative is step 2
      case 3: return false  // Setup: handled by internal button
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
            onRetry={retryLastMessage}
            canRetry={canRetry && !busy}
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
            setFormState={setFormStateWithEvents}
            onStepJump={handleStepJump}
            onApprove={handleApprove}
            canApprove={canApprove}
            busy={busy}
            onPartialReset={handlePartialReset}
            recoFromChat={audienceRecommendation}
          />
        </div>
      </main>
    </div>
  )
}
