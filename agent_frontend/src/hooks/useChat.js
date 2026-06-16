import { useState, useCallback, useRef, useEffect } from 'react'
import { AgentAPI, AGENT_SCENARIOS, fetchDmpAttributes, matchDmpByKeywords, extractTargetingKeywords, extractTargetingMap } from '@/api/agentApi'
import { generateId } from '@/lib/utils'
import log from '@/lib/logger'


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

  const boot = useCallback(async () => {
    if (bootedRef.current) return
    bootedRef.current = true
    setBusy(true)
    log.chat('boot → start')
    const response = await AgentAPI.boot()
    log.chat('boot ← done', { content_preview: response?.content?.slice(0, 100) })
    setMessages([response])
    setBusy(false)
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

  // Full reset: clear messages and re-run boot greeting
  const newChat = useCallback(async () => {
    bootedRef.current = false
    setMessages([])
    setBusy(true)
    log.chat('newChat → reset and re-boot')
    const response = await AgentAPI.boot()
    setMessages([response])
    setBusy(false)
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
    let response = await AgentAPI.chat(
      text,
      currentStep,
      formState,
      stepStatuses,
      workspaceEvents,
    )

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

  const approveStep = useCallback(async (stepIndex, stepData) => {
    if (busy) return
    setBusy(true)
    startThinking()

    log.step(`approveStep ${stepIndex} (${STEP_LABELS[stepIndex] ?? '?'}) → start`, {
      stepData_keys: Object.keys(stepData || {}),
      attrs_count: stepData?.attrs?.length,
      files_count: stepData?.creative?.files?.length,
    })

    let response
    switch (stepIndex) {
      // Step 0 — Brief
      case 0:
        response = await AgentAPI.approveBrief(stepData.brief)
        break

      // Step 1 — Audience (NEW: was step 2)
      case 1:
        response = await AgentAPI.approveAudience({
          attrs: stepData.attrs || [],
          size: stepData.size || 0,
        })
        break

      // Step 2 — Creative (NEW: was step 1)
      case 2:
        response = await AgentAPI.approveCreative(stepData.creative)
        break

      // Step 3 — Setup: order was already created by ConfirmPhase.handleCreate (phase=2).
      case 3:
        response = {
          id: generateId(),
          role: 'assistant',
          content: '✅ Chiến dịch đã được tạo thành công trên AdsPilot! Anh/Chị xem tổng kết ở bước Kết quả bên phải.',
          blocks: [{ type: 'info', text: '🎉 Order đã được khởi tạo. Chuyển sang bước Kết quả...' }],
          timestamp: new Date().toISOString(),
          metadata: { tool: 'order_create', model: 'minimax', step: 3 },
        }
        break

      // Step 4 — Result
      case 4:
        response = await AgentAPI.getResult()
        break

      // Steps 5-6 — Report / Email (mock)
      case 5:
        response = await AGENT_SCENARIOS.runReport(stepData.brief)
        break
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

    stopThinking(response)
    log.step(`approveStep ${stepIndex} ← done`, {
      tool: response?.metadata?.tool,
      content_preview: response?.content?.slice(0, 150),
      blocks: response?.blocks?.map(b => b.type),
    })
    setBusy(false)
    if (onStepApproved) onStepApproved(stepIndex)
  }, [busy, startThinking, stopThinking, onStepApproved])

  return { messages, busy, boot, newChat, sendMessage, approveStep, retryLastMessage, canRetry: !!lastSentRef.current }
}

