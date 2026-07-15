import { useState, useCallback, useEffect, useRef } from 'react'
import { useChat } from '@/hooks/useChat'
import TopBar from '@/components/TopBar'
import ChatPane from '@/components/ChatPane'
import WorkspacePane from '@/components/WorkspacePane'
import ExperienceSelector from '@/components/ExperienceSelector'
import AutopilotPanel from '@/components/AutopilotPanel'
import ModeSwitcher from '@/components/ModeSwitcher'
import { AgentAPI, getSetupEntry } from '@/api/agentApi'
import { generateId } from '@/lib/utils'
import log from '@/lib/logger'
import { MessageSquare, LayoutDashboard, Sparkles } from 'lucide-react'
import { DemoProvider } from '@/demo/DemoEngine'
import { ZONE_FORMAT_MAP } from '@/demo/demoScripts'
import { canApproveWorkflowStep } from '@/lib/workflowValidation'
import {
  deriveStepStatuses,
  firstRecomputeStep,
  isStepReachable,
  workspacePatchTarget,
} from '@/lib/nonLinearWorkflow'

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

const STEP_NAMES_VI = ['Brief', 'Audience', 'Creative', 'Setup Camp', 'Kết quả', 'Report', 'Email']

// Steps that auto-navigate to Workspace tab after agent update (2.5s delay)
const AUTO_NAV_STEPS = new Set([2, 3, 5]) // Creative, Setup, Report

// ─── Mobile Tab Bar ─────────────────────────────────────────────────────────
function TabBar({ activeTab, onTabChange, chatHasNew, workspaceHasNew, experienceMode }) {
  const canvasTab = experienceMode === 'autopilot' ? 'autopilot' : 'workspace'
  const CanvasIcon = experienceMode === 'autopilot' ? Sparkles : LayoutDashboard
  const canvasLabel = experienceMode === 'autopilot' ? 'Tiến độ' : 'Workspace'
  return (
    <div className="flex flex-shrink-0 border-b border-border bg-white/95 backdrop-blur-sm shadow-sm" role="tablist" aria-label="Chọn khu vực làm việc">
      <button
        id="tab-chat"
        onClick={() => onTabChange('chat')}
        role="tab"
        aria-selected={activeTab === 'chat'}
        className={`flex-1 flex items-center justify-center gap-2 py-3 text-sm font-semibold transition-all relative ${
          activeTab === 'chat'
            ? 'text-brand-600 border-b-2 border-brand-500 bg-brand-50/30'
            : 'text-muted-foreground hover:text-foreground'
        }`}
      >
        <MessageSquare className="w-4 h-4" />
        Chat
        {chatHasNew && (
          <span className="absolute top-2 right-[28%] w-2 h-2 rounded-full bg-brand-500 animate-pulse" />
        )}
      </button>
      <button
        id={`tab-${canvasTab}`}
        onClick={() => onTabChange(canvasTab)}
        role="tab"
        aria-selected={activeTab === canvasTab}
        className={`flex-1 flex items-center justify-center gap-2 py-3 text-sm font-semibold transition-all relative ${
          activeTab === canvasTab
            ? 'text-brand-600 border-b-2 border-brand-500 bg-brand-50/30'
            : 'text-muted-foreground hover:text-foreground'
        }`}
      >
        <CanvasIcon className="w-4 h-4" />
        {canvasLabel}
        {workspaceHasNew && (
          <span className="absolute top-2 right-[22%] w-2 h-2 rounded-full bg-brand-500 animate-pulse" />
        )}
      </button>
    </div>
  )
}

export default function App() {
  const [experienceMode, setExperienceMode] = useState(null)
  const [modeSelectionBusy, setModeSelectionBusy] = useState(false)
  const [modeSelectionError, setModeSelectionError] = useState('')
  const [autopilotSummary, setAutopilotSummary] = useState(null)
  const [currentStep, setCurrentStep] = useState(0)
  const [stepStatuses, setStepStatuses] = useState(STEPS.map(() => 'pending'))
  const [formState, setFormState] = useState(initialState)
  const [workspaceEvents, setWorkspaceEvents] = useState([])
  const [workspaceConflict, setWorkspaceConflict] = useState(null)
  const [canonicalWorkspace, setCanonicalWorkspace] = useState(null)
  const [recomputePlan, setRecomputePlan] = useState(null)
  const workspaceRef = useRef(null)
  const mainRef = useRef(null)
  const bootedRef = useRef(false)

  // ── Demo visibility: hide Demo button once user has interacted ──────────
  const [hasUserStarted, setHasUserStarted] = useState(false)

  // ── Mobile tab state ─────────────────────────────────────────────────────
  // activeTab controls which pane is visible on mobile (<768px).
  // Desktop keeps the fixed 42/58 split layout unchanged.
  const [activeTab, setActiveTab] = useState('chat')
  // Refs allow callbacks to read current values without stale closures
  const activeTabRef = useRef('chat')
  useEffect(() => { activeTabRef.current = activeTab }, [activeTab])
  const currentStepRef = useRef(currentStep)
  useEffect(() => { currentStepRef.current = currentStep }, [currentStep])

  // ── Demo-active flag ───────────────────────────────────────────────────────
  // While the guided demo is running it is the sole controller of the mobile
  // tab, so App's own auto-navigation must stand down to avoid fighting it.
  const isDemoActiveRef = useRef(false)

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

  useEffect(() => {
    const handler = (event) => setWorkspaceConflict(event.detail || {})
    window.addEventListener('agent:workspace_conflict', handler)
    return () => window.removeEventListener('agent:workspace_conflict', handler)
  }, [])

  // ── Tab notification state ───────────────────────────────────────────────
  // chatHasNew      → new agent message while user is on Workspace tab
  // workspaceHasNew → agent updated workspace while user is on Chat tab
  const [chatHasNew, setChatHasNew] = useState(false)
  const [workspaceHasNew, setWorkspaceHasNew] = useState(false)
  const prevMsgIdRef = useRef(null) // ID-based tracking (not length-based)

  // Clear notification dot when user switches to that tab
  useEffect(() => {
    if (activeTab === 'chat')      setChatHasNew(false)
    if (activeTab === 'workspace') setWorkspaceHasNew(false)
  }, [activeTab])

  // ── Workspace event queue ──────────────────────────────────────────────────
  const pushWorkspaceEvent = useCallback((description) => {
    log.workspace('event queued', description)
    setWorkspaceEvents(prev => [...prev, description])
  }, [])

  const clearWorkspaceEvents = useCallback(() => {
    log.workspace('events cleared (sent)')
    setWorkspaceEvents([])
  }, [])

  const hydrateCanonicalWorkspace = useCallback((workspace) => {
    if (!workspace) return
    const artifacts = workspace.artifacts || {}
    setCanonicalWorkspace(workspace)
    setFormState(prev => ({
      ...prev,
      ...(artifacts.brief?.value ? { brief: artifacts.brief.value } : {}),
      ...((artifacts.audience?.value || artifacts.targeting?.value) ? {
        segment: {
          ...prev.segment,
          ...(artifacts.audience?.value || {}),
          targeting: artifacts.targeting?.value || prev.segment?.targeting || {},
        },
      } : {}),
      ...(artifacts.creative?.value ? { creative: artifacts.creative.value } : {}),
      ...((artifacts.placements?.value || artifacts.assignments?.value) ? {
        setup: {
          ...prev.setup,
          ...(artifacts.placements?.value || {}),
          assignments: artifacts.assignments?.value || artifacts.placements?.value?.assignments || {},
        },
      } : {}),
    }))
    setStepStatuses(prev => deriveStepStatuses(prev, workspace))
    setWorkspaceConflict(null)
    AgentAPI.getRecomputePlan().then(plan => {
      if (plan) setRecomputePlan(plan)
    })
  }, [])

  const reloadCanonicalWorkspace = useCallback(async () => {
    const workspace = await AgentAPI.getWorkspace()
    if (!workspace) return
    hydrateCanonicalWorkspace(workspace)
    pushWorkspaceEvent(`Đã tải lại workspace phiên bản ${workspace.revision} từ máy chủ`)
  }, [hydrateCanonicalWorkspace, pushWorkspaceEvent])

  useEffect(() => {
    const handler = event => hydrateCanonicalWorkspace(event.detail)
    window.addEventListener('agent:canonical_workspace', handler)
    AgentAPI.getWorkspace().then(hydrateCanonicalWorkspace)
    return () => window.removeEventListener('agent:canonical_workspace', handler)
  }, [hydrateCanonicalWorkspace])

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
    const target = workspacePatchTarget(patch.field)
    let field = target.path
    let value = patch.value
    if (field !== patch.field) log.workspace(`field mapping: "${patch.field}" → "${field}"`)

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
    // On mobile: always notify. For key steps, also auto-navigate to Workspace after 2.5s.
    // Suppressed while the guided demo runs — it drives the tabs itself.
    if (experienceMode === 'guided' && window.innerWidth < 768 && !isDemoActiveRef.current) {
      setWorkspaceHasNew(true)
      if (AUTO_NAV_STEPS.has(currentStepRef.current) && activeTabRef.current === 'chat') {
        setTimeout(() => setActiveTab('workspace'), 2500)
      }
    }
  }, [experienceMode, pushWorkspaceEvent])


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

  const handleCreativePrepared = useCallback((files) => {
    setFormState(prev => ({
      ...prev,
      creative: { ...prev.creative, files, uploaded: files.length > 0 },
    }))
  }, [])

  const { messages, busy, boot, newChat, sendMessage, approveStep, retryLastMessage, canRetry } = useChat({
    currentStep,
    formState,
    stepStatuses,
    workspaceEvents,
    onClearWorkspaceEvents: clearWorkspaceEvents,
    onStepApproved: markStepDone,
    onAutoSelectAudience: handleAutoSelectAudience,
    onWorkspaceUpdate: handleWorkspaceUpdate,
    onCreativePrepared: handleCreativePrepared,

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
      if (window.innerWidth < 768 && activeTabRef.current === 'workspace' && !isDemoActiveRef.current) {
        setChatHasNew(true)
      }
    }
  }, [messages]) // eslint-disable-line react-hooks/exhaustive-deps

  const selectExperience = useCallback(async (mode) => {
    if (mode === experienceMode) return true
    setModeSelectionBusy(true)
    setModeSelectionError('')
    try {
      const result = await AgentAPI.setWorkspacePreferences(
        mode,
        mode === 'autopilot' ? 'critical_only' : 'review_every_stage',
      )
      if (!result?.ok) throw new Error(result?.detail || 'Không thể lưu chế độ làm việc.')
      setExperienceMode(mode)
      setActiveTab(mode === 'autopilot' ? 'autopilot' : 'workspace')
      setHasUserStarted(true)
      return true
    } catch (error) {
      setModeSelectionError(error.message)
      return false
    } finally {
      setModeSelectionBusy(false)
    }
  }, [experienceMode])

  useEffect(() => {
    if (experienceMode && !bootedRef.current) {
      bootedRef.current = true
      boot()
    }
  }, [boot, experienceMode])

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

  const handleStepJump = useCallback((i) => {
    if (busy) return
    if (i >= 0 && i < STEPS.length && isStepReachable(i, currentStep, stepStatuses)) {
      log.step(`stepJump: ${currentStep} → ${i}`)
      setCurrentStep(i)
      workspaceRef.current?.flash?.()
    }
  }, [busy, currentStep, stepStatuses])

  // Non-linear edit: preserve every artifact. The canonical mutation will mark
  // only real dependents stale; unaffected work stays reusable.
  const handlePartialReset = useCallback((fromStep) => {
    log.step(`openNonLinearEdit at step ${fromStep} (${STEP_NAMES_VI[fromStep]})`)
    if (fromStep <= 1) audienceEntryFiredRef.current = false
    if (fromStep <= 3) setupEntryFiredRef.current = false
    if (fromStep <= 5) reportEntryFiredRef.current = false
    pushWorkspaceEvent(
      `Đã mở chỉnh sửa lại bước ${STEP_NAMES_VI[fromStep]}; ` +
      `giữ nguyên dữ liệu khác cho đến khi thay đổi được xác nhận`
    )
    setStepStatuses(prev => prev.map((status, index) => (
      index === fromStep ? 'pending' : status
    )))
    setCurrentStep(fromStep)
  }, [pushWorkspaceEvent])

  const resetLocalCampaign = useCallback(() => {
    audienceEntryFiredRef.current = false
    setupEntryFiredRef.current = false
    reportEntryFiredRef.current = false
    setFormState(initialState)
    setStepStatuses(STEPS.map(() => 'pending'))
    setCanonicalWorkspace(null)
    setRecomputePlan(null)
    setWorkspaceEvents([])
    setCurrentStep(0)
  }, [])

  const handleReset = useCallback(() => {
    resetLocalCampaign()
    AgentAPI.newSession()
    AgentAPI.getWorkspace()
  }, [resetLocalCampaign])

  const handleNewChat = useCallback(async () => {
    const deleted = await newChat()
    if (!deleted) return
    resetLocalCampaign()
    bootedRef.current = false
    setExperienceMode(null)
    setAutopilotSummary(null)
    setModeSelectionError('')
  }, [resetLocalCampaign, newChat])

  // Listen for agent:reset event from BlockRenderer ActionResetBlock
  useEffect(() => {
    const handler = () => handleReset()
    window.addEventListener('agent:reset', handler)
    return () => window.removeEventListener('agent:reset', handler)
  }, [handleReset])

  // ── Demo: listen for demo:set_form_field to programmatically change fields ─
  useEffect(() => {
    const handler = (e) => {
      const { path, value } = e.detail || {}
      if (!path) return
      const [section, key] = path.split('.')
      if (section && key) {
        log.workspace(`demo:set_form_field → ${section}.${key} = ${value}`)
        setFormStateWithEvents(prev => ({
          ...prev,
          [section]: { ...prev[section], [key]: value }
        }))
      }
    }
    window.addEventListener('demo:set_form_field', handler)
    return () => window.removeEventListener('demo:set_form_field', handler)
  }, [setFormStateWithEvents])

  // ── Demo: listen for demo:new_chat to reset state for live run ─────────
  useEffect(() => {
    const handler = () => {
      log.step('demo:new_chat → resetting for demo live run')
      handleNewChat()
    }
    window.addEventListener('demo:new_chat', handler)
    return () => window.removeEventListener('demo:new_chat', handler)
  }, [handleNewChat])

  // ── Demo: listen for demo:inject_creatives to add pre-generated assets ──
  useEffect(() => {
    const handler = (e) => {
      const { creatives } = e.detail || {}
      if (!creatives?.length) return
      setFormStateWithEvents(prev => {
        const existing = prev.creative?.files || []
        const existingIds = new Set(existing.map(f => f.id))
        const toAdd = creatives.filter(c => !existingIds.has(c.id))
        if (!toAdd.length) return prev
        log.workspace(`demo:inject_creatives → adding ${toAdd.length} pre-generated creatives`)
        return {
          ...prev,
          creative: {
            ...prev.creative,
            files: [...existing, ...toAdd],
            uploaded: true,
          },
        }
      })
    }
    window.addEventListener('demo:inject_creatives', handler)
    return () => window.removeEventListener('demo:inject_creatives', handler)
  }, [setFormStateWithEvents])

  // ── Demo: pick 2 random recommended zones ─────────────────────────────────
  useEffect(() => {
    const handler = (e) => {
      const count = e.detail?.count || 2
      setFormStateWithEvents(prev => {
        const recoZones = prev.setup?.recoZones || []
        const available = recoZones.filter(z => !z.conflict)
        const shuffled = [...available].sort(() => Math.random() - 0.5)
        const chosen = shuffled.slice(0, count).map(z => z.id)
        log.workspace(`demo:select_reco_zones → picked [${chosen.join(', ')}]`)
        window.dispatchEvent(new CustomEvent('demo:reco_zones_selected', { detail: { zoneIds: chosen } }))
        return { ...prev, setup: { ...prev.setup, selectedZoneIds: chosen, created: false } }
      })
    }
    window.addEventListener('demo:select_reco_zones', handler)
    return () => window.removeEventListener('demo:select_reco_zones', handler)
  }, [setFormStateWithEvents])

  // ── Demo: assign creatives to selected zones by format map ────────────────
  useEffect(() => {
    const handler = () => {
      setFormStateWithEvents(prev => {
        const selectedZoneIds = prev.setup?.selectedZoneIds || []
        const files = prev.creative?.files || []
        const assignments = { ...(prev.setup?.assignments || {}) }
        selectedZoneIds.forEach(zoneId => {
          const formatId = ZONE_FORMAT_MAP[zoneId]  // null = box
          let matched
          if (formatId === null || formatId === undefined) {
            // Box: match the AI-generated file (name starts with "ai-zuma-box")
            matched = files.find(f => /^ai-zuma-box/i.test(f.name))
          } else {
            // Non-box: match by format filename
            matched = files.find(f => f.name === `${formatId}.png` || f.formatId === formatId)
          }
          if (matched) assignments[zoneId] = matched.id
        })
        log.workspace(`demo:assign_creatives → assignments:`, assignments)
        window.dispatchEvent(new CustomEvent('demo:creatives_assigned', { detail: { assignments } }))
        return { ...prev, setup: { ...prev.setup, assignments } }
      })
    }
    window.addEventListener('demo:assign_creatives', handler)
    return () => window.removeEventListener('demo:assign_creatives', handler)
  }, [setFormStateWithEvents])

  // ── Track user interaction to hide Demo button ─────────────────────────
  // Once user sends ANY message (not boot), hide the demo button permanently
  useEffect(() => {
    if (hasUserStarted) return
    const userMsgs = messages.filter(m => m.role === 'user')
    if (userMsgs.length > 0) {
      setHasUserStarted(true)
    }
  }, [messages, hasUserStarted])

  // Listen for agent:workspace_confirm — user clicked Đồng ý on a proposal block
  useEffect(() => {
    const handler = async (e) => {
      log.event('agent:workspace_confirm received', e.detail)
      if (e.detail?.patch) {
        handleWorkspaceUpdate(e.detail.patch)
        const originalField = e.detail.patch.field || ''
        const target = workspacePatchTarget(originalField)
        // Persist every typed proposal, including targeting, creative files,
        // placements and assignments. The previous step-only map silently
        // skipped those proposal classes.
        const persisted = e.detail.patch.proposal_id
          ? await AgentAPI.approveWorkspaceProposal(e.detail.patch.proposal_id)
          : await AgentAPI.commitWorkspace(originalField, e.detail.patch.value)
        log.workspace(`persistWorkspace(${originalField}) →`, persisted?.ok ? 'ok' : 'failed')
        if (e.detail.patch.proposal_id) {
          window.dispatchEvent(new CustomEvent('agent:workspace_proposal_result', {
            detail: {
              proposal_id: e.detail.patch.proposal_id,
              status: persisted?.ok ? 'approved' : 'failed',
            },
          }))
        }
        if (!persisted?.ok || target.step == null) return

        // In Autopilot, chat is a control surface for the canonical workspace.
        // Applying a proposal must not also launch the Guided step machine (and
        // its proactive audience request) behind the operator's back. The run
        // begins only from the explicit "Bắt đầu Autopilot" action above.
        if (experienceMode === 'autopilot') {
          window.dispatchEvent(new CustomEvent('agent:inject_message', {
            detail: {
              id: `autopilot_update_${Date.now()}`,
              role: 'assistant',
              content: '✅ Đã cập nhật workspace. Autopilot sẽ dùng thay đổi này khi bạn bấm **Bắt đầu Autopilot**.',
              blocks: [],
              timestamp: new Date().toISOString(),
              metadata: { tool: 'workspace_confirmed', model: 'none', step: target.step },
            }
          }))
          return
        }

        const stepNum = target.step
        if (stepStatuses[stepNum] !== 'done' && stepStatuses[stepNum] !== 'stale') {
          // Setup has multiple sub-phases and is completed only after safe order creation.
          if (stepNum === 3) return
          const rawValue = e.detail.patch.value
          const patchValue = typeof rawValue === 'string'
            ? (() => { try { return JSON.parse(rawValue) } catch { return {} } })()
            : (rawValue || {})
          const confirmMessages = {
            0: '✅ Brief đã được lưu! Em sẽ chuyển sang bước **Audience** để gợi ý segments phù hợp.',
            1: `✅ Audience đã xác nhận! ${(patchValue.attrs || []).length || 'Các'} segments được áp dụng — em sẽ chuyển sang bước **Creative**.`,
            2: '✅ Creative đã xác nhận! Em sẽ chuyển sang bước **Setup Camp**.',
          }
          window.dispatchEvent(new CustomEvent('agent:inject_message', {
            detail: {
              id: `confirm_${stepNum}_${Date.now()}`,
              role: 'assistant',
              content: confirmMessages[stepNum] || '✅ Đã áp dụng thay đổi workspace.',
              blocks: [],
              timestamp: new Date().toISOString(),
              metadata: { tool: 'workspace_confirmed', model: 'none', step: stepNum },
            }
          }))
          setTimeout(() => markStepDone(stepNum), 700)
        }
      }
    }
    window.addEventListener('agent:workspace_confirm', handler)
    return () => window.removeEventListener('agent:workspace_confirm', handler)
  }, [handleWorkspaceUpdate, stepStatuses, markStepDone, experienceMode])

  // Listen for agent:setup_zones_confirmed — fired by WorkspaceProposalBlock when user
  // clicks "✅ Duyệt các zones này". This advances the setup sub-phase to 'assign' using
  // the CURRENT formState.setup selection (not the stale proposal value).
  useEffect(() => {
    const handler = async (event) => {
      const proposalId = event.detail?.proposal_id
      if (proposalId) {
        await AgentAPI.rejectWorkspaceProposal(
          proposalId, 'operator_changed_zone_selection_before_confirmation'
        )
      }
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
      if (e.detail?.proposal_id) {
        AgentAPI.rejectWorkspaceProposal(e.detail.proposal_id)
      }
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

  const canApprove = canApproveWorkflowStep(currentStep, formState, stepStatuses)

  const openFirstRecomputeStep = useCallback(() => {
    const step = firstRecomputeStep(recomputePlan)
    if (step != null && step >= 0 && !busy) {
      setCurrentStep(step)
      workspaceRef.current?.flash?.()
    }
  }, [recomputePlan, busy])

  const openGuidedStep = useCallback(async (step) => {
    const switched = await selectExperience('guided')
    if (!switched) return
    setCurrentStep(step)
    setActiveTab('workspace')
    requestAnimationFrame(() => workspaceRef.current?.flash?.())
  }, [selectExperience])

  // ── isMobile helper (used for conditional inline styles) ──────────────────
  // Read at render-time. Tailwind md: breakpoints handle the class-based
  // layout switching automatically on resize.

  if (!experienceMode) {
    return (
      <ExperienceSelector
        onSelect={selectExperience}
        busy={modeSelectionBusy}
        error={modeSelectionError}
      />
    )
  }

  return (
    <DemoProvider
      busy={busy}
      messages={messages}
      onSendMessage={sendMessage}
      onApprove={handleApprove}
      onRequestTab={setActiveTab}
      activeTab={activeTab}
      onActiveChange={(active) => { isDemoActiveRef.current = active }}
    >
    <div className="flex h-screen flex-col overflow-hidden bg-gradient-to-br from-slate-50 to-brand-50/30 pb-[calc(4rem+env(safe-area-inset-bottom))] md:pb-0">
      <TopBar
        onReset={handleReset}
        onNewChat={handleNewChat}
        showDemo={!hasUserStarted}
      />

      <div className="hidden flex-shrink-0 md:block">
        <ModeSwitcher
          value={experienceMode}
          onChange={selectExperience}
          busy={modeSelectionBusy}
          error={modeSelectionError}
          autopilotSummary={autopilotSummary}
        />
      </div>

      {workspaceConflict && (
        <div className="flex items-center justify-between gap-3 border-b border-amber-300 bg-amber-50 px-4 py-2 text-sm text-amber-900">
          <span>
            Workspace trên máy chủ đã thay đổi (phiên bản {workspaceConflict.actual_revision}).
            Tải lại để tránh ghi đè dữ liệu mới hơn.
          </span>
          <button
            type="button"
            onClick={reloadCanonicalWorkspace}
            className="shrink-0 rounded-lg bg-amber-900 px-3 py-1.5 font-semibold text-white hover:bg-amber-800"
          >
            Tải lại workspace
          </button>
        </div>
      )}

      {/* Mobile-only Tab Bar — hidden on desktop (md:hidden) */}
      <div className="md:hidden flex-shrink-0">
        <TabBar
          activeTab={activeTab}
          onTabChange={setActiveTab}
          chatHasNew={chatHasNew}
          workspaceHasNew={workspaceHasNew}
          experienceMode={experienceMode}
        />
      </div>

      {/*
        Mobile layout: flex-col, one pane visible at a time via activeTab.
        Desktop layout: flex-row (md:flex-row), Chat on LEFT (42%), Workspace on RIGHT.
        md:flex on each pane overrides the mobile `hidden` so both show on desktop.
      */}
      <main ref={mainRef} className="flex flex-1 min-h-0 overflow-hidden flex-col md:flex-row">

        {/* ── Workspace Pane ──────────────────────────────────────────
            Mobile: shown when activeTab==='workspace', hidden otherwise
            Desktop: RIGHT side, flex-1 (always visible)             */}
        <div id="guided-canvas" role="tabpanel" aria-label="Quy trình hướng dẫn" data-mode-canvas="guided" data-demo="workspace-pane" className={`
          md:order-2 flex flex-col min-w-0 overflow-hidden bg-white
          md:flex-1 md:h-full
          ${experienceMode === 'guided' && activeTab === 'workspace' ? 'flex-1' : 'hidden'}
          ${experienceMode === 'guided' ? 'md:flex' : 'md:hidden'}
        `}>
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
            recomputePlan={recomputePlan}
            workspaceRevision={canonicalWorkspace?.revision}
            onOpenRecompute={openFirstRecomputeStep}
            autopilotMode={false}
          />
        </div>

        {/* Autopilot is a sibling canvas, not a banner above the workspace.
            It stays mounted while hidden so run state and the event stream survive mode switches. */}
        <div id="autopilot-canvas" role="tabpanel" aria-label="Campaign Autopilot" data-mode-canvas="autopilot" className={`
          md:order-2 min-w-0 overflow-hidden bg-slate-50 md:flex-1 md:h-full
          ${experienceMode === 'autopilot' && activeTab === 'autopilot' ? 'flex flex-1' : 'hidden'}
          ${experienceMode === 'autopilot' ? 'md:flex' : 'md:hidden'}
        `}>
          <AutopilotPanel
            brief={formState.brief}
            onWorkspaceRefresh={() => AgentAPI.getWorkspace()}
            onOpenBrief={() => openGuidedStep(0)}
            onOpenCreative={() => openGuidedStep(2)}
            onStatusChange={setAutopilotSummary}
          />
        </div>

        {/* ── Chat Pane ─────────────────────────────────────────────
            Mobile: shown when activeTab==='chat', hidden otherwise
            Desktop: LEFT side, flex-[0_0_42%] (always visible)     */}
        <div data-demo="chat-pane" className={`
          md:order-1 flex flex-col min-w-0 overflow-hidden
          bg-white/60 backdrop-blur-sm border-border
          md:border-t-0 md:border-r
          md:flex-[0_0_42%] md:h-full
          ${activeTab === 'chat' ? 'flex-1' : 'hidden md:flex'}
        `}>
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

      </main>

      <div className="fixed inset-x-0 bottom-0 z-30 md:hidden">
        <ModeSwitcher
          value={experienceMode}
          onChange={selectExperience}
          busy={modeSelectionBusy}
          error={modeSelectionError}
          mobile
          autopilotSummary={autopilotSummary}
        />
      </div>
    </div>
    </DemoProvider>
  )
}
