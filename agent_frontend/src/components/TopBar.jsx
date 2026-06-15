import { Bot, Zap, RotateCcw, MessageSquarePlus } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'

export default function TopBar({ onReset, onNewChat }) {
  return (
    <header className="h-14 flex items-center gap-3 px-5 border-b border-border bg-white/95 backdrop-blur-md shadow-sm flex-shrink-0 z-10">
      {/* Logo */}
      <div className="flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-brand-600 flex items-center justify-center shadow-sm">
          <Bot className="w-4.5 h-4.5 text-white" strokeWidth={2.5} />
        </div>
        <div className="flex items-baseline gap-1.5">
          <span className="font-black text-base text-brand-700 tracking-tight">Camp</span>
          <span className="font-black text-base text-amber-500 tracking-tight">Ads</span>
          <span className="font-black text-base text-brand-700 tracking-tight">Agent</span>
        </div>
      </div>

      <Separator orientation="vertical" className="h-5 mx-1" />

      <Badge variant="muted" className="gap-1.5 text-[11px]">
        <div className="w-1.5 h-1.5 rounded-full bg-brand-500 animate-pulse" />
        v2.0.0.1 · AdsPilot
      </Badge>

      <Badge variant="model-qwen" className="text-[11px]">
        <Zap className="w-3 h-3" />
        Minimax-M2.5
      </Badge>

      <div className="ml-auto flex items-center gap-2">
        <span className="text-xs text-muted-foreground hidden sm:block">
          Powered by GreenNode AI
        </span>
        {/* New Chat — clears chat + resets workspace */}
        <Button
          variant="default"
          size="sm"
          onClick={onNewChat}
          className="gap-1.5 text-xs h-8 bg-brand-500 hover:bg-brand-600"
          id="new-chat-btn"
        >
          <MessageSquarePlus className="w-3.5 h-3.5" />
          New Chat
        </Button>
        {/* Đặt lại — workspace reset only */}
        <Button variant="outline" size="sm" onClick={onReset} className="gap-1.5 text-xs h-8">
          <RotateCcw className="w-3.5 h-3.5" />
          Đặt lại
        </Button>
      </div>
    </header>
  )
}
