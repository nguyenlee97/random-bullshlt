import { useState, useCallback, useRef } from 'react'
import { AgentAPI, AGENT_SCENARIOS, fetchDmpAttributes, matchDmpByKeywords, extractTargetingKeywords, extractTargetingMap } from '@/api/agentApi'

import { generateId } from '@/lib/utils'


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

export function useChat({ currentStep, formState, onStepApproved, onAutoSelectAudience }) {

  const [messages, setMessages] = useState([])
  const [busy, setBusy] = useState(false)
  const thinkingIdRef = useRef(null)
  // Prevents double-boot from React StrictMode double-mount in dev
  const bootedRef = useRef(false)

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
    const response = await AgentAPI.boot()
    setMessages([response])
    setBusy(false)
  }, [])

  // Full reset: clear messages and re-run boot greeting
  const newChat = useCallback(async () => {
    bootedRef.current = false
    setMessages([])
    setBusy(true)
    const response = await AgentAPI.boot()
    setMessages([response])
    setBusy(false)
  }, [])

  const sendMessage = useCallback(async (text) => {
    if (busy || !text.trim()) return
    setBusy(true)
    addMessage(userMessage(text))
    startThinking()
    const response = await AgentAPI.chat(text, currentStep, formState)
    stopThinking(response)
    setBusy(false)

    // When AI returns targeting_autopick: extract the targeting map and store it.
    // Do NOT auto-select DMP segments — those are chosen manually from the panel.
    if (response?.metadata?.tool === 'targeting_autopick' && onAutoSelectAudience) {
      try {
        const targetingMap = extractTargetingMap(response.blocks || [])
        if (Object.keys(targetingMap).length) {
          onAutoSelectAudience([], targetingMap) // empty segments = don't touch DMP selection
        }
      } catch (e) {
        console.warn('[autoselect] failed:', e.message)
      }
    }
  }, [busy, currentStep, formState, addMessage, startThinking, stopThinking, onAutoSelectAudience])



  const approveStep = useCallback(async (stepIndex, stepData) => {
    if (busy) return
    setBusy(true)
    startThinking()

    let response
    switch (stepIndex) {
      // Step 0 — Brief
      case 0:
        response = await AgentAPI.approveBrief(stepData.brief)
        break

      // Step 1 — Creative
      case 1:
        response = await AgentAPI.approveCreative(stepData.creative)
        break

      // Step 2 — Audience (DMP segments + audience size)
      case 2:
        response = await AgentAPI.approveAudience({
          attrs: stepData.attrs || [],
          size: stepData.size || 0,
        })
        break

      // Step 3 — Setup: order was already created by ConfirmPhase.handleCreate (phase=2).
      // Just show a local success message to avoid a second backend call with wrong phase.
      case 3:
        response = {
          id: generateId(),
          role: 'assistant',
          content: '✅ Chiến dịch đã được tạo thành công trên AdsPilot! Anh xem tổng kết ở bước Kết quả bên phải.',
          blocks: [{ type: 'info', text: '🎉 Order đã được khởi tạo. Chuyển sang bước Kết quả...' }],
          timestamp: new Date().toISOString(),
          metadata: { tool: 'order_create', model: 'minimax', step: 3 },
        }
        break

      // Step 4 — Result
      case 4:
        response = await AgentAPI.getResult()
        break

      // Steps 5-6 — Report / Email (kept as mock for now)
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
    setBusy(false)
    if (onStepApproved) onStepApproved(stepIndex)
  }, [busy, startThinking, stopThinking, onStepApproved])

  return { messages, busy, boot, newChat, sendMessage, approveStep }
}
