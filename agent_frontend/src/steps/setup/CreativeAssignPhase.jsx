import { useEffect } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { Check, AlertTriangle, CheckCircle2, Layers, ArrowRight, Film, Wand2 } from 'lucide-react'
import { checkMismatch, checkAutopilotMismatch, canCheckRatio, scoreFile, getSelectedZones } from './setupUtils'

const isCreativeApproved = (file) =>
  ['auto_approved', 'approved_override'].includes(file.analysisStatus)

// ─── Single creative thumbnail option ─────────────────────────────────────────
function CreativeOption({ file, zone, selected, onSelect, rank, strictCompatibility = false }) {
  const mismatch = strictCompatibility
    ? checkAutopilotMismatch(zone, file)
    : checkMismatch(zone, file)
  const isBest = rank === 0
  const approved = isCreativeApproved(file)
  const incompatible = Boolean(mismatch)

  return (
    <button
      onClick={() => approved && (!incompatible || selected) && onSelect(selected ? null : file.id)}
      disabled={!approved || (incompatible && !selected)}
      className={cn(
        'relative flex flex-col rounded-lg border-2 overflow-hidden text-left transition-all duration-150',
        selected ? 'border-brand-500 shadow-md ring-2 ring-brand-200' : 'border-border hover:border-brand-300',
        (incompatible && !selected) || !approved ? 'opacity-50 cursor-not-allowed' : '',
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
        {incompatible && (
          <div className="absolute top-1 right-1">
            <AlertTriangle className="w-3.5 h-3.5 text-red-500 drop-shadow" />
          </div>
        )}
        {!approved && (
          <p className="text-[9px] text-amber-600 leading-tight mt-0.5">Chưa được duyệt</p>
        )}
      </div>

      {/* Info */}
      <div className="px-1.5 py-1.5 bg-white flex-1">
        <p className="text-[10px] font-semibold text-foreground truncate leading-tight">{file.name}</p>
        <p className="text-[10px] text-muted-foreground mt-0.5">
          {file.width && file.height ? `${file.width}×${file.height}px` : file.type?.split('/')[1]?.toUpperCase()}
        </p>
        {incompatible && (
          <p className="text-[9px] text-red-500 leading-tight mt-0.5">⚠ Tỷ lệ lệch</p>
        )}
      </div>
    </button>
  )
}

// ─── Single zone assignment row ───────────────────────────────────────────────
function AssignRow({
  zone,
  files,
  assignedFileId,
  onAssign,
  onGroupSameSize,
  groupedCount,
  strictCompatibility = false,
  identityAware = false,
}) {
  const assignedFile = files.find(f => f.id === assignedFileId)
  const mismatch = assignedFile
    ? (strictCompatibility
        ? checkAutopilotMismatch(zone, assignedFile)
        : checkMismatch(zone, assignedFile))
    : null

  // Rank files by smart score for this zone
  const rankedFiles = [...files]
    .map(f => ({ ...f, _score: scoreFile(f, zone, { identityAware }) }))
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
              strictCompatibility={strictCompatibility}
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
export default function CreativeAssignPhase({
  data, onChange, files, allZones, recoZones,
  repairMode = false, openaiCampaignFlow = false,
}) {
  const selectedZones = getSelectedZones(data.selectedZoneIds || [], allZones || null, recoZones || null)
  const assignments = data.assignments || {}
  const strictCompatibility = repairMode || openaiCampaignFlow

  const handleAssign = (zoneId, fileId) => {
    onChange({ ...data, assignments: { ...assignments, [zoneId]: fileId } })
  }

  // Autopilot reuses the canonical server recommendation. Guided setup keeps
  // its local scorer because it has no Autopilot assignment artifact.
  const handleAutoAssign = () => {
    const approvedFiles = files.filter(isCreativeApproved)
    if (approvedFiles.length === 0) return
    const newAssignments = { ...assignments }
    const recommended = data.recommendedAssignments || {}
    selectedZones.forEach(zone => {
      const recommendedFile = approvedFiles.find(file =>
        file.id === recommended[zone.id]
      )
      if (repairMode) {
        if (recommendedFile) {
          newAssignments[zone.id] = recommendedFile.id
        } else {
          const bestFallback = [...approvedFiles]
            .map(file => ({
              ...file,
              _score: scoreFile(file, zone, { identityAware: true }),
            }))
            .sort((a, b) => b._score - a._score)
            .at(0)
          if (bestFallback) newAssignments[zone.id] = bestFallback.id
          else delete newAssignments[zone.id]
        }
        return
      }
      const compatibleFiles = strictCompatibility
        ? approvedFiles.filter(file => !checkAutopilotMismatch(zone, file))
        : approvedFiles
      const assignmentPool = compatibleFiles.length ? compatibleFiles : approvedFiles
      const best = [...assignmentPool]
        .map(f => ({
          ...f,
          _score: scoreFile(f, zone, { identityAware: openaiCampaignFlow || repairMode }),
        }))
        .sort((a, b) => b._score - a._score)
        .at(0)
      if (best) newAssignments[zone.id] = best.id
      else delete newAssignments[zone.id]
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
    return f && (strictCompatibility ? checkAutopilotMismatch(z, f) : checkMismatch(z, f))
  }).length

  return (
    <div className="space-y-3" data-demo="autopilot-creative-assignment-editor">
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
              title={repairMode
                ? 'Khôi phục đề xuất đã được Agent kiểm tra theo verdict, format và tỷ lệ'
                : 'Tự động gắn creative phù hợp nhất vào mỗi zone'}
            >
              <Wand2 className="w-3.5 h-3.5" />
              {repairMode ? 'Dùng gán đề xuất' : 'Tự động gắn'}
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
            strictCompatibility={strictCompatibility}
            identityAware={openaiCampaignFlow || repairMode}
          />
        ))}
      </div>

      {/* Guided setup owns order confirmation. Autopilot repairs are persisted
          by the workspace footer so the existing run remains in control. */}
      {repairMode ? (
        <div className="rounded-xl border border-brand-200 bg-brand-50 px-3 py-2.5 text-xs leading-relaxed text-brand-800">
          Gán một creative đã duyệt cho từng placement, sau đó dùng nút
          <strong> Lưu &amp; quay lại Autopilot</strong> ở cuối màn hình.
        </div>
      ) : (
        <Button
          onClick={() => onChange({ ...data, phase: 'confirm' })}
          className="w-full gap-2"
          id="proceed-to-confirm-btn"
        >
          <ArrowRight className="w-4 h-4" />
          Xem tổng kết & xác nhận tạo chiến dịch
        </Button>
      )}
    </div>
  )
}
