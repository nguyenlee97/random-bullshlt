// ─── DemoEngine: React Context + Controller Hook ────────────────────────────
// Drives the demo walkthrough by advancing through step sequences,
// performing DOM actions, and communicating with App.jsx via custom events.

import { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react'
import DemoOverlay from './DemoOverlay'
import { STAGE1_STEPS, buildStage2Steps, pickRandomBrief, DEMO_AD_FORMAT_META, DEMO_NON_BOX_FORMAT_IDS, ZONE_FORMAT_MAP } from './demoScripts'
import { AUTOPILOT_TOUR_STEPS } from './autopilotTour'
import { buildAutopilotLiveSteps } from './autopilotWalkthrough'
import { compatiblePlacementIndexes } from './demoPlacementCompatibility.js'
import { fitDemoCreative } from './demoCreativeFit.js'
import {
  AUTOPILOT_CHECKPOINT_OBSERVATION,
  classifyAutopilotCheckpointObservation,
} from './autopilotCheckpointSync.js'
import { waitForDemoElement } from './demoElementWait.js'
import {
  hasSeenOpenAIWalkthroughTool,
  isOpenAIWalkthroughModel,
  matchesWalkthroughMetaTool,
  rememberOpenAIWalkthroughTool,
} from './walkthroughMessageTracker'
import log from '@/lib/logger'
import { ACTIVE_CAMPAIGN_ENGINE_ID } from '@/lib/campaignEnginePolicy'

const DemoContext = createContext(null)

export function useDemo() {
  return useContext(DemoContext)
}

// ─── State machine phases ────────────────────────────────────────────────────
const PHASE = {
  IDLE: 'idle',
  CONFIRM_START: 'confirm_start',
  STAGE1: 'stage1',
  CONFIRM_LIVE: 'confirm_live',
  STAGE2: 'stage2',
  COMPLETE: 'complete',
}

// ─── Helper: get element rect with retry ─────────────────────────────────────
function getRect(selector, retries = 5) {
  return new Promise((resolve) => {
    let attempts = 0
    const tryFind = () => {
      const el = document.querySelector(selector)
      if (el) {
        const rect = el.getBoundingClientRect()
        resolve({ top: rect.top, left: rect.left, right: rect.right, bottom: rect.bottom, width: rect.width, height: rect.height })
      } else if (attempts < retries) {
        attempts++
        setTimeout(tryFind, 300)
      } else {
        log.error(`DemoEngine: element not found: ${selector}`)
        resolve(null)
      }
    }
    tryFind()
  })
}

// ─── Helper: scroll element into view ────────────────────────────────────────
function scrollIntoView(selector) {
  const el = document.querySelector(selector)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

function currentCreativeReviewState() {
  return document
    .querySelector('[data-demo="creative-review-state"]')
    ?.getAttribute('data-review-state') || ''
}

function isCreativeReviewTerminal() {
  return document
    .querySelector('[data-demo="creative-review-state"]')
    ?.getAttribute('data-review-terminal') === 'true'
}

// ─── Helper: which mobile pane ('chat' | 'workspace') a step needs ────────────
// On desktop both panes are always visible, so this is only used to drive the
// mobile TabBar. Detection order:
//   1. If the step's target element is in the DOM, use its containing pane
//      (works even while a pane is hidden via `display:none`, since the node
//      is still mounted).
//   2. Otherwise (target not yet rendered, e.g. WAIT_FOR_SELECTOR) fall back to
//      a step-type default.
// Returns null for top-bar / global targets (New Chat, Reset, popups) → no switch.
function resolvePaneForStep(step) {
  if (!step) return null
  const sel = step.target || step.tooltip?.target
  if (sel) {
    const el = document.querySelector(sel)
    if (el) {
      if (el.closest('[data-demo="chat-pane"]')) return 'chat'
      if (el.closest('[data-demo="workspace-pane"]')) return 'workspace'
      if (el.closest('[data-demo="autopilot-canvas"]')) return 'autopilot'
      return null // top-bar / global element — leave the current tab as-is
    }
  }
  // Target not in DOM (or no target) → decide by step type
  switch (step.type) {
    case 'WAIT_FOR_RESPONSE':
    case 'WAIT_FOR_MSG':
    case 'HIGHLIGHT_MSG':
    case 'TYPE_AND_SEND':
      return 'chat'
    case 'WAIT_FOR_SELECTOR':
    case 'WAIT_FOR_CREATIVE_REVIEW':
    case 'INJECT_DEMO_CREATIVES':
    case 'SELECT_RECO_ZONES':
    case 'ASSIGN_CREATIVES':
    case 'EDIT_FIELD':
      return 'workspace'
    case 'WAIT_FOR_AUTOPILOT_TASK':
    case 'TRIM_AUTOPILOT_PLACEMENTS':
      return 'autopilot'
    default:
      return null
  }
}


// ─── DemoProvider ────────────────────────────────────────────────────────────
export function DemoProvider({
  children, busy, messages, onSendMessage, onApprove, onRequestTab, activeTab,
  onActiveChange, onPrepareLive, experienceMode = 'guided', autoStart = '', onAutoStartConsumed,
  conversationModel = ACTIVE_CAMPAIGN_ENGINE_ID,
}) {
  const [phase, setPhase] = useState(PHASE.IDLE)
  const [stepIdx, setStepIdx] = useState(0)
  const [steps, setSteps] = useState([])
  const [targetRect, setTargetRect] = useState(null)
  const [isWaiting, setIsWaiting] = useState(false)
  const [popup, setPopup] = useState(null)
  const [stepRetryNonce, setStepRetryNonce] = useState(0)
  const briefRef = useRef(null)
  const eventCleanupRef = useRef(null)
  const onApproveRef = useRef(onApprove)
  const busyRef = useRef(busy)
  const messagesRef = useRef(messages)
  const conversationModelRef = useRef(conversationModel)
  const openAISeenMetaToolsRef = useRef(new Set())
  const prevMsgCountRef = useRef(0)
  const autopilotWaitingTaskRef = useRef('')
  const tourModeRef = useRef(experienceMode === 'autopilot' ? 'autopilot' : 'copilot')
  // Refs for mobile tab control — read inside async step logic without stale closures
  const onRequestTabRef = useRef(onRequestTab)
  const activeTabRef = useRef(activeTab)

  // Keep refs fresh
  useEffect(() => { busyRef.current = busy }, [busy])
  useEffect(() => { onApproveRef.current = onApprove }, [onApprove])
  useEffect(() => { messagesRef.current = messages }, [messages])
  useEffect(() => {
    conversationModelRef.current = conversationModel
    if (!isOpenAIWalkthroughModel(conversationModel)) {
      openAISeenMetaToolsRef.current.clear()
    }
  }, [conversationModel])
  useEffect(() => { onRequestTabRef.current = onRequestTab }, [onRequestTab])
  useEffect(() => { activeTabRef.current = activeTab }, [activeTab])

  // OpenAI audience/setup responses can finish while the walkthrough is still
  // explaining the previous step. Record them from the beginning of the run so
  // WAIT_FOR_MSG cannot miss an already-fired event. GreenNode intentionally
  // keeps its established wait path unchanged.
  useEffect(() => {
    const handler = (event) => {
      rememberOpenAIWalkthroughTool(
        openAISeenMetaToolsRef.current,
        conversationModelRef.current,
        event,
      )
    }
    window.addEventListener('agent:inject_message', handler)
    return () => window.removeEventListener('agent:inject_message', handler)
  }, [])

  const isActive = phase !== PHASE.IDLE && phase !== PHASE.COMPLETE

  // Notify parent when the demo becomes active/inactive (used to pause App auto-nav)
  useEffect(() => { onActiveChange?.(isActive) }, [isActive]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Ensure the correct mobile pane is visible before measuring/acting ──────
  // Desktop (>=768px) shows both panes, so this is a no-op there. Only switches
  // (and waits for layout) when an actual tab change is needed on mobile.
  const syncTabForStep = useCallback(async (step) => {
    if (typeof window === 'undefined' || window.innerWidth >= 768) return
    const pane = resolvePaneForStep(step)
    if (pane && pane !== activeTabRef.current && onRequestTabRef.current) {
      onRequestTabRef.current(pane)
      activeTabRef.current = pane // optimistic — avoids double-switch before prop updates
      await new Promise(r => setTimeout(r, 350)) // let the pane mount + lay out
    }
  }, [])

  const currentStep = isActive && steps[stepIdx] ? steps[stepIdx] : null

  // ── Cleanup event listener on unmount ──────────────────────────────────
  useEffect(() => {
    return () => {
      if (eventCleanupRef.current) eventCleanupRef.current()
    }
  }, [])

  // ── Update target rect when step changes ───────────────────────────────
  useEffect(() => {
    if (!currentStep) {
      setTargetRect(null)
      return
    }

    let cancelled = false
    const target = currentStep.target || currentStep.tooltip?.target
    ;(async () => {
      // On mobile, make the pane holding this target visible before measuring
      await syncTabForStep(currentStep)
      if (cancelled) return
      if (target) {
        scrollIntoView(target)
        // Small delay for scroll to settle
        await new Promise(r => setTimeout(r, 200))
        if (cancelled) return
        const rect = await getRect(target)
        if (!cancelled) setTargetRect(rect)
      } else {
        setTargetRect(null)
      }
    })()
    return () => { cancelled = true }
  }, [currentStep, stepIdx, phase]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Execute step action ────────────────────────────────────────────────
  const executeStep = useCallback(async (step, idx) => {
    if (!step) return

    log.step(`DemoEngine: executing step ${idx} type=${step.type}`)

    if (
      step.whenAutopilotTask
      && autopilotWaitingTaskRef.current !== step.whenAutopilotTask
    ) {
      setStepIdx(prev => prev + 1)
      return
    }

    // Skip manual-review-only steps when analysis already auto-approved every
    // creative. This branches the walkthrough without changing either model
    // provider's underlying campaign workflow.
    if (
      step.whenReviewState
      && currentCreativeReviewState() !== step.whenReviewState
    ) {
      setStepIdx(prev => prev + 1)
      return
    }

    // Mobile: ensure the pane this step acts on is visible before clicking/typing.
    // No-op on desktop and when already on the right tab.
    await syncTabForStep(step)

    switch (step.type) {
      case 'TOOLTIP':
      case 'HIGHLIGHT_EL':
        // Just show tooltip — user clicks "Tiếp theo" to advance
        break

      case 'HIGHLIGHT_MSG': {
        // Scroll to last assistant message
        const thread = document.querySelector('[data-demo="chat-thread"]')
        if (thread) {
          const bubbles = thread.querySelectorAll('[data-demo="msg-bubble"]')
          const last = bubbles[bubbles.length - 1]
          if (last) {
            last.scrollIntoView({ behavior: 'smooth', block: 'center' })
            const rect = last.getBoundingClientRect()
            setTargetRect({ top: rect.top, left: rect.left, right: rect.right, bottom: rect.bottom, width: rect.width, height: rect.height })
          }
        }
        break
      }

      case 'TYPE_AND_SEND': {
        setIsWaiting(true)
        const input = document.querySelector('#chat-input')
        if (input) {
          const proto = input.tagName === 'TEXTAREA'
            ? window.HTMLTextAreaElement.prototype
            : window.HTMLInputElement.prototype
          const nativeSetter = Object.getOwnPropertyDescriptor(proto, 'value').set

          // Type character by character
          let i = 0
          await new Promise(resolve => {
            const typeChar = () => {
              if (i <= step.text.length) {
                nativeSetter.call(input, step.text.slice(0, i))
                input.dispatchEvent(new Event('input', { bubbles: true }))
                i++
                setTimeout(typeChar, 15)
              } else {
                resolve()
              }
            }
            typeChar()
          })

          // Pause then send
          await new Promise(r => setTimeout(r, 400))
          const sendBtn = document.querySelector('#chat-send-btn')
          if (sendBtn && !sendBtn.disabled) sendBtn.click()
        }
        setIsWaiting(false)
        // Immediately advance to WAIT_FOR_RESPONSE — which shows its own tooltip while waiting
        setStepIdx(prev => prev + 1)
        return
      }

      case 'WAIT_FOR_RESPONSE': {
        setIsWaiting(true)
        // Robust poll: wait for busy to appear, then clear
        await new Promise(resolve => {
          let seenBusy = false
          const poll = () => {
            if (!seenBusy && busyRef.current) {
              seenBusy = true
            }
            // If we already went busy OR we haven't gone busy yet within 2s, then just wait for false
            if (seenBusy && !busyRef.current) {
              resolve()
            } else {
              setTimeout(poll, 150)
            }
          }
          setTimeout(poll, 300)
        })
        if (step.requiredSelector) {
          const proposalReady = await new Promise(resolve => {
            const startedAt = Date.now()
            const poll = () => {
              if (document.querySelector(step.requiredSelector)) {
                resolve(true)
              } else if (Date.now() - startedAt > (step.requiredTimeout || 5000)) {
                resolve(false)
              } else {
                setTimeout(poll, 200)
              }
            }
            poll()
          })
          if (!proposalReady) {
            log.error(`DemoEngine: required response artifact missing: ${step.requiredSelector}`)
            setIsWaiting(false)
            setPhase(PHASE.CONFIRM_LIVE)
            setPopup({
              title: 'Brief chưa được tạo thành công',
              text: 'Agent chưa tạo được đề xuất Brief nên walkthrough đã dừng trước bước review. Bạn có thể thử lại bằng một campaign mới; walkthrough sẽ không giả vờ rằng proposal đã tồn tại.',
              buttons: [
                { label: 'Thử lại walkthrough', variant: 'primary', action: 'live' },
                { label: 'Dừng tại đây', variant: 'ghost', action: 'skip' },
              ],
            })
            return
          }
        }
        setIsWaiting(false)
        setStepIdx(prev => prev + 1)
        return
      }

      case 'EDIT_FIELD': {
        const { path, value } = step
        window.dispatchEvent(new CustomEvent('demo:set_form_field', {
          detail: { path, value }
        }))
        // Refresh rect after field updates
        await new Promise(r => setTimeout(r, 400))
        const target = step.tooltip?.target
        if (target) {
          const rect = await getRect(target)
          setTargetRect(rect)
        }
        break
      }

      case 'CLICK_EL': {
        setIsWaiting(true)
        const delay = step.delay || 300
        await new Promise(r => setTimeout(r, delay))
        const el = await waitForDemoElement(step.target, {
          timeout: step.timeout || 30000,
        })
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' })
          await new Promise(r => setTimeout(r, 300))
          el.click()
        } else {
          log.error(`DemoEngine: CLICK_EL target not found: ${step.target}`)
          setIsWaiting(false)
          setPopup({
            title: 'Thao tác walkthrough chưa sẵn sàng',
            text: `Walkthrough chưa tìm thấy điều khiển cần thiết cho bước **${step.tooltip?.title || step.title || 'tiếp theo'}**. Tiến trình hiện tại vẫn được giữ nguyên; hãy thử lại bước này thay vì bỏ qua dữ liệu.`,
            buttons: [
              { label: 'Thử lại bước này', variant: 'primary', action: 'retry_current_step' },
              { label: 'Dừng walkthrough', variant: 'ghost', action: 'skip' },
            ],
          })
          return
        }
        // Wait for any triggered busy cycle
        await new Promise(r => setTimeout(r, 400))
        if (busyRef.current) {
          await new Promise(resolve => {
            const poll = () => {
              if (!busyRef.current) resolve()
              else setTimeout(poll, 150)
            }
            poll()
          })
        }
        setIsWaiting(false)
        setStepIdx(prev => prev + 1)
        return
      }

      case 'WAIT_FOR_EVENT': {
        setIsWaiting(true)
        const { eventName, filter, timeout = 30000 } = step
        await waitForCustomEvent(eventName, filter, timeout)
        // Small extra wait for UI to settle
        await new Promise(r => setTimeout(r, 1200))
        setIsWaiting(false)
        setStepIdx(prev => prev + 1)
        return
      }

      // WAIT_FOR_MSG: like WAIT_FOR_EVENT but checks if message already exists first.
      // Resolves immediately if the tool message is already in the messages list.
      case 'WAIT_FOR_MSG': {
        setIsWaiting(true)
        const { metaTool, timeout = 30000 } = step

        // Check if the message already arrived (user was slow clicking Tiếp theo)
        const alreadyArrived = hasSeenOpenAIWalkthroughTool(
          openAISeenMetaToolsRef.current,
          conversationModelRef.current,
          metaTool,
        ) || messagesRef.current.some(
          m => m.metadata?.tool === metaTool
        )

        if (!alreadyArrived) {
          // Wait for the live event
          await new Promise((resolve) => {
            let resolved = false
            const handler = (e) => {
              const tool = e.detail?.metadata?.tool
              if (
                matchesWalkthroughMetaTool(
                  conversationModelRef.current,
                  tool,
                  metaTool,
                ) && !resolved
              ) {
                resolved = true
                window.removeEventListener('agent:inject_message', handler)
                resolve()
              }
            }
            window.addEventListener('agent:inject_message', handler)
            eventCleanupRef.current = () => window.removeEventListener('agent:inject_message', handler)

            setTimeout(() => {
              if (!resolved) {
                resolved = true
                window.removeEventListener('agent:inject_message', handler)
                log.error(`DemoEngine: WAIT_FOR_MSG timeout for metaTool=${metaTool}`)
                resolve()
              }
            }, timeout)
          })
        }

        // Small settle delay for UI to render
        await new Promise(r => setTimeout(r, 600))
        setIsWaiting(false)
        setStepIdx(prev => prev + 1)
        return
      }

      case 'POPUP': {
        setPopup(step)
        break
      }

      case 'TYPE_INPUT': {
        // Type text character-by-character into any arbitrary input/textarea selector
        const inputEl = document.querySelector(step.target)
        if (inputEl) {
          inputEl.focus()
          const proto = inputEl.tagName === 'TEXTAREA'
            ? window.HTMLTextAreaElement.prototype
            : window.HTMLInputElement.prototype
          const nativeSetter = Object.getOwnPropertyDescriptor(proto, 'value').set
          const contentToType = step.inputText || ''
          let i = 0
          await new Promise(resolve => {
            const typeChar = () => {
              if (i <= contentToType.length) {
                nativeSetter.call(inputEl, contentToType.slice(0, i))
                inputEl.dispatchEvent(new Event('input', { bubbles: true }))
                i++
                setTimeout(typeChar, step.charDelay || 18)
              } else {
                resolve()
              }
            }
            typeChar()
          })
        } else {
          log.error(`DemoEngine: TYPE_INPUT target not found: ${step.target}`)
        }
        if (step.autoAdvance && inputEl) {
          // Let React commit the controlled input value before the next
          // walkthrough action reads or clicks controls derived from it.
          await new Promise(r => setTimeout(r, 250))
          setStepIdx(prev => prev + 1)
          return
        }
        break
      }

      case 'WAIT_FOR_SELECTOR': {
        // Poll until a CSS selector appears in the DOM, then advance
        setIsWaiting(true)
        const { target: sel, timeout: wfTimeout = 90000 } = step
        const element = await waitForDemoElement(sel, {
          timeout: wfTimeout,
          interval: 300,
        })
        if (!element) {
          log.error(`DemoEngine: WAIT_FOR_SELECTOR timeout for: ${sel}`)
          setIsWaiting(false)
          setPopup({
            title: 'Màn hình tiếp theo chưa sẵn sàng',
            text: `Walkthrough vẫn đang chờ **${step.title || 'giao diện tiếp theo'}**. Nó sẽ không tự đi tiếp khi dữ liệu hoặc editor chưa xuất hiện.`,
            buttons: [
              { label: 'Tiếp tục chờ', variant: 'primary', action: 'retry_current_step' },
              { label: 'Dừng walkthrough', variant: 'ghost', action: 'skip' },
            ],
          })
          return
        }
        // Extra settle time so the element is fully rendered
        await new Promise(r => setTimeout(r, 700))
        setIsWaiting(false)
        setStepIdx(prev => prev + 1)
        return
      }

      case 'APPLY_AUTOPILOT_BRIEF': {
        setIsWaiting(true)
        const proposalButton = document.querySelector(
          '[data-demo="workspace-proposal-confirm"][data-workspace-field="brief"]',
        )
        if (proposalButton) {
          proposalButton.click()
        } else {
          // Older OpenAI responses can hydrate the Brief directly without a
          // proposal card. Reuse the real Guided approval callback as a
          // compatibility fallback; GreenNode never enters this walkthrough.
          await onApproveRef.current?.()
        }
        await new Promise(r => setTimeout(r, 800))
        setIsWaiting(false)
        setStepIdx(prev => prev + 1)
        return
      }

      case 'WAIT_FOR_AUTOPILOT_TASK': {
        setIsWaiting(true)
        const expected = new Set(step.taskKeys || [])
        const timeout = step.timeout || 120000
        const unexpectedGraceMs = step.unexpectedGraceMs ?? 4000
        const startedAt = Date.now()
        let unexpectedTask = ''
        let unexpectedSince = 0
        const found = await new Promise(resolve => {
          const poll = () => {
            const canvas = document.querySelector('[data-demo="autopilot-canvas"]')
            const taskKey = canvas?.getAttribute('data-autopilot-waiting-task') || ''
            const status = canvas?.getAttribute('data-autopilot-status') || ''
            const observation = classifyAutopilotCheckpointObservation({
              expectedTaskKeys: [...expected],
              taskKey,
              status,
              lastHandledTask: autopilotWaitingTaskRef.current,
            })

            if (observation === AUTOPILOT_CHECKPOINT_OBSERVATION.EXPECTED) {
              resolve(taskKey)
            } else if (observation === AUTOPILOT_CHECKPOINT_OBSERVATION.TERMINAL) {
              resolve('')
            } else if (observation === AUTOPILOT_CHECKPOINT_OBSERVATION.UNEXPECTED) {
              if (unexpectedTask !== taskKey) {
                unexpectedTask = taskKey
                unexpectedSince = Date.now()
              }
              if (Date.now() - unexpectedSince >= unexpectedGraceMs) {
                resolve(`unexpected:${taskKey}`)
              } else {
                setTimeout(poll, 500)
              }
            } else if (Date.now() - startedAt > timeout) {
              log.error(`DemoEngine: WAIT_FOR_AUTOPILOT_TASK timeout for ${[...expected].join(',')}`)
              resolve('')
            } else {
              // A just-approved checkpoint can remain visible while Autopilot
              // resumes. Keep waiting instead of treating it as a new blocker.
              unexpectedTask = ''
              unexpectedSince = 0
              setTimeout(poll, 500)
            }
          }
          poll()
        })
        setIsWaiting(false)
        if (found.startsWith('unexpected:')) {
          const blockedTask = found.slice('unexpected:'.length)
          const audienceBlocked = blockedTask === 'retrieve_audience'
          setPopup({
            title: audienceBlocked
              ? 'Brief cần thêm ngữ cảnh trước khi tìm audience'
              : 'Autopilot cần bạn xử lý một checkpoint phát sinh',
            text: audienceBlocked
              ? 'Walkthrough đã dừng đúng tại bước **Tìm audience** vì Agent cần làm rõ sản phẩm, dịch vụ hoặc người mua. Hãy bổ sung Brief hoặc chọn audience thủ công; các artifact đã tạo vẫn được giữ nguyên.'
              : `Autopilot đang chờ tại checkpoint **${blockedTask}**, ngoài checkpoint mà walkthrough dự kiến ở thời điểm này. Hãy xử lý checkpoint trong workspace rồi tiếp tục; walkthrough sẽ chờ lại từ đúng vị trí hiện tại.`,
            buttons: [
              { label: 'Đã xử lý, tiếp tục walkthrough', variant: 'primary', action: 'retry_current_step' },
              { label: 'Dừng walkthrough', variant: 'ghost', action: 'skip' },
            ],
          })
          return
        }
        if (!found) {
          setPopup({
            title: 'Autopilot chưa đến được checkpoint tiếp theo',
            text: 'Run bị lỗi, bị hủy hoặc chưa đến checkpoint tiếp theo trong thời gian chờ. Các artifact đã lưu vẫn được giữ lại; nếu run vẫn đang xử lý, bạn có thể tiếp tục chờ mà không phải khởi động lại walkthrough.',
            buttons: [
              { label: 'Tiếp tục chờ', variant: 'primary', action: 'retry_current_step' },
              { label: 'Dừng walkthrough và kiểm tra run', variant: 'ghost', action: 'skip' },
            ],
          })
          return
        }
        autopilotWaitingTaskRef.current = found
        await new Promise(r => setTimeout(r, 700))
        setStepIdx(prev => prev + 1)
        return
      }

      case 'TRIM_AUTOPILOT_AUDIENCE': {
        setIsWaiting(true)
        const keep = Math.max(1, Number(step.keep || 3))
        const selected = [
          ...document.querySelectorAll(
            '[data-demo="autopilot-audience-option"][aria-pressed="true"]',
          ),
        ]
        for (const option of selected.slice(keep).reverse()) {
          option.click()
          await new Promise(r => setTimeout(r, 120))
        }
        setIsWaiting(false)
        setStepIdx(prev => prev + 1)
        return
      }

      case 'CHANGE_AUTOPILOT_TARGETING': {
        setIsWaiting(true)
        for (const dimension of step.dimensions || []) {
          const option = document.querySelector(
            `[data-demo="autopilot-targeting-option"][data-targeting-dimension="${dimension}"][aria-pressed="false"]`,
          )
          option?.click()
          await new Promise(r => setTimeout(r, 180))
        }
        setIsWaiting(false)
        setStepIdx(prev => prev + 1)
        return
      }

      case 'TRIM_AUTOPILOT_PLACEMENTS': {
        setIsWaiting(true)
        const keep = Math.max(1, Number(step.keep || 2))
        const review = document.querySelector(
          '[data-demo="autopilot-review-artifact"][data-autopilot-task="plan_placement_intent"]',
        )
        const options = [
          ...(review || document).querySelectorAll(
            '[data-demo="autopilot-placement-option"]',
          ),
        ]
        const compatibleIndexes = step.creativeFormats?.length
          ? compatiblePlacementIndexes(
              options.map(option => ({
                size: option.dataset.zoneSize,
                format: option.dataset.zoneFormat,
                creativeContractId: option.dataset.zoneContract,
              })),
              step.creativeFormats,
              keep,
            )
          : []
        const desired = new Set(
          compatibleIndexes.length
            ? compatibleIndexes
            : options.slice(0, keep).map((_, index) => index),
        )
        for (const [index, option] of options.entries()) {
          const selected = option.getAttribute('aria-pressed') === 'true'
          if (selected !== desired.has(index)) {
            option.click()
            await new Promise(r => setTimeout(r, 180))
          }
        }
        setIsWaiting(false)
        setStepIdx(prev => prev + 1)
        return
      }

      case 'WAIT_FOR_CREATIVE_REVIEW': {
        setIsWaiting(true)
        const {
          reviewState,
          reviewStates = reviewState ? [reviewState] : ['ready', 'blocked'],
          timeout: reviewTimeout = 120000,
        } = step
        const startedAt = Date.now()

        const reachedTerminalState = await new Promise((resolve) => {
          const poll = () => {
            const state = currentCreativeReviewState()
            if (isCreativeReviewTerminal() && reviewStates.includes(state)) {
              resolve(true)
            } else if (Date.now() - startedAt > reviewTimeout) {
              log.error(
                `DemoEngine: WAIT_FOR_CREATIVE_REVIEW timeout; `
                + `expected=${reviewStates.join(',')} actual=${state || 'missing'}`,
              )
              resolve(false)
            } else {
              setTimeout(poll, 300)
            }
          }
          poll()
        })

        setIsWaiting(false)
        if (!reachedTerminalState) {
          setPopup({
            title: 'Phân tích creative chưa hoàn tất',
            text: 'Walkthrough đã dừng để không đi tiếp khi kết quả Creative Intelligence chưa sẵn sàng. Hãy kiểm tra trạng thái phân tích trong workspace rồi thử lại walkthrough.',
            buttons: [
              { label: 'Dừng walkthrough và kiểm tra', variant: 'primary', action: 'skip' },
            ],
          })
          return
        }

        await new Promise(r => setTimeout(r, 500))
        setStepIdx(prev => prev + 1)
        return
      }

      case 'PAUSE': {
        await new Promise(r => setTimeout(r, step.ms || 1000))
        setStepIdx(prev => prev + 1)
        return
      }

      case 'INJECT_DEMO_CREATIVES': {
        setIsWaiting(true)
        const { briefId } = step
        const creatives = []
        for (const formatId of DEMO_NON_BOX_FORMAT_IDS) {
          const meta = DEMO_AD_FORMAT_META[formatId]
          const url = `/demo-creatives/${briefId}/${formatId}.png`
          try {
            const resp = await fetch(url)
            if (!resp.ok) {
              log.error(`INJECT_DEMO_CREATIVES: 404 → ${url}`)
              continue
            }
            const sourceBlob = await resp.blob()
            const fitted = isOpenAIWalkthroughModel(conversationModelRef.current)
              ? await fitDemoCreative(sourceBlob, meta)
              : { blob: sourceBlob, dataUrl: await new Promise((resolve) => {
                  const reader = new FileReader()
                  reader.onload = () => resolve(reader.result)
                  reader.readAsDataURL(sourceBlob)
                }) }
            creatives.push({
              id: `demo-${briefId}-${formatId}`,
              name: `${formatId}.png`,
              type: 'image/png',
              size: fitted.blob.size,
              dataUrl: fitted.dataUrl,
              width: meta.width,
              height: meta.height,
              formatId,
              aiGenerated: false,
              demoInjected: true,
              exactDimensionsVerified: isOpenAIWalkthroughModel(conversationModelRef.current),
            })
          } catch (e) {
            log.error(`INJECT_DEMO_CREATIVES: failed ${url}`, e.message)
          }
        }
        if (creatives.length > 0) {
          window.dispatchEvent(new CustomEvent('demo:inject_creatives', { detail: { creatives } }))
          await new Promise(r => setTimeout(r, 500))
        }
        log.step(`INJECT_DEMO_CREATIVES: injected ${creatives.length} creatives for brief "${briefId}"`)
        setIsWaiting(false)
        setStepIdx(prev => prev + 1)
        return
      }

      case 'SELECT_RECO_ZONES': {
        setIsWaiting(true)
        const chosen = await new Promise(resolve => {
          const handler = (e) => { resolve(e.detail?.zoneIds || []) }
          window.addEventListener('demo:reco_zones_selected', handler, { once: true })
          window.dispatchEvent(new CustomEvent('demo:select_reco_zones', {
            detail: { count: step.count || 2 }
          }))
          // Safety timeout
          setTimeout(() => resolve([]), 6000)
        })
        log.step(`SELECT_RECO_ZONES: selected [${chosen.join(', ')}]`)
        setIsWaiting(false)
        setStepIdx(prev => prev + 1)
        return
      }

      case 'ASSIGN_CREATIVES': {
        setIsWaiting(true)
        const done = await new Promise(resolve => {
          const handler = (e) => { resolve(e.detail?.assignments || {}) }
          window.addEventListener('demo:creatives_assigned', handler, { once: true })
          window.dispatchEvent(new CustomEvent('demo:assign_creatives', {}))
          setTimeout(() => resolve({}), 6000)
        })
        log.step(`ASSIGN_CREATIVES: assigned ${Object.keys(done).length} zones`)
        setIsWaiting(false)
        setStepIdx(prev => prev + 1)
        return
      }

      default:
        log.error(`DemoEngine: unknown step type: ${step.type}`)
    }
  }, [])

  // ── Wait for busy to become true then false ────────────────────────────
  function waitForBusyCycle() {
    return new Promise((resolve) => {
      const check = () => {
        if (!busyRef.current) {
          resolve()
        } else {
          setTimeout(check, 200)
        }
      }
      // Wait until busy goes true first, or if already true, wait for false
      const waitForTrue = () => {
        if (busyRef.current) {
          check()
        } else {
          setTimeout(waitForTrue, 100)
        }
      }
      // Give a small head start for the action to trigger busy
      setTimeout(waitForTrue, 300)
    })
  }

  // ── Wait for a custom DOM event ────────────────────────────────────────
  function waitForCustomEvent(eventName, filter, timeout) {
    return new Promise((resolve) => {
      let resolved = false
      const handler = (e) => {
        if (filter?.metaTool) {
          const tool = e.detail?.metadata?.tool
          if (tool !== filter.metaTool) return
        }
        if (!resolved) {
          resolved = true
          window.removeEventListener(eventName, handler)
          resolve()
        }
      }
      window.addEventListener(eventName, handler)
      eventCleanupRef.current = () => window.removeEventListener(eventName, handler)

      // Timeout fallback
      setTimeout(() => {
        if (!resolved) {
          resolved = true
          window.removeEventListener(eventName, handler)
          log.error(`DemoEngine: WAIT_FOR_EVENT timeout for ${eventName}`)
          resolve()
        }
      }, timeout)
    })
  }

  // ── Advance to next step ───────────────────────────────────────────────
  const advanceStep = useCallback((fromIdx) => {
    const nextIdx = (fromIdx ?? stepIdx) + 1
    if (nextIdx >= steps.length) {
      // End of current phase
      handlePhaseEnd()
    } else {
      setStepIdx(nextIdx)
    }
  }, [stepIdx, steps])

  // When stepIdx changes, execute the new step
  useEffect(() => {
    if (isActive && steps[stepIdx]) {
      executeStep(steps[stepIdx], stepIdx)
    }
  }, [stepIdx, phase, stepRetryNonce]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Handle end of a phase ──────────────────────────────────────────────
  const handlePhaseEnd = useCallback(() => {
    switch (phase) {
      case PHASE.STAGE1:
        if (tourModeRef.current === 'autopilot') {
          if (isOpenAIWalkthroughModel(conversationModelRef.current)) {
            setPhase(PHASE.CONFIRM_LIVE)
            setPopup({
              title: 'Tiếp tục với walkthrough Autopilot tương tác?',
              text: 'Walkthrough sẽ tạo một **Autopilot run thật** từ scenario brief, giới thiệu cách đọc plan và evidence, tự động hoàn tất Audience cùng targeting, rồi dừng ở ba checkpoint quan trọng: placement, creative assignment và launch.\n\nNguồn creative được chọn ngẫu nhiên giữa bộ file chuẩn bị trước và phương án tạo tự động. Walkthrough dừng trước nút tạo order.',
              buttons: [
                { label: 'Bắt đầu walkthrough', variant: 'primary', action: 'live' },
                { label: 'Dừng tại tour giao diện', variant: 'ghost', action: 'skip' },
              ],
            })
            break
          }
          setPhase(PHASE.COMPLETE)
          setPopup({
            title: 'Tour Campaign Autopilot hoàn tất',
            text: 'Bạn đã hoàn tất tour giao diện. Walkthrough tương tác chưa được bật cho cấu hình campaign này; bạn vẫn có thể bắt đầu và vận hành Autopilot trực tiếp từ workspace.',
            buttons: [
              { label: 'Đã hiểu', variant: 'primary', action: 'skip' },
            ],
          })
          break
        }
        setPhase(PHASE.CONFIRM_LIVE)
        setPopup({
          title: 'Tiếp tục với walkthrough tương tác?',
          text: 'Bạn đã nắm được giao diện. Tiếp theo, Agent sẽ đi cùng bạn qua **Brief → Audience → Creative → Setup → launch review** trên workspace thật.\n\nTour dừng trước nút tạo order, nên không launch campaign thay bạn.',
          buttons: [
            { label: 'Bắt đầu walkthrough', variant: 'primary', action: 'live' },
            { label: 'Dừng tại đây', variant: 'ghost', action: 'skip' },
          ],
        })
        break
      case PHASE.STAGE2:
        if (tourModeRef.current === 'autopilot') {
          setPhase(PHASE.COMPLETE)
          setPopup({
            title: 'Walkthrough Autopilot đã đến Duyệt launch',
            text: 'Run thật đã đi qua Brief, Audience, targeting, 2 placement và creative assignment. Forecast cùng safety guard đã hoàn tất.\n\nWalkthrough dừng đúng ranh giới an toàn và **chưa tạo order**. Bạn có thể tự review rồi quyết định launch hoặc hủy run.',
            buttons: [
              { label: 'Tự review bản launch', variant: 'primary', action: 'skip' },
            ],
          })
        } else {
          setPhase(PHASE.COMPLETE)
          setPopup(null)
        }
        break
      default:
        setPhase(PHASE.IDLE)
        setPopup(null)
    }
  }, [phase])

  // ── Public API ─────────────────────────────────────────────────────────

  const startDemo = useCallback((requestedMode) => {
    log.step('DemoEngine: startDemo')
    openAISeenMetaToolsRef.current.clear()

    const mode = typeof requestedMode === 'string'
      ? requestedMode
      : experienceMode === 'autopilot' ? 'autopilot' : 'copilot'
    tourModeRef.current = mode === 'autopilot' ? 'autopilot' : 'copilot'

    if (tourModeRef.current === 'autopilot') {
      setPhase(PHASE.CONFIRM_START)
      setPopup({
        title: 'Khởi động tour Campaign Autopilot',
        text: 'Chọn cách bạn muốn khám phá **ngay trên giao diện thật**:\n\n**Tour giao diện** — Spotlight các khu vực Brief, nguồn creative, chế độ kiểm soát và cách đọc tiến độ Autopilot.\n\n**Walkthrough tương tác** — Tạo một Autopilot run từ scenario brief, thao tác Audience, targeting, placement và creative, rồi dừng tại launch review.',
        buttons: [
          { label: 'Tour giao diện', variant: 'outline', action: 'tour' },
          { label: 'Walkthrough tương tác', variant: 'primary', action: 'live' },
          { label: 'Bỏ qua', variant: 'ghost', action: 'skip' },
        ],
      })
      return
    }

    if (requestedMode === 'copilot-tour') {
      setPopup(null)
      setSteps([...STAGE1_STEPS])
      setStepIdx(0)
      setPhase(PHASE.STAGE1)
      return
    }

    setPhase(PHASE.CONFIRM_START)
    setPopup({
      title: 'Khởi động tour Campaign Copilot',
      text: 'Chọn cách bạn muốn khám phá **ngay trên giao diện thật**:\n\n**Tour giao diện** — Spotlight từng khu vực và cách phối hợp Chat + Workspace.\n\n**Walkthrough tương tác** — Agent đi qua các bước campaign và dừng tại launch review.',
      buttons: [
        { label: 'Tour giao diện', variant: 'outline', action: 'tour' },
        { label: 'Walkthrough tương tác', variant: 'primary', action: 'live' },
        { label: 'Bỏ qua', variant: 'ghost', action: 'skip' },
      ],
    })
  }, [experienceMode])

  useEffect(() => {
    if (!autoStart || isActive || popup) return
    startDemo(autoStart)
    onAutoStartConsumed?.()
  }, [autoStart, isActive, popup, startDemo, onAutoStartConsumed])

  const stopDemo = useCallback(() => {
    log.step('DemoEngine: stopDemo')
    openAISeenMetaToolsRef.current.clear()
    autopilotWaitingTaskRef.current = ''
    setStepRetryNonce(0)
    setPhase(PHASE.IDLE)
    setStepIdx(0)
    setSteps([])
    setTargetRect(null)
    setIsWaiting(false)
    setPopup(null)
    if (eventCleanupRef.current) eventCleanupRef.current()
  }, [])

  // ── Handle popup button actions ────────────────────────────────────────
  const handlePopupAction = useCallback((action) => {
    setPopup(null)

    if (action === 'retry_current_step') {
      setStepRetryNonce(prev => prev + 1)
      return
    }

    if (action === 'skip') {
      stopDemo()
      return
    }

    switch (phase) {
      case PHASE.CONFIRM_START: {
        if (action === 'tour') {
          // Stage 1 UI Tour
          setSteps(tourModeRef.current === 'autopilot'
            ? [...AUTOPILOT_TOUR_STEPS]
            : [...STAGE1_STEPS])
          setStepIdx(0)
          setPhase(PHASE.STAGE1)
        } else if (action === 'live') {
          // Skip tour, go straight to live demo
          startLiveDemo()
        }
        break
      }
      case PHASE.CONFIRM_LIVE: {
        if (action === 'live') {
          startLiveDemo()
        } else {
          stopDemo()
        }
        break
      }
      case PHASE.STAGE2:
        // POPUP step within stage 2 — advance
        setStepIdx(prev => prev + 1)
        break
      case PHASE.COMPLETE:
        stopDemo()
        break
      default:
        stopDemo()
    }
  }, [phase, stopDemo]) // eslint-disable-line react-hooks/exhaustive-deps

  async function startLiveDemo() {
    // Clear Stage 1 immediately, then let App prepare a fresh Copilot campaign
    // without dropping the selected mode or returning to the homepage.
    setSteps([])
    setStepIdx(0)
    setTargetRect(null)
    openAISeenMetaToolsRef.current.clear()
    try {
      const prepared = await onPrepareLive?.()
      if (prepared === false) throw new Error('Không thể chuẩn bị campaign walkthrough.')
      briefRef.current = pickRandomBrief()
      log.step(`DemoEngine: picked brief "${briefRef.current.id}"`)
      await new Promise(resolve => setTimeout(resolve, 350))
      const s2 = tourModeRef.current === 'autopilot'
        ? buildAutopilotLiveSteps(briefRef.current)
        : buildStage2Steps(briefRef.current)
      setSteps(s2)
      setStepIdx(0)
      setPhase(PHASE.STAGE2)
      prevMsgCountRef.current = messagesRef.current.length
    } catch (error) {
      log.error(`DemoEngine: prepare live walkthrough failed: ${error.message}`)
      setPhase(PHASE.CONFIRM_LIVE)
      setPopup({
        title: 'Chưa thể bắt đầu walkthrough',
        text: 'Agent không tạo được workspace mới cho walkthrough. Bạn có thể thử lại mà không mất campaign hiện tại.',
        buttons: [
          { label: 'Thử lại', variant: 'primary', action: 'live' },
          { label: 'Dừng tại đây', variant: 'ghost', action: 'skip' },
        ],
      })
    }
  }

  // ── Handle "Tiếp theo" click ───────────────────────────────────────────
  const handleNext = useCallback(() => {
    if (isWaiting) return
    advanceStep(stepIdx)
  }, [isWaiting, stepIdx, advanceStep])

  const totalSteps = steps.length

  return (
    <DemoContext.Provider value={{ isActive, phase, startDemo, stopDemo }}>
      {children}
      <DemoOverlay
        isActive={isActive || popup !== null}
        currentStep={currentStep}
        stepIdx={stepIdx}
        totalSteps={totalSteps}
        targetRect={targetRect}
        onNext={handleNext}
        onSkip={stopDemo}
        isWaiting={isWaiting}
        popup={popup}
        onPopupAction={handlePopupAction}
      />
    </DemoContext.Provider>
  )
}
