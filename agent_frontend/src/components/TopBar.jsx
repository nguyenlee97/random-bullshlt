import { Bot, RotateCcw, Home, Play, FileText, History } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useDemo } from '@/demo/DemoEngine'
import AccountMenu from '@/components/AccountMenu'

export default function TopBar({
  onReset, onNewChat, onOpenHistory, showDemo, experienceMode,
  identity, identityBusy, onLogin, onLogout, onLoadSessions, onRevokeSession,
  onLinkZalo, onOpenZaloOA, onUnlinkZaloOA,
}) {
  const demo = useDemo()

  return (
    <header className="h-14 flex items-center gap-2 px-2 sm:gap-3 sm:px-5 border-b border-border bg-white/95 backdrop-blur-md shadow-sm flex-shrink-0 z-10">
      {/* Logo */}
      <div className="flex shrink-0 items-center gap-2.5">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-brand-600 flex items-center justify-center shadow-sm">
          <Bot className="w-4.5 h-4.5 text-white" strokeWidth={2.5} />
        </div>
        <div className="hidden sm:flex items-baseline gap-1.5">
          <span className="font-black text-base text-slate-900 tracking-tight">Advertising</span>
          <span className="font-black text-base text-brand-600 tracking-tight">Agent</span>
        </div>
      </div>

      <div className="ml-auto flex min-w-0 items-center gap-1 sm:gap-2">

        <AccountMenu identity={identity} busy={identityBusy} onLogin={onLogin} onLogout={onLogout}
          onLoadSessions={onLoadSessions} onRevokeSession={onRevokeSession}
          onLinkZalo={onLinkZalo} onOpenZaloOA={onOpenZaloOA} onUnlinkZaloOA={onUnlinkZaloOA} compact />

        <Button
          variant="outline"
          size="sm"
          onClick={onOpenHistory}
          className="h-8 shrink-0 gap-1.5 px-2 text-xs sm:px-3"
          title="Lịch sử chiến dịch"
          aria-label="Mở lịch sử chiến dịch"
          id="conversation-history-btn"
        >
          <History className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Lịch sử</span>
        </Button>

        {/* Technical docs — opens standalone report page */}
        <Button
          variant="outline"
          size="sm"
          onClick={() => { window.location.href = '/tech-docs.html' }}
          className="h-8 shrink-0 gap-1.5 px-2 text-xs sm:px-3"
          title="Tài liệu kỹ thuật"
          aria-label="Mở tài liệu kỹ thuật"
          id="tech-docs-btn"
        >
          <FileText className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Docs</span>
        </Button>

        {/* Guided tour stays discoverable after workspace entry. */}
        {showDemo && demo && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => demo.startDemo(experienceMode === 'autopilot' ? 'autopilot' : 'copilot')}
            className="flex h-8 shrink-0 gap-1.5 border-amber-300 bg-amber-50 px-2 text-xs text-amber-700 hover:border-amber-400 hover:bg-amber-100 hover:animate-none sm:px-3 sm:animate-pulse"
            id="demo-btn"
            aria-label="Bắt đầu guided tour"
          >
            <Play className="w-3.5 h-3.5" />
            <span className="hidden min-[400px]:inline">Tour</span>
          </Button>
        )}

        {/* Mode selection lives on the campaign homepage. */}
        <Button
          variant="default"
          size="sm"
          onClick={onNewChat}
          className="h-8 shrink-0 gap-1.5 bg-brand-500 px-2 text-xs hover:bg-brand-600 sm:px-3"
          id="new-chat-btn"
          aria-label="Về trang chủ và bắt đầu campaign mới"
        >
          <Home className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Trang chủ</span>
        </Button>
        {/* Đặt lại — workspace reset only */}
        <Button variant="outline" size="sm" onClick={onReset} className="h-8 shrink-0 gap-1.5 px-2 text-xs sm:px-3" data-demo="reset-btn" aria-label="Đặt lại workspace">
          <RotateCcw className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Đặt lại</span>
        </Button>
      </div>
    </header>
  )
}
