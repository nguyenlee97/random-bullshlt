import { useState, useCallback, useEffect, useRef } from 'react'
import { useChat } from '@/hooks/useChat'
import TopBar from '@/components/TopBar'
import ChatPane from '@/components/ChatPane'
import WorkspacePane from '@/components/WorkspacePane'
import SplitDivider from '@/components/SplitDivider'
import { AgentAPI, getSetupEntry } from '@/api/agentApi'
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
  const mainRef = useRef(null)

  // ── Mobile split ratio ─────────────────────────────────────────────────────
  // splitRatio = fraction [0.0–1.0] of the container height given to Chat pane (bottom).
  // Workspace (top) gets (1 - splitRatio).
  // Only used on mobile (< 768px); desktop uses fixed 42/58 flex sizing.
  const [splitRatio, setSplitRatio] = useState(0.5)

  // Steps that are workspace-heavy: auto-shrink chat to 35% on these
  const WORKSPACE_HEAVY_STEPS = new Set([2, 3, 5, 6]) // Creative, Setup, Report, Email

  // Auto-ratio fires every time currentStep changes (mobile only)
  useEffect(() => {
    if (window.innerWidth >= 768) return
    setSplitRatio(WORKSPACE_HEAVY_STEPS.has(currentStep) ? 0.35 : 0.5)
  }, [currentStep])

  // Drag handler — called by SplitDivider with deltaY pixels from the drag.
  // Layout: Workspace (top) height = (1-splitRatio), Chat (bottom) height = splitRatio.
  // Dragging DOWN → divider moves down → workspace grows → splitRatio DECREASES → negate deltaY.
  const handleSplitDrag = useCallback((deltaY) => {
    const containerH = mainRef.current?.clientHeight ?? window.innerHeight
    setSplitRatio(prev =>
      Math.min(0.85, Math.max(0.15, prev - deltaY / containerH))
    )
  }, [])

  // Expand button handlers (snap to target ratios or restore 50/50)
  // Chat expand  → 85% chat / 15% workspace  (user ignores workspace, reads chat)
  // Work expand  → 30% chat / 70% workspace  (user works in workspace, still needs chat)
  const handleWorkspaceExpand = useCallback(() => {
    setSplitRatio(prev => (prev <= 0.32 ? 0.5 : 0.30)) // toggle workspace 70%
  }, [])
  const handleChatExpand = useCallback(() => {
    setSplitRatio(prev => (prev >= 0.83 ? 0.5 : 0.85)) // toggle chat 85%
  }, [])

  // Visual Viewport API — tracks keyboard height on mobile so the composer
  // is never hidden behind the soft keyboard. Sets a CSS variable used in index.css.
  useEffect(() => {
    if (!window.visualViewport) return
    const update = () => {
      document.documentElement.style.setProperty(
        '--visual-viewport-height',
        `${window.visualViewport.height}px`
      )
    }
    window.visualViewport.addEventListener('resize', update)
    window.visualViewport.addEventListener('scroll', update)
    update()
    return () => {
      window.visualViewport.removeEventListener('resize', update)
      window.visualViewport.removeEventListener('scroll', update)
    }
  }, [])
  // ── Activity notifications for SplitDivider ─────────────────────────────────
  // chatHasNew      → new agent message while chat is compact (workspace expanded)
  // workspaceHasNew → step advanced while workspace is compact (chat expanded)
  const [chatHasNew, setChatHasNew] = useState(false)
  const [workspaceHasNew, setWorkspaceHasNew] = useState(false)
  const prevMsgIdRef = useRef(null)   // tracks last assistant msg ID (ID-based, not length-based)
  // splitRatioRef keeps the latest ratio accessible inside callbacks without
  // adding splitRatio to their dependency arrays (avoids stale closure).
  const splitRatioRef = useRef(splitRatio)
  useEffect(() => { splitRatioRef.current = splitRatio }, [splitRatio])

  // (messages.length effect placed after useChat declaration below — TDZ-safe)
  // workspaceHasNew is triggered directly inside handleWorkspaceUpdate below.

  // Clear notifications when the pane becomes visible again
  useEffect(() => {
    if (splitRatio >= 0.38) setChatHasNew(false)
    if (splitRatio <= 0.62) setWorkspaceHasNew(false)
  }, [splitRatio])

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
    let field = patch.field
    let value = patch.value

    // Normalize field aliases — LLM sometimes uses "audience" instead of "segment"
    const FIELD_ALIASES = { audience: 'segment', targeting: 'segment', dmp: 'segment' }
    if (FIELD_ALIASES[field]) {
      log.workspace(`field alias: "${field}" → "${FIELD_ALIASES[field]}"`)
      field = FIELD_ALIASES[field]
    }

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
          // Special: setup.action="auto_assign" → fire event, don't store action flag
          if (section === 'setup' && value.action === 'auto_assign') {
            log.step('handleWorkspaceUpdate: auto_assign action → dispatching agent:trigger_auto_assign')
            setTimeout(() => window.dispatchEvent(new CustomEvent('agent:trigger_auto_assign')), 200)
            const { action: _action, ...valueWithoutAction } = value
            next[section] = { ...next[section], ...valueWithoutAction }
          } else {
            next[section] = { ...next[section], ...value }
          }
        } else if (section in next) {
          next[section] = value
        } else {
          log.error(`  unknown section "${section}" — no update applied`)
        }
      }
      return next
    })
    pushWorkspaceEvent(`Agent đã cập nhật "${field}" (đã xác nhận bởi anh/chị)`)
    // Notify user if workspace is hidden behind an expanded chat pane
    if (window.innerWidth < 768 && splitRatioRef.current > 0.62) {
      setWorkspaceHasNew(true)
    }
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

  // Watch for new assistant messages while chat is compact (workspace expanded on mobile).
  // Uses ID comparison instead of messages.length — stopThinking() REPLACES the thinking
  // bubble (array length unchanged) so length-based tracking misses chip responses.
  useEffect(() => {
    const last = messages[messages.length - 1]
    if (!last || last.role !== 'assistant') return
    if (last.id !== prevMsgIdRef.current) {
      prevMsgIdRef.current = last.id
      if (window.innerWidth < 768 && splitRatioRef.current < 0.38) {
        setChatHasNew(true)
      }
    }
  }, [messages]) // eslint-disable-line react-hooks/exhaustive-deps

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
          // Pass current formState.brief as hint — backend uses it when pending_proposal
          // hasn't been committed yet (e.g. user clicked '✅ Đồng ý, cập nhật' button)
          const data = await AgentAPI.getAudienceEntry(formState.brief)
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
              suggestions: data.suggestions || [],
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

  // Setup-entry: when user reaches step 3 with creative done → proactive zone recommendation in chat
  const setupEntryFiredRef = useRef(false)
  useEffect(() => {
    if (
      currentStep === 3 &&
      stepStatuses[2] === 'done' &&
      !setupEntryFiredRef.current &&
      !formState.setup.initialized   // skip if zones already loaded
    ) {
      setupEntryFiredRef.current = true
      ;(async () => {
        log.step('setup-entry triggered — fetching zone recommendation')
        try {
          const data = await getSetupEntry()
          if (data && !data.skip) {
            // Auto-apply workspace_proposal so SetupStep reads zones from formState
            const proposalBlock = (data.blocks || []).find(
              b => b.type === 'workspace_proposal' && b.changes?.field === 'setup'
            )
            if (proposalBlock?.changes?.value) {
              handleWorkspaceUpdate(proposalBlock.changes)
              log.workspace('setup-entry → auto-applied zone proposal to formState')
            }
            const msg = {
              id: generateId(),
              role: 'assistant',
              content: data.text || '',
              blocks: data.blocks || [],
              timestamp: new Date().toISOString(),
              metadata: data.meta || { tool: 'setup_entry', model: 'none', step: 3 },
              suggestions: data.suggestions || [],
            }
            window.dispatchEvent(new CustomEvent('agent:inject_message', { detail: msg }))
          }
        } catch (e) {
          log.error('setup-entry fetch failed', e.message)
        }
      })()
    }
  }, [currentStep, stepStatuses[2], handleWorkspaceUpdate])

  // Report-entry: when user reaches step 5 with step 4 done → trigger report generation
  const reportEntryFiredRef = useRef(false)
  useEffect(() => {
    if (
      currentStep === 5 &&
      stepStatuses[4] === 'done' &&
      !reportEntryFiredRef.current
    ) {
      reportEntryFiredRef.current = true
      ;(async () => {
        log.step('report-entry triggered — calling AgentAPI.reportEntry')
        try {
          const data = await AgentAPI.reportEntry()
          if (data) {
            // Extract campaignId from workspace_update
            const campaignId = data.workspace_update?.value?.campaignId || ''

            // Store report context in formState
            setFormState(prev => ({
              ...prev,
              report: {
                ...prev.report,
                campaignId: campaignId || prev.report?.campaignId || '',
              },
            }))

            // Inject intro message into chat
            const msg = {
              id: generateId(),
              role: 'assistant',
              content: data.text || '',
              blocks: data.blocks || [],
              timestamp: new Date().toISOString(),
              metadata: data.meta || { tool: 'report_entry', model: 'none', step: 5 },
              suggestions: data.suggestions || [],
            }
            window.dispatchEvent(new CustomEvent('agent:inject_message', { detail: msg }))
          }
        } catch (e) {
          log.error('report-entry failed', e.message)
        }
      })()
    }
  }, [currentStep, stepStatuses[4]])

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
    // Allow entry probes to re-trigger when their steps are reset
    if (fromStep <= 1) audienceEntryFiredRef.current = false
    if (fromStep <= 3) setupEntryFiredRef.current = false
    if (fromStep <= 5) reportEntryFiredRef.current = false
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
    const STEP_PRIMARY_FIELDS = { 0: 'brief', 1: 'segment', 2: 'creative', 3: 'setup' }
    const handler = (e) => {
      log.event('agent:workspace_confirm received', e.detail)
      if (e.detail?.patch) {
        handleWorkspaceUpdate(e.detail.patch)
        const topField = (e.detail.patch.field || '').split('.')[0]
        const stepEntry = Object.entries(STEP_PRIMARY_FIELDS).find(([, v]) => v === topField)
        if (stepEntry) {
          const stepNum = Number(stepEntry[0])
          // ── Persist to MongoDB so audience-entry (and other downstream calls)
          // can read the confirmed value immediately. Without this, the button only
          // updates frontend state — backend session stays empty → brief_not_set.
          AgentAPI.commitWorkspace(topField, e.detail.patch.value)
            .then(r => log.workspace(`commitWorkspace(${topField}) →`, r?.ok ? 'ok' : 'failed'))
            .catch(err => log.error('commitWorkspace failed', err?.message))
          if (stepStatuses[stepNum] !== 'done') {
            log.step(`workspace_confirm → marking step ${stepNum} done for field "${topField}"`)
            // Setup step is special — it has 3 sub-phases (zones→assign→confirm).
            // It must NOT be marked done here; it advances only when formState.setup.submitted
            // becomes true (handled by the dedicated useEffect below).
            if (topField === 'setup') {
              log.step('workspace_confirm(setup) — skipping markStepDone; sub-phase flow handles advance')
              return
            }
            // Parse value if LLM returned it as a JSON string (not an object)
            const _rawPatchVal = e.detail.patch.value
            const _patchVal = typeof _rawPatchVal === 'string'
              ? (() => { try { return JSON.parse(_rawPatchVal) } catch { return {} } })()
              : (_rawPatchVal || {})
            const confirmMessages = {
              brief: '✅ Brief đã được lưu! Em sẽ chuyển sang bước **Audience** để gợi ý segments phù hợp.',
              segment: `✅ Audience đã xác nhận! ${(_patchVal.attrs || []).length} segments được áp dụng — em sẽ chuyển sang bước **Creative**.`,
              creative: '✅ Creative đã xác nhận! Em sẽ chuyển sang bước **Setup Camp**.',
            }
            const confirmText = confirmMessages[topField] || `✅ Bước ${topField} đã xác nhận.`
            window.dispatchEvent(new CustomEvent('agent:inject_message', {
              detail: {
                id: `confirm_${topField}_${Date.now()}`,
                role: 'assistant',
                content: confirmText,
                blocks: [],
                timestamp: new Date().toISOString(),
                metadata: { tool: 'workspace_confirmed', model: 'none', step: stepNum },
              }
            }))
            setTimeout(() => markStepDone(stepNum), 700)
          }
        }
      }
    }
    window.addEventListener('agent:workspace_confirm', handler)
    return () => window.removeEventListener('agent:workspace_confirm', handler)
  }, [handleWorkspaceUpdate, stepStatuses, markStepDone])

  // Listen for agent:setup_zones_confirmed — fired by WorkspaceProposalBlock when user
  // clicks "✅ Duyệt các zones này". This advances the setup sub-phase to 'assign' using
  // the CURRENT formState.setup selection (not the stale proposal value).
  useEffect(() => {
    const handler = () => {
      setFormState(prev => {
        const currentSetup = prev.setup
        const selectedIds = currentSetup.selectedZoneIds || []
        if (!selectedIds.length) {
          log.step('setup_zones_confirmed: no zones selected — ignoring')
          return prev
        }
        log.step(`setup_zones_confirmed → advancing to assign phase (${selectedIds.length} zones)`)
        // Persist current selection to backend
        AgentAPI.commitWorkspace('setup', { ...currentSetup, phase: 'assign' })
          .then(r => log.workspace('commitWorkspace(setup/zones) ->', r?.ok ? 'ok' : 'failed'))
          .catch(err => log.error('commitWorkspace(setup) failed', err?.message))
        // Inject acknowledgment message into chat
        const confirmText = `✅ Đã xác nhận **${selectedIds.length} zones**! Anh/chị chuyển sang bước **Gắn creative** trong panel bên phải để gán creative vào từng zone nhé.`
        window.dispatchEvent(new CustomEvent('agent:inject_message', {
          detail: {
            id: `setup_zones_confirm_${Date.now()}`,
            role: 'assistant',
            content: confirmText,
            blocks: [],
            timestamp: new Date().toISOString(),
            metadata: { tool: 'workspace_confirmed', model: 'none', step: 3 },
          }
        }))
        return { ...prev, setup: { ...currentSetup, phase: 'assign' } }
      })
    }
    window.addEventListener('agent:setup_zones_confirmed', handler)
    return () => window.removeEventListener('agent:setup_zones_confirmed', handler)
  }, [])

  useEffect(() => {
    const handler = (e) => {
      log.event('agent:workspace_cancel received', e.detail)
      const field = e.detail?.field
      // For audience proposals: "Tự chọn" should clear the AI-applied segments
      // so the user starts with an empty selection and picks manually.
      if (field === 'segment') {
        log.step('workspace_cancel(segment) → clearing attrs + targeting')
        setFormState(prev => ({
          ...prev,
          segment: { attrs: [], size: 0, targeting: {} },
        }))
      }
    }
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

  // ── isMobile helper (used for conditional inline styles) ──────────────────
  // Read at render-time. Tailwind md: breakpoints handle the class-based
  // layout switching automatically on resize.
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 768

  return (
    <div className="flex flex-col h-screen bg-gradient-to-br from-slate-50 to-brand-50/30 overflow-hidden">
      <TopBar onReset={handleReset} onNewChat={handleNewChat} />

      {/*
        Mobile layout: flex-col, Workspace on TOP, Chat on BOTTOM.
        Desktop layout: flex-row (md:flex-row), Chat on LEFT (42%), Workspace on RIGHT.

        We use CSS `order` to reorder without changing the DOM:
          Workspace: order-1 on mobile (top), md:order-2 (right)
          Chat:      order-3 on mobile (bottom), md:order-1 (left)
      */}
      <main ref={mainRef} className="flex flex-1 min-h-0 overflow-hidden flex-col md:flex-row">

        {/* ── Workspace Pane ──────────────────────────────────────────
            Mobile: TOP (order-1), height = (1 - splitRatio)
            Desktop: RIGHT side, flex-1                              */}
        <div
          className="order-1 md:order-2 flex flex-col min-w-0 overflow-hidden bg-white
                     md:flex-1 md:h-full
                     transition-[height] duration-300 ease-in-out"
          style={isMobile ? { height: `${(1 - splitRatio) * 100}%` } : undefined}
        >
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
            onSendChat={sendMessage}
          />
        </div>

        {/* ── Draggable Divider ─────────────────────────────────────
            Mobile only (md:hidden inside component), order-2       */}
        <div className="order-2 md:hidden">
          <SplitDivider
            onDrag={handleSplitDrag}
            splitRatio={splitRatio}
            onWorkspaceExpand={handleWorkspaceExpand}
            onChatExpand={handleChatExpand}
            chatHasNew={chatHasNew}
            workspaceHasNew={workspaceHasNew}
          />
        </div>

        {/* ── Chat Pane ─────────────────────────────────────────────
            Mobile: BOTTOM (order-3), height = splitRatio
            Desktop: LEFT side, flex-[0_0_42%]                      */}
        <div
          className="order-3 md:order-1 flex flex-col min-w-0 overflow-hidden
                     bg-white/60 backdrop-blur-sm border-border
                     border-t md:border-t-0 md:border-r
                     md:flex-[0_0_42%] md:h-full
                     transition-[height] duration-300 ease-in-out"
          style={isMobile ? { height: `${splitRatio * 100}%` } : undefined}
        >
          <ChatPane
            messages={messages}
            busy={busy}
            currentStep={currentStep}
            onSend={sendMessage}
            onBack={() => !busy && currentStep > 0 && setCurrentStep(prev => prev - 1)}
            onRetry={retryLastMessage}
            canRetry={canRetry && !busy}
            chatCompact={isMobile && splitRatio < 0.38}
          />
        </div>

      </main>
    </div>
  )
}
