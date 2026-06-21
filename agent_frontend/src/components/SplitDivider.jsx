import { useRef } from 'react'
import { cn } from '@/lib/utils'
import { ChevronUp, ChevronDown, MessageSquare, LayoutDashboard } from 'lucide-react'

/**
 * SplitDivider — draggable horizontal divider for the mobile vertical split layout.
 *
 * The entire bar is the drag target (not just the center dots).
 * Buttons stop pointer propagation so they don't accidentally start a drag.
 *
 * Activity notifications:
 * - chatHasNew   → pulse dot on the Chat button   (new agent message while workspace is expanded)
 * - workspaceHasNew → pulse dot on the Work button (workspace updated while chat is expanded)
 */
export default function SplitDivider({
  onDrag,
  splitRatio,
  onWorkspaceExpand,
  onChatExpand,
  chatHasNew = false,
  workspaceHasNew = false,
}) {
  const lastY = useRef(null)

  // ── Drag handlers on the OUTER bar ─────────────────────────────────────────
  // Buttons use e.stopPropagation() on pointerdown to avoid triggering drag.
  const handlePointerDown = (e) => {
    e.currentTarget.setPointerCapture(e.pointerId)
    lastY.current = e.clientY
  }

  const handlePointerMove = (e) => {
    if (lastY.current === null) return
    const deltaY = e.clientY - lastY.current
    lastY.current = e.clientY
    onDrag(deltaY)
  }

  const handlePointerUp = () => {
    lastY.current = null
  }

  const isWorkspaceExpanded = splitRatio <= 0.32  // workspace at ~70%+
  const isChatExpanded      = splitRatio >= 0.83  // chat at ~85%

  return (
    <div
      className="md:hidden flex-shrink-0 h-10 flex items-center z-10
                 bg-gradient-to-r from-slate-50 via-white to-slate-50
                 border-y border-border/60 cursor-row-resize touch-none select-none"
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerUp}
      role="separator"
      aria-label="Kéo để điều chỉnh kích thước"
    >

      {/* ── Expand Workspace button ─────────────────────────────────────── */}
      <div className="relative flex-shrink-0 mx-1.5">
        <button
          onPointerDown={e => e.stopPropagation()}  // don't start drag on button tap
          onClick={onWorkspaceExpand}
          className={cn(
            'flex items-center gap-1 text-[11px] font-semibold px-2.5 py-1.5 rounded-full transition-all',
            isWorkspaceExpanded
              ? 'bg-violet-100 text-violet-700 border border-violet-200'
              : 'text-muted-foreground hover:bg-muted/60 border border-transparent'
          )}
        >
          <LayoutDashboard className="w-3 h-3" />
          <ChevronUp className="w-3 h-3" />
        </button>

        {/* Activity pulse — workspace updated while user is looking at chat */}
        {!isWorkspaceExpanded && workspaceHasNew && (
          <span className="absolute -top-0.5 -right-0.5 flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-violet-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-violet-500" />
          </span>
        )}
      </div>

      {/* ── Center grip dots (visual only — drag is on the whole bar) ──── */}
      <div className="flex-1 flex items-center justify-center gap-[3px] pointer-events-none">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="w-1 h-1 rounded-full bg-slate-300" />
        ))}
      </div>

      {/* ── Expand Chat button ──────────────────────────────────────────── */}
      <div className="relative flex-shrink-0 mx-1.5">
        <button
          onPointerDown={e => e.stopPropagation()}  // don't start drag on button tap
          onClick={onChatExpand}
          className={cn(
            'flex items-center gap-1 text-[11px] font-semibold px-2.5 py-1.5 rounded-full transition-all',
            isChatExpanded
              ? 'bg-brand-100 text-brand-700 border border-brand-200'
              : 'text-muted-foreground hover:bg-muted/60 border border-transparent'
          )}
        >
          <ChevronDown className="w-3 h-3" />
          <MessageSquare className="w-3 h-3" />
        </button>

        {/* Activity pulse — new agent message while user is looking at workspace */}
        {!isChatExpanded && chatHasNew && (
          <span className="absolute -top-0.5 -right-0.5 flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-brand-500" />
          </span>
        )}
      </div>

    </div>
  )
}
