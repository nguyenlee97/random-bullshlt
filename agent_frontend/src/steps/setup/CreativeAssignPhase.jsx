import { useEffect } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { Check, AlertTriangle, CheckCircle2, Layers, ArrowRight, Film, Wand2 } from 'lucide-react'
import { checkMismatch, canCheckRatio, scoreFile, getSelectedZones } from './setupUtils'

// ─── Single creative thumbnail option ─────────────────────────────────────────
function CreativeOption({ file, zone, selected, onSelect, rank }) {
  const mismatch = checkMismatch(zone, file)
  const isBest = rank === 0

  return (
    <button
      onClick={() => onSelect(selected ? null : file.id)}
      className={cn(
        'relative flex flex-col rounded-lg border-2 overflow-hidden text-left transition-all duration-150',
        selected ? 'border-brand-500 shadow-md ring-2 ring-brand-200' : 'border-border hover:border-brand-300',
        mismatch && !selected && 'opacity-75',
      )}
      title={file.name}
    >
      {/* Thumbnail */}
      <div className="h-16 bg-muted/40 overflow-hidden relative flex-shrink-0">
        {file.type?.startsWith('image/') ? (
          <img src={file.dataUrl} alt={file.name} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-violet-50">
            <Film className="w-6 h-6 text-violet-400" />
          </div>
        )}

        {/* Badges overlay */}
        {isBest && !selected && (
          <div className="absolute top-1 left-1">
            <span className="text-[8px] font-bold bg-amber-400 text-white px-1 py-0.5 rounded">⭐ Best</span>
          </div>
        )}
        {selected && (
          <div className="absolute inset-0 bg-brand-500/20 flex items-center justify-center">
            <div className="w-6 h-6 rounded-full bg-brand-500 flex items-center justify-center shadow">
              <Check className="w-3.5 h-3.5 text-white" strokeWidth={3} />
            </div>
          </div>
        )}
        {mismatch && (
          <div className="absolute top-1 right-1">
            <AlertTriangle className="w-3.5 h-3.5 text-red-500 drop-shadow" />
          </div>
        )}
      </div>

      {/* Info */}
      <div className="px-1.5 py-1.5 bg-white flex-1">
        <p className="text-[10px] font-semibold text-foreground truncate leading-tight">{file.name}</p>
        <p className="text-[10px] text-muted-foreground mt-0.5">
          {file.width && file.height ? `${file.width}×${file.height}px` : file.type?.split('/')[1]?.toUpperCase()}
        </p>
        {mismatch && (
          <p className="text-[9px] text-red-500 leading-tight mt-0.5">⚠ Tỷ lệ lệch</p>
        )}
      </div>
    </button>
  )
}

// ─── Single zone assignment row ───────────────────────────────────────────────
function AssignRow({ zone, files, assignedFileId, onAssign, onGroupSameSize, groupedCount }) {
  const assignedFile = files.find(f => f.id === assignedFileId)
  const mismatch = assignedFile ? checkMismatch(zone, assignedFile) : null

  // Rank files by smart score for this zone
  const rankedFiles = [...files]
    .map(f => ({ ...f, _score: scoreFile(f, zone) }))
    .sort((a, b) => b._score - a._score)

  return (
    <div className={cn(
      'rounded-xl border p-3 space-y-2.5 transition-all',
      mismatch ? 'border-red-200 bg-red-50/30'
        : assignedFile ? 'border-brand-200 bg-brand-50/20'
          : 'border-border bg-white'
    )}>
      {/* Zone header */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className={cn('w-2 h-2 rounded-full flex-shrink-0', assignedFile ? 'bg-brand-500' : 'bg-muted-foreground/40')} />
        <span className="text-xs font-bold text-foreground flex-1">{zone.name}</span>
        <div className="flex items-center gap-1">
          {[zone.platform, zone.size, zone.format].map(t => (
            <Badge key={t} variant="muted" className="text-[10px] h-4 px-1.5">{t}</Badge>
          ))}
        </div>
      </div>

      {/* Creative thumbnail grid */}
      {files.length === 0 ? (
        <p className="text-xs text-muted-foreground italic pl-4">Chưa có creative — upload ở bước Creative</p>
      ) : (
        <div
          className="grid gap-2 pl-4"
          style={{ gridTemplateColumns: `repeat(${Math.min(files.length, 5)}, minmax(0, 1fr))` }}
        >
          {rankedFiles.map((file, rank) => (
            <CreativeOption
              key={file.id}
              file={file}
              zone={zone}
              selected={file.id === assignedFileId}
              onSelect={(id) => onAssign(zone.id, id)}
              rank={rank}
            />
          ))}
        </div>
      )}

      {/* Status & Group */}
      <div className="flex items-center gap-2 pl-4 flex-wrap">
        {mismatch ? (
          <div className="flex items-start gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5 text-red-500 flex-shrink-0 mt-0.5" />
            <p className="text-[10px] text-red-600">{mismatch}</p>
          </div>
        ) : assignedFile && mismatch === false ? (
          <div className="flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5 text-brand-500" />
            <p className="text-[10px] text-brand-600 font-medium">Tỷ lệ khớp ✓</p>
          </div>
        ) : assignedFile && mismatch === null && !canCheckRatio(zone) ? (
          <p className="text-[10px] text-muted-foreground italic">Skin format — kiểm tỷ lệ thủ công</p>
        ) : null}

        {assignedFile && groupedCount > 0 && (
          <button
            onClick={() => onGroupSameSize(zone, assignedFileId)}
            className="ml-auto flex items-center gap-1 px-2 py-1 rounded-lg border border-dashed border-brand-400 text-brand-600 text-[10px] font-semibold hover:bg-brand-50"
          >
            <Layers className="w-3 h-3" />
            Áp dụng cho {groupedCount} zone cùng tỷ lệ
          </button>
        )}
      </div>
    </div>
  )
}

// ─── Phase 2 component ─────────────────────────────────────────────────────────
export default function CreativeAssignPhase({ data, onChange, files, allZones, recoZones }) {
  const selectedZones = getSelectedZones(data.selectedZoneIds || [], allZones || null, recoZones || null)
  const assignments = data.assignments || {}

  const handleAssign = (zoneId, fileId) => {
    onChange({ ...data, assignments: { ...assignments, [zoneId]: fileId } })
  }

  // Auto-assign: pick best scored file for each zone
  const handleAutoAssign = () => {
    if (files.length === 0) return
    const newAssignments = { ...assignments }
    selectedZones.forEach(zone => {
      const best = [...files]
        .map(f => ({ ...f, _score: scoreFile(f, zone) }))
        .sort((a, b) => b._score - a._score)[0]
      if (best) newAssignments[zone.id] = best.id
    })
    onChange({ ...data, assignments: newAssignments })
  }

  // Listen for auto-assign trigger from chat (agent fires agent:trigger_auto_assign)
  useEffect(() => {
    const handler = () => {
      if (files.length === 0) return
      handleAutoAssign()
    }
    window.addEventListener('agent:trigger_auto_assign', handler)
    return () => window.removeEventListener('agent:trigger_auto_assign', handler)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [files, selectedZones])

  const handleGroupSameSize = (sourceZone, fileId) => {
    const [sw, sh] = sourceZone.size.split('×').map(Number)
    const sRatio = sw / sh
    const newA = { ...assignments }
    selectedZones.forEach(z => {
      const [zw, zh] = z.size.split('×').map(Number)
      if (!zw) return
      if (Math.abs(zw / zh - sRatio) / sRatio < 0.15) newA[z.id] = fileId
    })
    onChange({ ...data, assignments: newA })
  }

  const countGroupable = (sourceZone, fileId) => {
    if (!fileId) return 0
    const [sw, sh] = sourceZone.size.split('×').map(Number)
    if (!sw) return 0
    const sRatio = sw / sh
    return selectedZones.filter(z => {
      if (z.id === sourceZone.id) return false
      const [zw, zh] = z.size.split('×').map(Number)
      return zw && Math.abs(zw / zh - sRatio) / sRatio < 0.15
    }).length
  }

  const assignedCount = selectedZones.filter(z => assignments[z.id]).length
  const mismatchCount = selectedZones.filter(z => {
    const f = files.find(f => f.id === assignments[z.id])
    return f && checkMismatch(z, f)
  }).length

  return (
    <div className="space-y-3">
      {/* Breadcrumb */}
      <div className="flex items-center gap-1.5 text-xs">
        <button
          onClick={() => onChange({ ...data, phase: 'zones', created: false })}
          className="text-brand-600 hover:underline"
        >
          ← Chọn zones
        </button>
        <span className="text-muted-foreground">/</span>
        <span className="font-semibold">Gắn creative</span>
      </div>

      {/* Progress */}
      <Card className="border-brand-200 bg-brand-50">
        <CardContent className="py-3 flex items-center gap-3">
          <div className="flex-1">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-muted-foreground">Đã gắn creative</span>
              <span className="text-xs font-bold text-brand-700">{assignedCount} / {selectedZones.length}</span>
            </div>
            <div className="h-1.5 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-brand-500 rounded-full transition-all"
                style={{ width: selectedZones.length ? `${(assignedCount / selectedZones.length) * 100}%` : '0%' }}
              />
            </div>
          </div>
          {files.length > 0 && (
            <button
              data-demo="auto-assign-btn"
              onClick={handleAutoAssign}
              className="flex-shrink-0 flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-violet-100 hover:bg-violet-200 text-violet-700 text-xs font-semibold transition-colors border border-violet-200"
              title="Tự động gắn creative phù hợp nhất vào mỗi zone"
            >
              <Wand2 className="w-3.5 h-3.5" />
              Tự động gắn
            </button>
          )}
          {mismatchCount > 0 && (
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-red-50 border border-red-200 flex-shrink-0">
              <AlertTriangle className="w-3.5 h-3.5 text-red-500" />
              <span className="text-xs font-semibold text-red-600">{mismatchCount} lỗi tỷ lệ</span>
            </div>
          )}
        </CardContent>
      </Card>

      {files.length === 0 && (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="py-3 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-amber-700">
              Chưa upload creative. Có thể bỏ qua nhưng cần gắn trước khi chạy thật.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Assignment rows */}
      <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1 -mr-1">
        {selectedZones.map(zone => (
          <AssignRow
            key={zone.id}
            zone={zone}
            files={files}
            assignedFileId={assignments[zone.id]}
            onAssign={handleAssign}
            onGroupSameSize={handleGroupSameSize}
            groupedCount={countGroupable(zone, assignments[zone.id])}
          />
        ))}
      </div>

      {/* Proceed to confirm */}
      <Button
        onClick={() => onChange({ ...data, phase: 'confirm' })}
        className="w-full gap-2"
        id="proceed-to-confirm-btn"
      >
        <ArrowRight className="w-4 h-4" />
        Xem tổng kết & xác nhận tạo chiến dịch
      </Button>
    </div>
  )
}
