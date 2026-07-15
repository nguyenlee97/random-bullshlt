import { Bot, Zap, RotateCcw, MessageSquarePlus, Play, FileText } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { useDemo } from '@/demo/DemoEngine'

export default function TopBar({ onReset, onNewChat, showDemo, experienceMode }) {
  const demo = useDemo()

  return (
    <header className="h-14 flex items-center gap-3 px-5 border-b border-border bg-white/95 backdrop-blur-md shadow-sm flex-shrink-0 z-10">
      {/* Logo */}
      <div className="flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-brand-600 flex items-center justify-center shadow-sm">
          <Bot className="w-4.5 h-4.5 text-white" strokeWidth={2.5} />
        </div>
        <div className="hidden sm:flex items-baseline gap-1.5">
          <span className="font-black text-base text-slate-900 tracking-tight">Advertising</span>
          <span className="font-black text-base text-brand-600 tracking-tight">Agent</span>
        </div>
      </div>

      <Separator orientation="vertical" className="h-5 mx-1 hidden sm:block" />

      <Badge variant="muted" className="gap-1.5 text-[11px] hidden sm:flex">
        <div className="w-1.5 h-1.5 rounded-full bg-brand-500 animate-pulse" />
        {experienceMode === 'autopilot' ? 'Campaign Autopilot' : 'Guided Workflow'}
      </Badge>

      <Badge variant="model-qwen" className="text-[11px] hidden sm:flex">
        <Zap className="w-3 h-3" />
        Minimax-M2.5
      </Badge>

      <div className="ml-auto flex items-center gap-2">

        {/* Technical docs — opens standalone report page */}
        <Button
          variant="outline"
          size="sm"
          onClick={() => { window.location.href = '/tech-docs.html' }}
          className="gap-1.5 text-xs h-8"
          title="Tài liệu kỹ thuật"
          aria-label="Mở tài liệu kỹ thuật"
          id="tech-docs-btn"
        >
          <FileText className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Docs</span>
        </Button>

        {/* Demo button — available on all viewports, hidden once user starts interacting */}
        {showDemo && demo && (
          <Button
            variant="outline"
            size="sm"
            onClick={demo.startDemo}
            className="flex gap-1.5 text-xs h-8 border-amber-300 bg-amber-50 text-amber-700 hover:bg-amber-100 hover:border-amber-400 animate-pulse hover:animate-none"
            id="demo-btn"
            aria-label="Bắt đầu demo hướng dẫn"
          >
            <Play className="w-3.5 h-3.5" />
            Demo
          </Button>
        )}

        {/* New Chat — clears chat + resets workspace */}
        <Button
          variant="default"
          size="sm"
          onClick={onNewChat}
          className="gap-1.5 text-xs h-8 bg-brand-500 hover:bg-brand-600"
          id="new-chat-btn"
          aria-label="Bắt đầu campaign mới"
        >
          <MessageSquarePlus className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">New Chat</span>
        </Button>
        {/* Đặt lại — workspace reset only */}
        <Button variant="outline" size="sm" onClick={onReset} className="gap-1.5 text-xs h-8" data-demo="reset-btn" aria-label="Đặt lại workspace">
          <RotateCcw className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Đặt lại</span>
        </Button>
      </div>
    </header>
  )
}
