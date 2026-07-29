import { useState, useCallback, useRef, useEffect } from 'react'
import { AgentAPI, AGENT_SCENARIOS, fetchDmpAttributes, matchDmpByKeywords, extractTargetingKeywords, extractTargetingMap, prepareCreativeFiles } from '@/api/agentApi'
import { creativeReviewState } from '@/lib/creativeIntel'
import { generateId } from '@/lib/utils'
import log from '@/lib/logger'
import { responseAllowsAdvance } from '@/lib/workflowValidation'


function userMessage(text) {
  return {
    id: generateId(),
    role: 'user',
    content: text,
    blocks: [],
    timestamp: new Date().toISOString(),
  }
}

function thinkingMessage() {
  return {
    id: generateId(),
    role: 'thinking',
    content: '',
    blocks: [],
    timestamp: new Date().toISOString(),
  }
}

export function useChat({
  currentStep,
  formState,
  stepStatuses,
  workspaceEvents,
  onClearWorkspaceEvents,
  onStepApproved,
  onAutoSelectAudience,
  onWorkspaceUpdate,
  onCreativePrepared,
  onSnapshotRequest,   // () => { formState, stepStatuses, currentStep } — called before each send
  onRestoreSnapshot,  // (snapshot) => void — called on retry to revert external state
}) {

  const [messages, setMessages] = useState([])
  const [busy, setBusy] = useState(false)
  const thinkingIdRef = useRef(null)
  // Prevents double-boot from React StrictMode double-mount in dev
  const bootedRef = useRef(false)
  // Snapshot for retry: stores { text, messagesBefore } of the last sent message
  const lastSentRef = useRef(null)

  const addMessage = useCallback((msg) => {
    setMessages(prev => [...prev, msg])
    return msg.id
  }, [])

  const startThinking = useCallback(() => {
    const thinking = thinkingMessage()
    thinkingIdRef.current = thinking.id
    setMessages(prev => [...prev, thinking])
    return thinking.id
  }, [])

  const stopThinking = useCallback((response) => {
    const id = thinkingIdRef.current
    if (id) {
      setMessages(prev => prev.map(m => m.id === id ? response : m))
      thinkingIdRef.current = null
    } else {
      setMessages(prev => [...prev, response])
    }
  }, [])

  const boot = useCallback(async (experienceMode = 'guided') => {
    if (bootedRef.current) return
    bootedRef.current = true
    setBusy(true)
    log.chat('boot → start')
    const response = await AgentAPI.boot(experienceMode)
    log.chat('boot ← done', { content_preview: response?.content?.slice(0, 100) })
    setMessages([response])
    setBusy(false)
  }, [])

  const hydrateMessages = useCallback((storedMessages = []) => {
    const restored = Array.isArray(storedMessages) ? storedMessages : []
    bootedRef.current = restored.length > 0
    thinkingIdRef.current = null
    lastSentRef.current = null
    setMessages(restored)
  }, [])

  // Listen for externally-injected assistant messages (e.g. audience-entry recommendation from App.jsx)
  useEffect(() => {
    const handler = (e) => {
      if (e.detail) {
        log.chat('agent:inject_message received', { tool: e.detail.metadata?.tool })
        setMessages(prev => [...prev, e.detail])
      }
    }
    window.addEventListener('agent:inject_message', handler)
    return () => window.removeEventListener('agent:inject_message', handler)
  }, [])

  // Start a new owned conversation. The previous campaign remains available
  // in History instead of being deleted from MongoDB.
  const newChat = useCallback(async (options = {}) => {
    setBusy(true)
    try {
      const context = await AgentAPI.createConversation(options)
      bootedRef.current = false
      setMessages([])
      lastSentRef.current = null
      log.chat('newChat → persistent conversation created', {
        conversation_id: context?.conversation_id,
      })
      setBusy(false)
      return context
    } catch (error) {
      const response = {
        id: generateId(), role: 'error', blocks: [],
        content: '⚠️ Không thể tạo chiến dịch mới. Workspace hiện tại vẫn được giữ nguyên; hãy thử lại khi kết nối phục hồi.',
        timestamp: new Date().toISOString(),
        metadata: { tool: 'conversation_create_failed', model: 'none' },
      }
      setMessages(prev => [...prev, response])
      setBusy(false)
      return null
    }
  }, [])


  const sendMessage = useCallback(async (text, _isRetry = false) => {
    if (busy || !text.trim()) return
    setBusy(true)

    // Snapshot FULL state BEFORE send (messages + external formState/step)
    if (!_isRetry) {
      const externalSnapshot = onSnapshotRequest?.() ?? null
      setMessages(prev => {
        lastSentRef.current = { text, messagesBefore: prev, externalSnapshot }
        return prev
      })
    }

    addMessage(userMessage(text))
    startThinking()

    log.chat('sendMessage →', {
      text: text.slice(0, 120),
      step: currentStep,
      workspace_events: workspaceEvents,
      confirmed_steps: (stepStatuses || []).reduce((a, s, i) => { if (s === 'done') a.push(i); return a }, []),
      formState_summary: {
        brand: formState?.brief?.brand,
        segment_count: formState?.segment?.attrs?.length,
        files_count: formState?.creative?.files?.length,
      },
    })

    // Send workspace state + pending events with every chat message
    // For step 5 (Report), include the active report tab in formData
    const chatPayload = {
      session_id: window.__AGENT_SESSION_ID__,
      step: currentStep,
      message: text,
      workspace: {
        brief: formState?.brief || {},
        segment: {
          attrs: (formState?.segment?.attrs || []).map(a => ({
            name: a.name || a.fullLabel || '',
            type: a.type || '',
            category: a.category || '',
            est_size: a.est_size || 0,
          })),
          size: formState?.segment?.size || 0,
        },
        creative: {
          files: (formState?.creative?.files || []).map(f => ({
            name: f.name, type: f.type, size: f.size,
          })),
        },
        setup: {
          selectedZoneIds: formState?.setup?.selectedZoneIds || [],
          phase: formState?.setup?.phase || 'zones',
        },
      },
      confirmed_steps: (stepStatuses || []).reduce((a, s, i) => { if (s === 'done') a.push(i); return a }, []),
      workspace_events: workspaceEvents || [],
    }

    // Include activeReportTab for step 5 so backend routes to correct analysis
    if (currentStep === 5 && formState?.report?.activeTab) {
      chatPayload.formData = { activeReportTab: formState.report.activeTab }
    }

    let response = await AgentAPI.chat(
      text,
      currentStep,
      formState,
      stepStatuses,
      workspaceEvents,
    )

    // ── Error guard: null response = timeout / network / HTTP error ───────────
    if (!response) {
      const errMsg = {
        id: generateId(),
        role: 'error',
        content: '⚠️ Yêu cầu thất bại hoặc quá thời gian chờ (>3 phút). Anh/chị thử lại nhé!',
        blocks: [],
        timestamp: new Date().toISOString(),
        metadata: { tool: 'error', model: 'none', step: currentStep },
      }
      stopThinking(errMsg)
      setBusy(false)
      onClearWorkspaceEvents?.()
      log.error('sendMessage: null response → showing error bubble')
      return
    }

    log.chat('sendMessage ←', {
      tool: response?.metadata?.tool,
      content_preview: response?.content?.slice(0, 200),
      blocks: response?.blocks?.map(b => b.type),
      workspace_update: response?.workspace_update,
    })

    // Guard: if response came back empty (backend tool-call bug), show fallback
    if (response && !response.content && (!response.blocks || response.blocks.length === 0)) {
      log.error('empty response received — showing fallback', { tool: response?.metadata?.tool })
      response = {
        ...response,
        content: '⚠️ Em gặp sự cố khi xử lý yêu cầu này. Anh/Chị thử lại hoặc diễn đạt khác nhé!',
      }
    }


    stopThinking(response)
    setBusy(false)

    // Drain workspace events — they've been sent
    onClearWorkspaceEvents?.()
    log.workspace('workspace_events drained (sent to backend)')

    // ── Pre-populate workspace form when agent proposes a change ─────────────
    // When a workspace_proposal block appears, apply the value immediately so
    // the user sees the form populated right away and can edit before confirming.
    // The "Đồng ý" button will only advance the step (data is already in formState).
    if (onWorkspaceUpdate) {
      const proposals = (response?.blocks || []).filter(b => b.type === 'workspace_proposal' && b.changes?.field)
      for (const block of proposals) {
        log.workspace('workspace_proposal block → pre-populating form', block.changes)
        onWorkspaceUpdate(block.changes)
      }
    }

    // Handle workspace_update — agent confirmed a change (pending proposal applied by backend)
    if (response?.workspace_update && onWorkspaceUpdate) {
      log.workspace('applying workspace_update from response', response.workspace_update)
      onWorkspaceUpdate(response.workspace_update)

      // Auto-advance step when the updated field belongs to the current step
      // so the user doesn't have to press "Đồng ý & Tiếp tục" manually after chat confirm
      const STEP_PRIMARY_FIELDS = { 0: 'brief', 1: 'segment', 2: 'creative', 3: 'setup' }
      const updatedField = response.workspace_update.field?.split('.')?.[0]  // 'brief.brand' → 'brief'
      const isCurrentStepField = STEP_PRIMARY_FIELDS[currentStep] === updatedField
      const alreadyDone = (stepStatuses || [])[currentStep] === 'done'
      if (isCurrentStepField && !alreadyDone) {
        log.step(`workspace_update for step ${currentStep} field "${updatedField}" → auto-advance`)
        setTimeout(() => onStepApproved?.(currentStep), 700)
      }
    }

    // When AI returns targeting_autopick: extract the targeting map and store it.
    if (response?.metadata?.tool === 'targeting_autopick' && onAutoSelectAudience) {
      try {
        const targetingMap = extractTargetingMap(response.blocks || [])
        if (Object.keys(targetingMap).length) {
          log.chat('targeting_autopick → auto-select audience', targetingMap)
          onAutoSelectAudience([], targetingMap)
        }
      } catch (e) {
        log.error('targeting_autopick parse failed', e.message)
      }
    }
  }, [busy, currentStep, formState, stepStatuses, workspaceEvents, addMessage, startThinking, stopThinking, onClearWorkspaceEvents, onAutoSelectAudience, onWorkspaceUpdate])

  // Retry: restore full state (messages + formState + step) to before last send, then re-send
  const retryLastMessage = useCallback(() => {
    if (!lastSentRef.current || busy) return
    const { text, messagesBefore, externalSnapshot } = lastSentRef.current
    lastSentRef.current = null
    // 1. Revert messages to before the user sent
    setMessages(messagesBefore)
    // 2. Revert external state (formState, stepStatuses, currentStep) if snapshot available
    if (externalSnapshot && onRestoreSnapshot) {
      onRestoreSnapshot(externalSnapshot)
    }
    // 3. Re-send (small delay so state settles before send)
    setTimeout(() => sendMessage(text, true), 50)
  }, [busy, sendMessage, onRestoreSnapshot])



  const STEP_LABELS = ['Brief', 'Audience', 'Creative', 'Setup', 'Result', 'Report', 'Email']

  const approveStep = useCallback(async (stepIndex, stepData, options = {}) => {
    if (busy) return { response: null, shouldAdvance: false }
    const silent = options.silent === true
    const markApproved = options.markApproved !== false
    const persistReadyCreative = options.persistReadyCreative === true
    const completeReadyCreative = options.completeReadyCreative === true
    setBusy(true)
    if (!silent) startThinking()

    log.step(`approveStep ${stepIndex} (${STEP_LABELS[stepIndex] ?? '?'}) → start`, {
      stepData_keys: Object.keys(stepData || {}),
      attrs_count: stepData?.attrs?.length,
      files_count: stepData?.creative?.files?.length,
    })

    let response
    let shouldAdvance = true
    switch (stepIndex) {
      // Step 0 — Brief
      case 0:
        response = await AgentAPI.approveBrief(stepData.brief)
        shouldAdvance = responseAllowsAdvance(response)
        break

      // Step 1 — Audience (NEW: was step 2)
      case 1:
        response = await AgentAPI.approveAudience({
          attrs: stepData.attrs || [],
          size: stepData.size || 0,
          targeting: stepData.targeting || {},
        })
        shouldAdvance = responseAllowsAdvance(response)
        break

      case 2: {
        try {
          const currentFiles = stepData.creative?.files || []
          if (creativeReviewState(currentFiles) === 'ready') {
            // Guided mode reaches this state only after the authoritative
            // creative input has already been committed. The Autopilot repair
            // editor is different: a manual verdict can make its local file
            // ready while the waiting prepare_creatives task still references
            // the earlier proposal. Persisting the reviewed file set creates a
            // creative revision, allowing Autopilot to recheck that input gate.
            if (persistReadyCreative) {
              response = await AgentAPI.approveCreative(stepData.creative)
              shouldAdvance = responseAllowsAdvance(response)
              if (!shouldAdvance) break
            }
            if (markApproved) await AgentAPI.confirmWorkflowStep(2)
            response = response || {
              id: generateId(),
              role: 'assistant',
              content: '✅ Kết quả phân tích creative đã được xác nhận. Mời Anh/Chị tiếp tục sang Setup Camp.',
              blocks: [],
              timestamp: new Date().toISOString(),
              metadata: { tool: 'creative_review_confirmed', model: 'none', step: 2 },
              suggestions: [],
            }
            shouldAdvance = true
            break
          }
          const prepared = await prepareCreativeFiles(
            currentFiles,
            files => onCreativePrepared?.(files),
          )
          onCreativePrepared?.(prepared)
          const reviewFiles = prepared.filter(file => file.analysisStatus === 'needs_review')
          if (reviewFiles.length) {
            shouldAdvance = false
            response = {
              id: generateId(),
              role: 'assistant',
              content: `⚠ **${reviewFiles.length} creative cần duyệt thủ công.** Xem lý do ở workspace, nhập lý do phê duyệt rồi xác nhận lại.`,
              blocks: [],
              timestamp: new Date().toISOString(),
              metadata: { tool: 'creative_blocked', model: 'none', step: 2 },
              suggestions: [],
            }
          } else {
            if (completeReadyCreative) {
              response = await AgentAPI.approveCreative({
                ...(stepData.creative || {}),
                files: prepared,
                uploaded: prepared.length > 0,
              })
              shouldAdvance = responseAllowsAdvance(response)
              break
            }
            // The authoritative file set was committed before analysis.
            // Recommitting it now would invalidate the fresh verdict artifact.
            response = {
              id: generateId(),
              role: 'assistant',
              content: markApproved
                ? `✅ Đã phân tích xong ${prepared.length} creative. Anh/Chị hãy đọc kết quả trong workspace, sau đó bấm “Xác nhận & sang Setup” khi đã sẵn sàng.`
                : `✅ ${prepared.length} creative đã được phân tích. Anh/Chị hãy đọc kết quả, sau đó bấm “Lưu & quay lại Autopilot” khi đã sẵn sàng.`,
              blocks: [],
              timestamp: new Date().toISOString(),
              metadata: { tool: 'creative_approved', model: 'none', step: 2 },
              suggestions: [],
            }
            // Both modes pause after the first analysis pass so the operator
            // can read an auto-approved result instead of being fast-forwarded.
            // A second explicit confirmation persists the ready file set.
            shouldAdvance = false
          }
        } catch (error) {
          shouldAdvance = false
          response = {
            id: generateId(),
            role: 'assistant',
            content: `⚠ Không thể hoàn tất phân tích creative: ${error.message}`,
            blocks: [],
            timestamp: new Date().toISOString(),
            metadata: { tool: 'creative_analysis_error', model: 'none', step: 2 },
            suggestions: [],
          }
        }
        break
      }


      // Step 3 — Setup: order was already created by ConfirmPhase.handleCreate (phase=2).
      case 3:
        response = {
          id: generateId(),
          role: 'assistant',
          content: '✅ Chiến dịch đã được tạo thành công trên nền tảng quảng cáo! Anh/Chị xem tổng kết ở bước Kết quả bên phải.',
          blocks: [{ type: 'info', text: '🎉 Order đã được khởi tạo. Chuyển sang bước Kết quả...' }],
          timestamp: new Date().toISOString(),
          metadata: { tool: 'order_create', model: 'minimax', step: 3 },
        }
        break

      // Step 4 — Result
      case 4:
        response = await AgentAPI.getResult()
        shouldAdvance = responseAllowsAdvance(response)
        break

      // Steps 5-6 — Report / Email
      case 5: {
        // Report: use the real backend (report_entry triggers generation)
        response = await AgentAPI.reportEntry()
        if (!response) {
          response = {
            id: generateId(),
            role: 'assistant',
            content: '📊 Đang chuẩn bị báo cáo... Vui lòng xem panel phải.',
            blocks: [],
            timestamp: new Date().toISOString(),
            metadata: { tool: 'report_entry', model: 'none', step: 5 },
          }
        }
        shouldAdvance = responseAllowsAdvance(response)
        break
      }
      case 6:
        response = await AGENT_SCENARIOS.sendEmail(stepData.brief, stepData.campaigns)
        break

      default:
        response = {
          id: generateId(),
          role: 'assistant',
          content: `✅ Bước ${stepIndex + 1} hoàn tất!`,
          blocks: [],
          timestamp: new Date().toISOString(),
          metadata: { model: 'minimax' },
        }
    }

    if (!silent) stopThinking(response)
    log.step(`approveStep ${stepIndex} ← done`, {
      tool: response?.metadata?.tool,
      content_preview: response?.content?.slice(0, 150),
      blocks: response?.blocks?.map(b => b.type),
    })
    setBusy(false)
    if (shouldAdvance && markApproved && onStepApproved) onStepApproved(stepIndex)
    return { response, shouldAdvance }
  }, [busy, startThinking, stopThinking, onStepApproved, onCreativePrepared])

  return {
    messages, busy, boot, hydrateMessages, newChat, sendMessage, approveStep,
    retryLastMessage, canRetry: !!lastSentRef.current,
  }
}
