import { useState, useEffect, useRef } from 'react'
import { Button } from '@/components/ui/button'
import { Send, Loader2, ChevronLeft } from 'lucide-react'

// ─── Step-specific quick chips ────────────────────────────────────────────────
const STEP_CHIPS = {
  0: ['Objective nào phù hợp với tôi?', 'KPI nào nên chọn cho Awareness?', 'Budget tối thiểu là bao nhiêu?'],
  1: ['Hãy tự động chọn targeting phù hợp nhất cho chiến dịch này', 'DMP segment nào phù hợp với brief?', 'Audience size bao nhiêu là đủ?'],
  2: ['Creative size nào phù hợp cho Banner?', 'Skin zone cần creative như thế nào?', 'Format nào được hỗ trợ?'],
  3: ['Zone nào tốt nhất cho objective của tôi?', 'VI% và CTR có nghĩa là gì?', 'CPM bao nhiêu là hợp lý?'],
  4: ['Tổng kết chiến dịch', 'Xem link AdsPilot', 'Tạo chiến dịch mới'],
  5: ['Campaign nào hiệu quả nhất?', 'Đề xuất tối ưu tiếp theo'],
  6: ['Thêm người nhận', 'Chỉnh sửa nội dung email'],
}

export default function ChatComposer({ busy, currentStep, onSend, onBack }) {
  const [text, setText] = useState('')
  const inputRef = useRef(null)

  // Listen for prefill events dispatched by suggestion chips (action="prefill")
  useEffect(() => {
    const handler = (e) => {
      if (e.detail?.text !== undefined) {
        setText(e.detail.text)
        setTimeout(() => {
          inputRef.current?.focus()
          autoResize(inputRef.current)
        }, 50)
      }
    }
    window.addEventListener('agent:prefill_composer', handler)
    return () => window.removeEventListener('agent:prefill_composer', handler)
  }, [])

  // Auto-resize textarea up to max-height
  function autoResize(el) {
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 72) + 'px'
  }

  const handleChange = (e) => {
    setText(e.target.value)
    autoResize(e.target)
  }

  const handleSend = () => {
    if (!text.trim() || busy) return
    onSend(text.trim())
    setText('')
    // Reset height
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const chips = STEP_CHIPS[currentStep] || STEP_CHIPS[0]

  return (
    <div
      className="border-t border-border bg-white p-3 flex-shrink-0"
      style={{ paddingBottom: 'max(12px, env(safe-area-inset-bottom))' }}
    >
      {/* Quick chips — hidden on mobile for steps 0-4, shown on mobile for Report(5)/Email(6) */}
      <div data-demo="chat-chips" className="flex gap-1.5 overflow-x-auto scrollbar-none pb-1 mb-2.5 flex-nowrap">
        {currentStep > 0 && (
          <button
            onClick={onBack}
            disabled={busy}
            className="flex-shrink-0 flex items-center gap-1 text-[11px] font-semibold text-muted-foreground border border-border rounded-full px-2.5 py-1 hover:bg-muted/60 transition-colors disabled:opacity-50"
          >
            <ChevronLeft className="w-3 h-3" /> Quay lại
          </button>
        )}
        {chips.map(chip => (
          <button
            key={chip}
            onClick={() => !busy && onSend(chip)}
            disabled={busy}
            className="flex-shrink-0 text-[11px] font-semibold text-brand-700 bg-brand-50 border border-brand-200 rounded-full px-2.5 py-1 hover:bg-brand-100 transition-colors disabled:opacity-50"
          >
            {chip}
          </button>
        ))}
      </div>

      {/* Input row */}
      <div className="flex gap-2 items-end">
        <textarea
          ref={inputRef}
          id="chat-input"
          value={text}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder="Trao đổi với agent về bước hiện tại... (Shift+Enter xuống dòng)"
          disabled={busy}
          rows={1}
          className={[
            'flex-1 text-sm resize-none rounded-md border border-input bg-background px-3 py-2',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
            'disabled:cursor-not-allowed disabled:opacity-50',
            'leading-5 overflow-y-auto transition-all',
            // Desktop: max 3 lines (~72px), mobile: max 2 lines (~48px)
            'max-h-[48px] md:max-h-[72px]',
          ].join(' ')}
          style={{ minHeight: '40px' }}
        />

        <Button
          onClick={handleSend}
          disabled={busy || !text.trim()}
          size="icon"
          className="h-10 w-10 flex-shrink-0 self-end"
          id="chat-send-btn"
        >
          {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
        </Button>
      </div>
    </div>
  )
}
