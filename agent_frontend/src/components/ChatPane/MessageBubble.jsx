import ReactMarkdown from 'react-markdown'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import BlockRenderer from '@/blocks/BlockRenderer'
import { Bot, User, Wrench } from 'lucide-react'

// ─── Typing indicator ─────────────────────────────────────────────────────────
function TypingIndicator() {
  return (
    <div className="flex gap-2.5 animate-fade-in">
      <Avatar className="w-8 h-8 flex-shrink-0 bg-gradient-to-br from-brand-500 to-brand-600">
        <AvatarFallback className="bg-transparent">
          <Bot className="w-4 h-4 text-white" />
        </AvatarFallback>
      </Avatar>
      <div className="bg-white rounded-2xl rounded-tl-sm border border-border shadow-chat px-4 py-3 flex items-center gap-1.5 max-w-[200px]">
        <span className="text-xs text-muted-foreground mr-1">Đang xử lý</span>
        <span className="typing-dot text-brand-400" />
        <span className="typing-dot text-brand-400" />
        <span className="typing-dot text-brand-400" />
      </div>
    </div>
  )
}

// ─── Model badge ──────────────────────────────────────────────────────────────
function ModelBadge({ tool, model }) {
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
    </div>
  )
}

// ─── Single message bubble ────────────────────────────────────────────────────
function MessageBubble({ message }) {
  const isUser = message.role === 'user'
  const isThinking = message.role === 'thinking'

  if (isThinking) return <TypingIndicator />

  return (
    <div className={cn('flex gap-2.5 animate-fade-in', isUser && 'flex-row-reverse')}>
      {/* Avatar */}
      <Avatar className={cn('w-8 h-8 flex-shrink-0 self-start mt-0.5', isUser ? 'bg-blue-600' : 'bg-gradient-to-br from-brand-500 to-brand-600')}>
        <AvatarFallback className="bg-transparent">
          {isUser
            ? <User className="w-4 h-4 text-white" />
            : <Bot className="w-4 h-4 text-white" />
          }
        </AvatarFallback>
      </Avatar>

      {/* Bubble */}
      <div className={cn('max-w-[85%] min-w-0', isUser && 'flex flex-col items-end')}>
        <div className={cn(
          'rounded-2xl px-4 py-3 shadow-chat',
          isUser
            ? 'bg-gradient-to-br from-brand-500 to-brand-600 text-white rounded-tr-sm'
            : 'bg-white border border-border text-foreground rounded-tl-sm'
        )}>
          {/* Text content */}
          <div className={cn('markdown-content text-sm', isUser && 'text-white [&_code]:bg-white/20 [&_code]:text-white')}>
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>

          {/* Rich blocks (only on bot messages) */}
          {!isUser && message.blocks?.map((block, i) => (
            <BlockRenderer key={i} block={block} />
          ))}
        </div>

        {/* Tool/model metadata */}
        {!isUser && message.metadata?.tool && (
          <ModelBadge tool={message.metadata.tool} model={message.metadata.model} />
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
