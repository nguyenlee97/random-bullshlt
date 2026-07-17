import { useEffect, useCallback, useState, useRef } from 'react'
import { Loader2 } from 'lucide-react'
import { fetchZonesFromAgent } from '@/api/agentApi'
import { ALL_ZONES, getRecommendedZones } from '@/data/zones'
import ZoneSelectionPhase from './setup/ZoneSelectionPhase'
import CreativeAssignPhase from './setup/CreativeAssignPhase'
import ConfirmPhase from './setup/ConfirmPhase'

function zoneNameFromId(id) { return id.replace(/_/g, ' ') }
function platformFromId(id) { return id.split('_')[0] || id }
function placementFromId(id) { return id.split('_').slice(1).join(' ') || id }

export default function SetupStep({ data, onChange, brief, creative, segment, isDone, assignmentRepair = false }) {
  const files = creative?.files || []
  const phase = assignmentRepair ? 'assign' : (data.phase || 'zones')
  const isInitialized = data.initialized || false
  const allZones = data.allZones || ALL_ZONES
  const recoZones = data.recoZones || []

  // ── Fallback fetch ───────────────────────────────────────────────────────────
  // Primary flow: App.jsx setup-entry populates formState.setup via workspace_proposal.
  // This fallback fires only if setup-entry fails/times out (initialized stays false).
  const fallbackFiredRef = useRef(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (isInitialized || fallbackFiredRef.current || loading) return
    // Wait 3 s for setup-entry to arrive before falling back
    const timer = setTimeout(async () => {
      if (isInitialized) return  // setup-entry arrived in time
      fallbackFiredRef.current = true
      setLoading(true)
      try {
        const result = await fetchZonesFromAgent()
        if (result?.zones?.length) {
          const staticMap = Object.fromEntries(ALL_ZONES.map(z => [z.id, z]))
          const mappedZones = result.zones.map(z => {
            const staticZone = staticMap[z.id] || {}
            return {
              ...staticZone,
              id: z.id,
              reach: z.reach, vi: z.vi, ctr: z.ctr, cpm: z.cpm,
              format: z.format || staticZone.format,
              size: z.size || staticZone.size,
              score: z.score, reason: z.reason,
              est_impressions: z.est_impressions,
              recommended: z.recommended,
              conflict: z.conflict || null,
              siteUrl: z.siteUrl || staticZone.siteUrl || null,
              name: staticZone.name || zoneNameFromId(z.id),
              platform: staticZone.platform || z.channel || platformFromId(z.id),
              placement: staticZone.placement || placementFromId(z.id),
            }
          })
          const recoZones = mappedZones.filter(z => result.recommended_ids.includes(z.id))
          onChange({
            ...data,
            recoZones, allZones: mappedZones,
            selectedZoneIds: recoZones.map(z => z.id),
            initialized: true, created: false, phase: 'zones', assignments: {}, submitted: false,
          })
          setLoading(false)
          return
        }
      } catch (e) {
        console.warn('[SetupStep] fallback zones failed:', e.message)
      }
      // Static fallback
      const zones = getRecommendedZones(brief?.objective || 'awareness', brief?.budget || 100)
      onChange({
        ...data,
        recoZones: zones, allZones: ALL_ZONES,
        selectedZoneIds: zones.map(z => z.id),
        initialized: true, created: false, phase: 'zones', assignments: {}, submitted: false,
      })
      setLoading(false)
    }, 3000)
    return () => clearTimeout(timer)
  }, [isInitialized])   // eslint-disable-line react-hooks/exhaustive-deps

  // ── Loading overlay ─────────────────────────────────────────────────────────
  if (!isInitialized || loading) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-4">
        <div className="w-16 h-16 rounded-2xl bg-violet-50 border border-violet-200 flex items-center justify-center">
          <Loader2 className="w-8 h-8 animate-spin text-violet-500" />
        </div>
        <div className="text-center space-y-1">
          <p className="font-semibold text-foreground">AI đang phân tích zones tối ưu...</p>
          <p className="text-xs text-muted-foreground">
            Objective: <strong>{brief?.objective}</strong> · Budget: <strong>{brief?.budget}M VND</strong>
          </p>
        </div>
      </div>
    )
  }

  // ── Done state (after submission) ───────────────────────────────────────────
  if (isDone) {
    const zones = allZones.filter(z => (data.selectedZoneIds || []).includes(z.id))
    return (
      <div className="space-y-3">
        {/* Success banner */}
        <div className="rounded-xl border border-brand-200 bg-brand-50 p-4 space-y-1">
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 rounded-full bg-brand-500 flex items-center justify-center flex-shrink-0">
              <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <p className="text-sm font-semibold text-brand-700">Chiến dịch đã được tạo thành công!</p>
          </div>
          <p className="text-xs text-brand-600 pl-7">
            {(data.selectedZoneIds || []).length} zones · {brief?.budget}M VND · {brief?.startDate} → {brief?.endDate}
          </p>
        </div>

        {/* Per-zone live links */}
        {zones.length > 0 && (
          <div className="rounded-xl border border-border bg-white p-3 space-y-2">
            <p className="text-xs font-bold text-foreground">🔗 Kiểm tra quảng cáo live</p>
            <div className="space-y-1.5">
              {zones.map(z => {
                const url = z.siteUrl || null
                return (
                  <div key={z.id} className="flex items-center justify-between gap-2 rounded-lg bg-slate-50 px-3 py-2">
                    <div className="min-w-0">
                      <p className="text-xs font-semibold text-foreground truncate">{z.name || z.id}</p>
                      <p className="text-[10px] text-muted-foreground">{z.platform || z.channel || ''} · {z.format}</p>
                    </div>
                    {url ? (
                      <a
                        href={url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex-shrink-0 text-[11px] font-semibold text-brand-600 hover:text-brand-700 bg-brand-50 hover:bg-brand-100 border border-brand-200 rounded-lg px-2.5 py-1 transition-colors whitespace-nowrap"
                        id={`live-link-${z.id}`}
                      >
                        Xem live →
                      </a>
                    ) : (
                      <span className="flex-shrink-0 text-[11px] text-muted-foreground italic">Không có test site</span>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
    )
  }

  // ── Phase routing ────────────────────────────────────────────────────────────
  if (phase === 'assign') {
    return (
      <CreativeAssignPhase
        data={data}
        onChange={onChange}
        files={files}
        allZones={allZones}
        recoZones={recoZones}
        repairMode={assignmentRepair}
      />
    )
  }

  if (phase === 'confirm') {
    return (
      <ConfirmPhase
        data={data}
        onChange={onChange}
        brief={brief}
        segment={segment}
        files={files}
        allZones={allZones}
        recoZones={recoZones}
      />
    )
  }

  // Default: zone selection
  return (
    <ZoneSelectionPhase
      data={data}
      onChange={onChange}
      brief={brief}
      allZones={allZones}
    />
  )
}
