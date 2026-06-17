import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn, fmt } from '@/lib/utils'
import {
  CheckCircle2, Loader2, AlertTriangle, Film, Rocket,
  FileText, Users, LayoutGrid, DollarSign, XCircle,
} from 'lucide-react'
import { checkMismatch, getSelectedZones, fmtVnd, fmtImp, estImpressions } from './setupUtils'
import { createCampaignOrder, uploadCreativeFile } from '@/api/agentApi'

const OBJECTIVE_LABELS = {
  awareness: 'Awareness — Tăng nhận biết',
  consideration: 'Consideration — Tăng quan tâm',
  conversion: 'Conversion — Chuyển đổi',
  retention: 'Retention — Giữ chân',
}

function SectionCard({ icon: Icon, title, iconClass, children }) {
  return (
    <Card>
      <CardHeader className="pb-2 pt-3">
        <CardTitle className="text-sm flex items-center gap-2">
          <Icon className={cn('w-4 h-4', iconClass)} />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="pb-3 pt-0">
        {children}
      </CardContent>
    </Card>
  )
}

export default function ConfirmPhase({ data, onChange, brief, segment, files, allZones, recoZones }) {
  const [submitting, setSubmitting] = useState(false)
  const [uploadStatus, setUploadStatus] = useState('')  // upload progress label

  const selectedZones = getSelectedZones(data.selectedZoneIds || [], allZones || null, recoZones || null)
  const assignments = data.assignments || {}
  const budgetPerZone = selectedZones.length > 0 ? (brief?.budget || 0) / selectedZones.length : 0

  const totalMismatch = selectedZones.filter(z => {
    const f = files.find(f => f.id === assignments[z.id])
    return f && checkMismatch(z, f)
  }).length

  // Zones that have booking conflicts with the campaign date range
  const conflictedZones = selectedZones.filter(z => z.conflict)
  const hasConflicts = conflictedZones.length > 0

  const handleCreate = async () => {
    setSubmitting(true)

    // 1. Convert assignments: fileId → fileIndex
    const assignmentsAsIndex = {}
    const uniqueFileIndexes = new Set()
    for (const [zoneId, fileId] of Object.entries(data.assignments || {})) {
      const idx = files.findIndex(f => f.id === fileId)
      const safeIdx = idx >= 0 ? idx : 0
      assignmentsAsIndex[zoneId] = safeIdx
      uniqueFileIndexes.add(safeIdx)
    }

    // 2. Upload each unique creative to AdsPilot VPS to get a real URL
    const fileUrls = {}
    let uploadsDone = 0
    const totalUploads = [...uniqueFileIndexes].filter(idx => files[idx]?.dataUrl).length
    for (const idx of uniqueFileIndexes) {
      const f = files[idx]
      if (!f) continue
      if (f.url) {
        // Already has a URL (previously uploaded)
        fileUrls[String(idx)] = f.url
      } else if (f.dataUrl) {
        uploadsDone++
        setUploadStatus(`Đang tải creative ${uploadsDone}/${totalUploads}...`)
        const url = await uploadCreativeFile(f.dataUrl, f.name, f.type)
        if (url) fileUrls[String(idx)] = url
      }
    }
    setUploadStatus('')

    // 3. Create the order with resolved creative URLs
    await createCampaignOrder(data.selectedZoneIds || [], assignmentsAsIndex, fileUrls)
    onChange({ ...data, submitted: true })
  }

  const dateRange = brief?.startDate && brief?.endDate
    ? `${brief.startDate} → ${brief.endDate}`
    : brief?.startDate || '—'

  return (
    <div className="space-y-3">
      {/* Breadcrumb */}
      <div className="flex items-center gap-1.5 text-xs">
        <button
          onClick={() => onChange({ ...data, phase: 'assign' })}
          className="text-brand-600 hover:underline"
        >
          ← Gắn creative
        </button>
        <span className="text-muted-foreground">/</span>
        <span className="font-semibold text-foreground">Xác nhận & Tạo chiến dịch</span>
      </div>

      {/* Mismatch warning banner */}
      {totalMismatch > 0 && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-50 border border-amber-200">
          <AlertTriangle className="w-4 h-4 text-amber-500 flex-shrink-0" />
          <p className="text-xs text-amber-700 font-medium">
            {totalMismatch} zone có tỷ lệ ảnh không khớp — kiểm tra lại ở bước trước nếu cần.
          </p>
        </div>
      )}

      {/* ── Brief ─────────────────────────────────────────────────────────────── */}
      <SectionCard icon={FileText} title="Brief chiến dịch" iconClass="text-brand-500">
        <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-xs">
          {[
            ['Thương hiệu', brief?.brand],
            ['Mục tiêu', OBJECTIVE_LABELS[brief?.objective] || brief?.objective],
            ['KPI', brief?.kpi],
            ['Ngân sách', `${brief?.budget} triệu VND`],
            ['Thời gian', dateRange],
            ['Ghi chú', brief?.notes],
          ].map(([k, v]) => (
            <div key={k}>
              <span className="text-muted-foreground">{k}: </span>
              <span className="font-semibold text-foreground">{v || '—'}</span>
            </div>
          ))}
        </div>
      </SectionCard>

      {/* ── Audience ──────────────────────────────────────────────────────────── */}
      <SectionCard icon={Users} title="Audience" iconClass="text-blue-500">
        <div className="flex items-center gap-4">
          <div>
            <p className="text-xs text-muted-foreground">Segments đã chọn</p>
            <p className="text-lg font-black text-foreground">{(segment?.attrs || []).length}</p>
          </div>
          <div className="border-l border-border pl-4">
            <p className="text-xs text-muted-foreground">Audience size ước lượng</p>
            <p className="text-lg font-black text-brand-700">{fmt(segment?.size || 0)} người</p>
          </div>
        </div>
        {(segment?.attrs || []).length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-2">
            {segment.attrs.map(a => (
              <Badge key={a._uid || a.code} variant="muted" className="text-[10px]">{a.name}</Badge>
            ))}
          </div>
        )}
      </SectionCard>

      {/* ── Ad Zones ──────────────────────────────────────────────────────────── */}
      <SectionCard icon={LayoutGrid} title={`Ad Zones (${selectedZones.length})`} iconClass="text-violet-500">
        <div className="space-y-2">
          {selectedZones.map(zone => {
            const assignedFile = files.find(f => f.id === assignments[zone.id])
            const mismatch = assignedFile ? checkMismatch(zone, assignedFile) : null
            const imp = estImpressions(zone, budgetPerZone)

            return (
              <div key={zone.id} className={cn(
                'flex items-start gap-3 p-2.5 rounded-lg border',
                mismatch ? 'border-red-200 bg-red-50/30' : 'border-border'
              )}>
                {/* Creative thumbnail */}
                <div className="w-14 h-10 rounded-md overflow-hidden bg-muted/40 flex-shrink-0 border border-border">
                  {assignedFile?.type?.startsWith('image/') ? (
                    <img src={assignedFile.dataUrl} alt={assignedFile.name} className="w-full h-full object-cover" />
                  ) : assignedFile?.type?.startsWith('video/') ? (
                    <div className="w-full h-full flex items-center justify-center bg-violet-50">
                      <Film className="w-4 h-4 text-violet-400" />
                    </div>
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <span className="text-[9px] text-muted-foreground">No img</span>
                    </div>
                  )}
                </div>

                {/* Zone info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-xs font-semibold">{zone.name}</span>
                    <Badge variant="muted" className="text-[9px] h-3.5 px-1">{zone.platform}</Badge>
                    <Badge variant="muted" className="text-[9px] h-3.5 px-1">{zone.size}</Badge>
                  </div>
                  {assignedFile ? (
                    <p className="text-[10px] text-muted-foreground mt-0.5 truncate">
                      🎨 {assignedFile.name}
                      {assignedFile.width ? ` · ${assignedFile.width}×${assignedFile.height}px` : ''}
                    </p>
                  ) : (
                    <p className="text-[10px] text-amber-600 mt-0.5">⚠ Chưa gắn creative</p>
                  )}
                  {mismatch && (
                    <p className="text-[10px] text-red-600 mt-0.5">⚠ {mismatch}</p>
                  )}
                </div>

                {/* Budget + impressions */}
                <div className="text-right flex-shrink-0">
                  <p className="text-xs font-bold text-foreground">{budgetPerZone.toFixed(1)}M</p>
                  <p className="text-[10px] text-muted-foreground">≈{fmtImp(imp)} imps</p>
                  <p className="text-[10px] text-amber-600">CPM {fmtVnd(zone.cpm)}đ</p>
                </div>
              </div>
            )
          })}
        </div>

        {/* Total row */}
        <div className="flex items-center justify-between mt-3 pt-2 border-t border-border">
          <span className="text-xs font-bold text-foreground">Tổng ngân sách</span>
          <span className="text-sm font-black text-brand-700">{brief?.budget}M VND</span>
        </div>
      </SectionCard>

      {/* Conflict blocking banner */}
      {hasConflicts && (
        <Card className="border-red-300 bg-red-50">
          <CardContent className="py-3 space-y-2">
            <div className="flex items-center gap-2">
              <XCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
              <p className="text-xs font-bold text-red-700">
                {conflictedZones.length} zone đang bị đặt bởi chiến dịch khác — không thể tạo chiến dịch
              </p>
            </div>
            <ul className="space-y-1 pl-6">
              {conflictedZones.map(z => (
                <li key={z.id} className="text-[11px] text-red-600 leading-tight">
                  <span className="font-bold">{z.name || z.id}</span>: đang được chiến dịch{' '}
                  <span className="font-bold">&ldquo;{z.conflict.campaignName}&rdquo;</span>{' '}
                  đặt từ {z.conflict.startDate} đến {z.conflict.endDate}
                </li>
              ))}
            </ul>
            <p className="text-[11px] text-red-500 pl-6">
              Vui lòng quay lại bước chọn zone và bỏ chọn các zone đang xung đột.
            </p>
          </CardContent>
        </Card>
      )}

      {/* ── Create button ──────────────────────────────────────────────────────── */}
      {!data.submitted ? (
        <Button
          onClick={handleCreate}
          disabled={submitting || hasConflicts}
          className="w-full gap-2 h-11 text-sm font-bold"
          id="create-campaign-btn"
        >
          {submitting ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              {uploadStatus || 'Đang gọi Agent API · Tạo chiến dịch...'}
            </>
          ) : (
            <>
              <Rocket className="w-5 h-5" />
              Xác nhận & Tạo chiến dịch
            </>
          )}
        </Button>
      ) : (
        <Card className="border-brand-200 bg-brand-50">
          <CardContent className="py-3 flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-brand-500" />
            <p className="text-sm font-semibold text-brand-700">
              Chiến dịch đã được tạo thành công! Đang chuyển sang Kết quả...
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
