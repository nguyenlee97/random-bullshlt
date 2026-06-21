import { useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import BlockRenderer from '@/blocks/BlockRenderer'
import { Bot, User, Wrench, RefreshCw, AlertTriangle } from 'lucide-react'

// ─── Typing indicator ─────────────────────────────────────────────────────────
const THINKING_PHRASES = [
  'Đang suy nghĩ...',
  'Chờ xíu nha...',
  'Đang phân tích...',
  'Gần xong rồi...',
  'Đang xử lý...',
  'Cho em thêm chút...',
]

function TypingIndicator() {
  const [phraseIdx, setPhraseIdx] = useState(0)
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    const phraseTimer = setInterval(() => setPhraseIdx(i => (i + 1) % THINKING_PHRASES.length), 3000)
    const elapsedTimer = setInterval(() => setElapsed(e => e + 1), 1000)
    return () => { clearInterval(phraseTimer); clearInterval(elapsedTimer) }
  }, [])

  return (
    <div className="flex gap-2.5 animate-fade-in">
      <Avatar className="w-8 h-8 flex-shrink-0 bg-gradient-to-br from-brand-500 to-brand-600">
        <AvatarFallback className="bg-transparent">
          <Bot className="w-4 h-4 text-white" />
        </AvatarFallback>
      </Avatar>
      <div className="bg-white rounded-2xl rounded-tl-sm border border-border shadow-chat px-4 py-3 flex items-center gap-1.5">
        <span className="text-xs text-muted-foreground transition-all duration-500">
          {THINKING_PHRASES[phraseIdx]}
        </span>
        {elapsed >= 15 && (
          <span className="text-[10px] text-amber-500 ml-1">({elapsed}s)</span>
        )}
        <span className="typing-dot text-brand-400" />
        <span className="typing-dot text-brand-400" />
        <span className="typing-dot text-brand-400" />
      </div>
    </div>
  )
}

// ─── Model badge ──────────────────────────────────────────────────────────────
function ModelBadge({ tool, model, showRetry, onRetry }) {
  const displayModel = model === 'minimax' ? 'Minimax-M2.5'
    : model === 'none' ? null
    : model || 'Minimax-M2.5'
  return (
    <div className="flex items-center gap-1.5 mt-2 flex-wrap">
      {tool && (
        <Badge variant="muted" className="text-[10px] h-5">
          <Wrench className="w-2.5 h-2.5" />
          {tool}
        </Badge>
      )}
      {displayModel && (
        <Badge variant="model-qwen" className="text-[10px] h-5">
          {displayModel}
        </Badge>
      )}
      {/* Subtle ghost retry icon — only on the latest assistant message */}
      {showRetry && (
        <button
          onClick={onRetry}
          title="Gửi lại tin nhắn này"
          id="retry-last-msg-btn"
          className="w-5 h-5 flex items-center justify-center rounded text-muted-foreground/50 hover:text-brand-500 hover:bg-brand-50 transition-colors"
        >
          <RefreshCw className="w-3 h-3" />
        </button>
      )}
    </div>
  )
}

// ─── Quick-reply suggestion chips ─────────────────────────────────────────────
// Rendered below bot messages that carry a `suggestions` array.
// action="send"    → immediately calls onSend(text) (goes through _is_confirm or LLM)
// action="prefill" → dispatches agent:prefill_composer so ChatComposer sets & focuses input
function SuggestionChips({ suggestions, onSend, busy }) {
  if (!suggestions?.length) return null

  // Normalize: accept both strings and { label, text, action } objects
  const chips = suggestions.map(s =>
    typeof s === 'string' ? { label: s, text: s, action: 'send' } : s
  )

  const handleChip = (chip) => {
    if (busy) return
    if (chip.action === 'send') {
      onSend?.(chip.text)
    } else {
      // prefill — set the composer input so user can complete the request naturally
      window.dispatchEvent(new CustomEvent('agent:prefill_composer', { detail: { text: chip.text } }))
    }
  }

  return (
    <div className="flex gap-1.5 flex-wrap mt-2.5 max-w-[85%]">
      {chips.map((chip, i) => (
        <button
          key={i}
          onClick={() => handleChip(chip)}
          disabled={busy}
          title={
            chip.action === 'prefill'
              ? `Điền vào ô chat: "${chip.text}"`
              : `Gửi: "${chip.text}"`
          }
          className={cn(
            'text-[11px] font-semibold rounded-full px-2.5 py-1 border transition-all duration-150 disabled:opacity-40 active:scale-95',
            chip.action === 'send'
              ? 'bg-brand-50 text-brand-700 border-brand-200 hover:bg-brand-100 hover:border-brand-300'
              : 'bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100 hover:border-slate-300'
          )}
        >
          {chip.label}
        </button>
      ))}
    </div>
  )
}

// ─── Error bubble ─────────────────────────────────────────────────────────────
function ErrorBubble({ message, onRetry }) {
  return (
    <div className="flex gap-2.5 animate-fade-in">
      <Avatar className="w-8 h-8 flex-shrink-0 bg-red-500">
        <AvatarFallback className="bg-transparent">
          <AlertTriangle className="w-4 h-4 text-white" />
        </AvatarFallback>
      </Avatar>
      <div className="max-w-[85%]">
        <div className="bg-red-50 border border-red-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-chat">
          <p className="text-sm text-red-700 font-medium mb-2">
            {message.content || '⚠️ Yêu cầu thất bại hoặc quá thời gian chờ.'}
          </p>
          {onRetry && (
            <button
              onClick={onRetry}
              id="error-retry-btn"
              className="flex items-center gap-1.5 text-xs font-semibold text-white bg-red-500 hover:bg-red-600 active:scale-95 transition-all px-3 py-1.5 rounded-full"
            >
              <RefreshCw className="w-3 h-3" />
              Thử lại
            </button>
          )}
        </div>
        <span className="text-[10px] text-muted-foreground mt-1 px-1 block">
          {new Date(message.timestamp).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>
    </div>
  )
}

// ─── Single message bubble ────────────────────────────────────────────────────
function MessageBubble({ message, showRetry, onRetry, onSend, busy }) {
  const isUser = message.role === 'user'
  const isThinking = message.role === 'thinking'
  const isError = message.role === 'error'

  if (isThinking) return <TypingIndicator />
  if (isError) return <ErrorBubble message={message} onRetry={onRetry} />

  return (
    <div className={cn('flex gap-2.5 animate-fade-in min-w-0', isUser && 'flex-row-reverse')}>
      {/* Avatar */}
      <Avatar className={cn('w-8 h-8 flex-shrink-0 self-start mt-0.5', isUser ? 'bg-blue-600' : 'bg-gradient-to-br from-brand-500 to-brand-600')}>
        <AvatarFallback className="bg-transparent">
          {isUser
            ? <User className="w-4 h-4 text-white" />
            : <Bot className="w-4 h-4 text-white" />
          }
        </AvatarFallback>
      </Avatar>

      {/* Bubble + chips below */}
      <div className={cn('max-w-[85%] min-w-0', isUser && 'flex flex-col items-end')}>
        <div className={cn(
          'rounded-2xl px-4 py-3 shadow-chat overflow-x-auto',
          isUser
            ? 'bg-gradient-to-br from-brand-500 to-brand-600 text-white rounded-tr-sm'
            : 'bg-white border border-border text-foreground rounded-tl-sm'
        )}>
          {/* Text content */}
          <div className={cn('markdown-content text-sm', isUser && 'text-white [&_code]:bg-white/20 [&_code]:text-white')}>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                table: ({ node, ...props }) => (
                  <div className="overflow-x-auto my-2">
                    <table className="w-full text-xs border-collapse" {...props} />
                  </div>
                ),
                thead: ({ node, ...props }) => (
                  <thead className="bg-brand-50" {...props} />
                ),
                th: ({ node, ...props }) => (
                  <th className="px-3 py-2 text-left font-semibold text-brand-700 border border-border whitespace-nowrap" {...props} />
                ),
                td: ({ node, ...props }) => (
                  <td className="px-3 py-2 text-foreground border border-border" {...props} />
                ),
                tr: ({ node, ...props }) => (
                  <tr className="even:bg-muted/30" {...props} />
                ),
              }}
            >{message.content}</ReactMarkdown>
          </div>

          {/* Rich blocks (only on bot messages) */}
          {!isUser && message.blocks?.map((block, i) => (
            <BlockRenderer key={i} block={block} />
          ))}
        </div>

        {/* Quick-reply suggestion chips — only on bot messages with suggestions */}
        {!isUser && (
          <SuggestionChips suggestions={message.suggestions} onSend={onSend} busy={busy} />
        )}

        {/* Tool/model metadata — with subtle retry icon on latest message */}
        {!isUser && message.metadata?.tool && (
          <ModelBadge
            tool={message.metadata.tool}
            model={message.metadata.model}
            showRetry={showRetry}
            onRetry={onRetry}
          />
        )}

        {/* Timestamp */}
        <span className="text-[10px] text-muted-foreground mt-1 px-1">
          {new Date(message.timestamp).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>
    </div>
  )
}

export default MessageBubble
