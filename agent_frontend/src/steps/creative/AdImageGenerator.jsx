import { useState, useEffect, useCallback, useRef } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import {
  Sparkles, Loader2, CheckCircle2, AlertCircle, ChevronDown, ChevronUp,
  X, PlusCircle, ImageIcon, ZoomIn, Wand2, Pencil, Clock3,
} from 'lucide-react'
import { AgentAPI } from '@/api/agentApi'
import { AD_FORMATS, AD_FORMATS_MAP } from '@/data/adFormats'
import { creativeImageCrossOrigin, creativeImageSource } from '@/lib/creativeImageUrl'
import ImageCropModal from './ImageCropModal'
import {
  MAX_CONCURRENT_GENERATIONS,
  MAX_PENDING_GENERATIONS,
  canEnqueueGeneration,
  countActiveGenerations,
  countPendingGenerations,
  nextQueuedGenerations,
} from './generationQueue'

function galleryImage(job) {
  const result = job.result || {}
  const metadata = job.metadata || {}
  const formatId = metadata.format_id || job.formatId || ''
  const finalUrl = result.final_url || ''
  return {
    id: job.job_id,
    name: result.final_filename || `ai-${formatId}-${job.job_id}.png`,
    type: result.final_mime_type || 'image/png',
    size: result.bytes || 0,
    dataUrl: creativeImageSource(finalUrl),
    url: finalUrl,
    width: result.width || AD_FORMATS_MAP[formatId]?.width,
    height: result.height || AD_FORMATS_MAP[formatId]?.height,
    formatId,
    aiGenerated: true,
    generation: {
      provider: metadata.provider,
      model: metadata.model,
      promptVersion: metadata.promptVersion,
      promptFingerprint: metadata.promptFingerprint,
      generationSize: metadata.generationSize,
      finalSize: metadata.finalSize,
      jobId: job.job_id,
      requestId: result.request_id,
      assetIds: metadata.asset_ids || [],
    },
  }
}

// ─── Format Card ──────────────────────────────────────────────────────────────
function FormatCard({ fmt, selected, onClick }) {
  const ratio = (fmt.width / fmt.height).toFixed(1)
  const isWide  = fmt.width > fmt.height
  const isTall  = fmt.height > fmt.width
  const isSq    = Math.abs(fmt.width - fmt.height) < 100

  return (
    <button
      onClick={() => onClick(fmt.id)}
      className={cn(
        'w-full text-left p-3 rounded-xl border transition-all duration-150 flex items-start gap-3',
        selected
          ? 'border-violet-400 bg-violet-50 shadow-sm ring-1 ring-violet-300'
          : 'border-border bg-white hover:border-violet-300 hover:bg-violet-50/40',
      )}
      id={`format-${fmt.id}`}
    >
      {/* Aspect ratio preview swatch */}
      <div className="flex-shrink-0 flex items-center justify-center w-10 h-10 rounded-lg bg-muted/50 border border-border">
        <div
          className={cn(
            'bg-violet-400 rounded-sm',
            isWide ? 'w-8 h-2' : isTall ? 'w-2 h-8' : isSq ? 'w-5 h-5' : 'w-6 h-4'
          )}
        />
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-xs font-bold text-foreground">{fmt.label}</span>
          {selected && <CheckCircle2 className="w-3.5 h-3.5 text-violet-500 flex-shrink-0" />}
        </div>
        <p className="text-[10px] text-muted-foreground mt-0.5">
          {fmt.width} × {fmt.height}px · {ratio}:1
        </p>
        <p className="text-[10px] text-violet-700/80 mt-0.5 leading-tight">{fmt.usageHint}</p>
      </div>
    </button>
  )
}

// ─── Generated Image Card ─────────────────────────────────────────────────────
function GenImageCard({ img, selected, onToggle, onRemove, onPreview }) {
  const fmt = AD_FORMATS_MAP[img.formatId] || {}
  return (
    <div
      className={cn(
        'relative rounded-xl border overflow-hidden transition-all duration-150 group',
        selected
          ? 'border-violet-400 ring-2 ring-violet-300 shadow-md'
          : 'border-border hover:border-violet-300',
      )}
      id={`gen-img-${img.id}`}
    >
      <div className="relative cursor-pointer" onClick={() => onPreview(img)}>
        <img
          src={img.dataUrl}
          alt={img.name}
          className="w-full h-28 object-cover"
        />
        {/* Zoom overlay on hover */}
        <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
          <div className="w-9 h-9 rounded-full bg-white/90 flex items-center justify-center">
            <ZoomIn className="w-4 h-4" />
          </div>
        </div>
        {/* Selection checkbox */}
        <div
          className={cn(
            'absolute top-1.5 left-1.5 w-5 h-5 rounded-full border-2 flex items-center justify-center transition-all cursor-pointer',
            selected ? 'bg-violet-500 border-violet-500' : 'bg-white/80 border-white hover:border-violet-400',
          )}
          onClick={(e) => { e.stopPropagation(); onToggle(img.id) }}
        >
          {selected && <CheckCircle2 className="w-3 h-3 text-white" />}
        </div>
        {/* Remove button */}
        <button
          onClick={(e) => { e.stopPropagation(); onRemove(img.id) }}
          className="absolute top-1.5 right-1.5 w-5 h-5 rounded-full bg-black/60 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-500"
        >
          <X className="w-2.5 h-2.5" />
        </button>
      </div>
      {/* Footer */}
      <div
        className="px-2 py-1.5 cursor-pointer hover:bg-muted/30 transition-colors"
        onClick={() => onToggle(img.id)}
        data-demo="gen-img-footer"
      >
        <p className="text-[10px] font-semibold text-foreground truncate">{fmt.label || img.name}</p>
        <p className="text-[10px] text-muted-foreground">{img.width}×{img.height}px</p>
      </div>
    </div>
  )
}

// ─── Lightbox (for generated images) ─────────────────────────────────────────
function GenLightbox({ img, onClose }) {
  if (!img) return null
  const fmt = AD_FORMATS_MAP[img.formatId] || {}
  return (
    <div
      className="fixed inset-0 z-50 bg-black/85 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div className="relative max-w-5xl max-h-full" onClick={e => e.stopPropagation()}>
        <button
          onClick={onClose}
          className="absolute -top-3 -right-3 z-10 w-8 h-8 rounded-full bg-white shadow-lg flex items-center justify-center hover:bg-gray-100"
        >
          <X className="w-4 h-4" />
        </button>
        <img
          src={img.dataUrl}
          alt={img.name}
          className="max-w-full max-h-[85vh] object-contain rounded-lg shadow-2xl"
        />
        <p className="text-white/80 text-sm text-center mt-3 font-medium">
          {fmt.label || img.name}
          <span className="ml-2 text-white/50 text-xs">{img.width}×{img.height}px</span>
        </p>
      </div>
    </div>
  )
}

// ─── Main Component ───────────────────────────────────────────────────────────
export default function AdImageGenerator({
  brief,
  segment,
  onAddToCreative,
  openaiCampaignFlow = false,
}) {
  const [selectedFormatId, setSelectedFormatId] = useState(null)
  const [error, setError]                       = useState('')
  const [generationJobs, setGenerationJobs]     = useState([])
  const [hiddenJobIds, setHiddenJobIds]         = useState(new Set())
  const [deferredCropIds, setDeferredCropIds]   = useState(new Set())
  const [finalizing, setFinalizing]             = useState(false)
  const [selectedIds, setSelectedIds]           = useState(new Set())
  const [briefExpanded, setBriefExpanded]       = useState(false)
  const [lightboxImg, setLightboxImg]           = useState(null)
  const [customPrompt, setCustomPrompt]         = useState('')
  const [promptExpanded, setPromptExpanded]     = useState(false)
  const [assets, setAssets]                     = useState([])
  const [selectedAssetIds, setSelectedAssetIds] = useState(new Set())
  const [assetDraft, setAssetDraft]             = useState({ name: '', kind: 'logo', useInstruction: '', required: true })
  const [assetUploading, setAssetUploading]      = useState(false)
  const [promptSpec, setPromptSpec]              = useState(null)
  const [composingPrompt, setComposingPrompt]    = useState(false)
  const startedGenerationIds = useRef(new Set())

  // Pending crop: raw response waiting for user crop action
  // { b64, formatId, width, height }
  const [pendingCrop, setPendingCrop] = useState(null)

  const refreshGeneratedJobs = useCallback(async () => {
    const jobs = await AgentAPI.listGeneratedImages()
    setGenerationJobs(previous => {
      const serverIds = new Set(jobs.map(job => job.job_id))
      const localOnly = previous.filter(job => job.localOnly && !serverIds.has(job.job_id))
      return [...jobs, ...localOnly]
    })
  }, [])

  useEffect(() => {
    AgentAPI.listCreativeAssets().then(setAssets)
    refreshGeneratedJobs()
  }, [refreshGeneratedJobs])

  const activeGenerationCount = countActiveGenerations(generationJobs)
  const pendingGenerationCount = countPendingGenerations(generationJobs)
  const queuedGenerationCount = generationJobs.filter(job => job.status === 'queued').length
  const generating = activeGenerationCount > 0

  useEffect(() => {
    if (!generationJobs.some(job => ['reserved', 'ambiguous'].includes(job.status))) return undefined
    const timer = window.setInterval(refreshGeneratedJobs, 3000)
    return () => window.clearInterval(timer)
  }, [generationJobs, refreshGeneratedJobs])

  const runGenerationJob = useCallback(async job => {
    const request = job.request || {}
    try {
      const result = await AgentAPI.generateAdImage(
        request.brief,
        request.formatId,
        request.customPrompt,
        {
          assetIds: request.assetIds,
          promptSpec: request.promptSpec,
          quality: request.quality,
          campaignFlow: request.campaignFlow,
          audienceContext: request.audienceContext,
          idempotencyKey: job.job_id,
        },
      )

      if (!result.ok) {
        const unavailableToday = result.remaining === 0
          || result.status === 'quota_exhausted'
          || result.quota?.status === 'quota_exhausted'
        setError(unavailableToday
          ? 'Tạm thời chưa thể tạo thêm ảnh hôm nay. Vui lòng thử lại vào ngày mai.'
          : (result.error || 'Tạo ảnh thất bại — hãy thử lại'))
        setGenerationJobs(previous => previous.map(previousJob => {
          if (previousJob.job_id === job.job_id) {
            return { ...previousJob, status: result.jobStatus || 'failed' }
          }
          if (unavailableToday && previousJob.status === 'queued') {
            return { ...previousJob, status: 'quota_exhausted' }
          }
          return previousJob
        }))
        await refreshGeneratedJobs()
        return
      }

      await refreshGeneratedJobs()
    } finally {
      startedGenerationIds.current.delete(job.job_id)
    }
  }, [refreshGeneratedJobs])

  useEffect(() => {
    const jobsToStart = nextQueuedGenerations(generationJobs).filter(
      job => !startedGenerationIds.current.has(job.job_id),
    )
    if (jobsToStart.length === 0) return

    const startingIds = new Set(jobsToStart.map(job => job.job_id))
    jobsToStart.forEach(job => startedGenerationIds.current.add(job.job_id))
    setGenerationJobs(previous => previous.map(job =>
      startingIds.has(job.job_id) && job.status === 'queued'
        ? { ...job, status: 'generating' }
        : job
    ))
    jobsToStart.forEach(job => { void runGenerationJob(job) })
  }, [generationJobs, runGenerationJob])

  const handleGenerate = useCallback(() => {
    if (!selectedFormatId) return
    setError('')

    const jobId = `guided:${globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`}`
    const formatId = selectedFormatId
    const request = {
      brief,
      formatId,
      customPrompt,
      assetIds: [...selectedAssetIds],
      promptSpec,
      quality: promptSpec?.quality || 'medium',
      campaignFlow: openaiCampaignFlow ? 'openai' : '',
      audienceContext: openaiCampaignFlow ? segment : {},
    }
    setGenerationJobs(previous => {
      if (!canEnqueueGeneration(previous)) return previous
      return [...previous, {
        job_id: jobId,
        status: 'queued',
        localOnly: true,
        created_at: new Date().toISOString(),
        metadata: { format_id: formatId },
        request,
        result: {},
      }]
    })
  }, [selectedFormatId, brief, customPrompt, selectedAssetIds, promptSpec, openaiCampaignFlow, segment])

  const handleFormatSelect = useCallback((formatId) => {
    setSelectedFormatId(formatId)
    setPromptSpec(null)
  }, [])

  const handleAssetFile = useCallback(async (event) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    if (!assetDraft.name.trim()) {
      setError('Hãy đặt tên cho asset trước khi tải ảnh lên.')
      return
    }
    setAssetUploading(true)
    setError('')
    try {
      const dataUrl = await new Promise((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(reader.result)
        reader.onerror = reject
        reader.readAsDataURL(file)
      })
      const asset = await AgentAPI.createCreativeAsset({ ...assetDraft, dataUrl })
      setAssets(prev => [asset, ...prev])
      setSelectedAssetIds(prev => new Set([...prev, asset.asset_id]))
      setAssetDraft({ name: '', kind: 'logo', useInstruction: '', required: true })
      setPromptSpec(null)
    } catch (uploadError) {
      setError(uploadError.message || 'Không thể lưu reference asset.')
    } finally {
      setAssetUploading(false)
    }
  }, [assetDraft])

  const handleComposePrompt = useCallback(async () => {
    if (!selectedFormatId || composingPrompt) return
    setComposingPrompt(true)
    setError('')
    try {
      const result = await AgentAPI.composeCreativePrompt({
        brief, formatId: selectedFormatId, assetIds: [...selectedAssetIds], direction: customPrompt,
      })
      setPromptSpec(result.prompt_spec)
      setPromptExpanded(true)
    } catch (composeError) {
      setError(composeError.message || 'Không thể soạn prompt creative.')
    } finally {
      setComposingPrompt(false)
    }
  }, [brief, selectedFormatId, selectedAssetIds, customPrompt, composingPrompt])

  // ── After crop modal resolves ─────────────────────────────────────────────
  const visibleJobs = generationJobs.filter(job => !hiddenJobIds.has(job.job_id))
  const generatedImages = visibleJobs
    .filter(job => job.status === 'succeeded' && job.result?.final_url)
    .map(galleryImage)
  const readyToCrop = visibleJobs.filter(job =>
    job.status === 'succeeded' && job.result?.raw_url && !job.result?.final_url
  )

  useEffect(() => {
    if (pendingCrop || finalizing) return
    const next = readyToCrop.find(job => !deferredCropIds.has(job.job_id))
    if (!next) return
    const formatId = next.metadata?.format_id || ''
    setPendingCrop({
      jobId: next.job_id,
      src: creativeImageSource(next.result.raw_url),
      formatId,
      width: next.result.width || AD_FORMATS_MAP[formatId]?.width,
      height: next.result.height || AD_FORMATS_MAP[formatId]?.height,
    })
  }, [readyToCrop, deferredCropIds, pendingCrop, finalizing])

  const finishImage = useCallback(async (croppedDataUrl) => {
    if (!pendingCrop || finalizing) return
    setFinalizing(true)
    setError('')
    try {
      const updated = await AgentAPI.finalizeGeneratedImage(pendingCrop.jobId, croppedDataUrl)
      setGenerationJobs(previous => previous.map(job =>
        job.job_id === updated.job_id ? updated : job
      ))
      setDeferredCropIds(previous => {
        const next = new Set(previous)
        next.delete(pendingCrop.jobId)
        return next
      })
      setPendingCrop(null)
    } catch (cropError) {
      setError(cropError.message || 'Không thể lưu ảnh đã crop.')
    } finally {
      setFinalizing(false)
    }
  }, [pendingCrop, finalizing])

  const handleCropConfirm = useCallback((croppedDataUrl) => {
    if (!pendingCrop) return
    return finishImage(croppedDataUrl)
  }, [pendingCrop, finishImage])

  const handleScale = useCallback((scaledDataUrl) => {
    if (!pendingCrop) return
    return finishImage(scaledDataUrl)
  }, [pendingCrop, finishImage])

  const handleCropCancel = useCallback(() => {
    if (pendingCrop?.jobId) {
      setDeferredCropIds(previous => new Set([...previous, pendingCrop.jobId]))
    }
    setPendingCrop(null)
  }, [pendingCrop])

  const toggleSelect = (id) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const removeGen = (id) => {
    setHiddenJobIds(previous => new Set([...previous, id]))
    setSelectedIds(prev => { const n = new Set(prev); n.delete(id); return n })
  }

  const handleAddToCreative = () => {
    const toAdd = generatedImages.filter(i => selectedIds.has(i.id))
    if (!toAdd.length) return
    onAddToCreative(toAdd)
    setSelectedIds(new Set())
  }

  // Brief preview — only visually-relevant fields (mirrors backend)
  const briefLines = [
    brief?.brand && `🏷 Brand: ${brief.brand}`,
    brief?.notes && `📝 Notes: ${brief.notes}`,
  ].filter(Boolean)

  const audienceLines = (segment?.attrs || []).map(a =>
    `• ${a.name || a.fullLabel || a.code}` +
    (a.type ? ` (${a.type})` : '') +
    (a.sizeRaw ? ` — ${a.sizeRaw}` : '')
  )

  const targeting = segment?.targeting || {}
  const targetingLines = Object.entries(targeting)
    .filter(([, v]) => v && (Array.isArray(v) ? v.length : true))
    .map(([k, v]) => `• ${k}: ${Array.isArray(v) ? v.join(', ') : v}`)

  const pendingFmt = pendingCrop ? (AD_FORMATS_MAP[pendingCrop.formatId] || {}) : null

  return (
    <div className="space-y-4">

      {/* Crop modal — rendered when API returns raw image */}
      {pendingCrop && (
        <ImageCropModal
          src={pendingCrop.src}
          targetW={pendingFmt?.width  ?? pendingCrop.width}
          targetH={pendingFmt?.height ?? pendingCrop.height}
          label={pendingFmt?.label ?? pendingCrop.formatId}
          onConfirm={handleCropConfirm}
          onScale={handleScale}
          onCancel={handleCropCancel}
        />
      )}

      {/* Brief preview (collapsed by default) */}
      <Card className="border-slate-200 bg-slate-50">
        <CardContent className="py-2.5 px-3">
          <button
            onClick={() => setBriefExpanded(e => !e)}
            className="w-full flex items-center justify-between text-xs font-semibold text-slate-600"
          >
            <span>📋 Brief ({brief?.brand || 'chưa có'}) — Brand + Notes</span>
            {briefExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
          {briefExpanded && (
            <div className="mt-2 space-y-1">
              {briefLines.length === 0 && (
                <p className="text-[11px] text-amber-700">⚠ Hoàn thành bước Brief trước để prompt chính xác hơn.</p>
              )}
              <p className="text-[10px] text-slate-400 italic">
                💡 Chỉ Brand & Notes được dùng trong prompt ảnh. KPI, budget, ngày tháng không ảnh hưởng visual.
              </p>
              {briefLines.map((l, i) => (
                <p key={i} className="text-[11px] text-slate-700 whitespace-pre-wrap">{l}</p>
              ))}

              {audienceLines.length > 0 && (
                <>
                  <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wide mt-2">👥 Audience Segments</p>
                  {audienceLines.map((l, i) => (
                    <p key={i} className="text-[11px] text-slate-700">{l}</p>
                  ))}
                </>
              )}

              {targetingLines.length > 0 && (
                <>
                  <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wide mt-2">🎯 Targeting Parameters</p>
                  {targetingLines.map((l, i) => (
                    <p key={i} className="text-[11px] text-slate-700">{l}</p>
                  ))}
                </>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Format picker */}
      <div>
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
          Chọn kích thước / định dạng ảnh
        </p>
        <div className="space-y-1.5 max-h-64 overflow-y-auto pr-0.5">
          {AD_FORMATS.map(fmt => (
            <FormatCard
              key={fmt.id}
              fmt={fmt}
              selected={selectedFormatId === fmt.id}
              onClick={handleFormatSelect}
            />
          ))}
        </div>
      </div>

      {/* Named brand/reference assets */}
      <div
        className="rounded-xl border border-sky-200 bg-sky-50/40 p-3 space-y-3"
        data-testid="creative-asset-pack"
        data-demo="creative-reference-assets"
      >
        <div>
          <p className="text-xs font-bold text-sky-800">Brand & reference assets</p>
          <p className="text-[10px] text-sky-700 mt-0.5">Đặt tên cho logo, sản phẩm hoặc ảnh tham khảo và mô tả chính xác cách dùng trong creative.</p>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <input value={assetDraft.name} onChange={event => setAssetDraft(current => ({ ...current, name: event.target.value }))}
            placeholder="Tên asset, ví dụ Logo Hutao" className="col-span-2 text-xs border rounded-lg px-2.5 py-2 bg-white" />
          <select value={assetDraft.kind} onChange={event => setAssetDraft(current => ({ ...current, kind: event.target.value }))}
            className="text-xs border rounded-lg px-2.5 py-2 bg-white">
            <option value="logo">Logo</option><option value="product">Product</option>
            <option value="packshot">Packshot</option><option value="character">Character</option>
            <option value="style_reference">Style reference</option><option value="background">Background</option>
            <option value="legal">Legal artwork</option>
          </select>
          <label className="flex items-center gap-2 text-[11px] text-sky-800 px-2">
            <input type="checkbox" checked={assetDraft.required}
              onChange={event => setAssetDraft(current => ({ ...current, required: event.target.checked }))} />
            Bắt buộc xuất hiện
          </label>
          <input value={assetDraft.useInstruction}
            onChange={event => setAssetDraft(current => ({ ...current, useInstruction: event.target.value }))}
            placeholder="Cách dùng: logo ở góc trái, giữ nguyên màu…" className="col-span-2 text-xs border rounded-lg px-2.5 py-2 bg-white" />
          <label className={cn('col-span-2 flex items-center justify-center gap-2 rounded-lg border border-dashed px-3 py-2 text-xs font-semibold cursor-pointer', assetUploading ? 'opacity-60' : 'bg-white hover:border-sky-400 text-sky-700')}>
            {assetUploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <PlusCircle className="w-3.5 h-3.5" />}
            {assetUploading ? 'Đang lưu asset…' : 'Chọn ảnh và thêm asset'}
            <input type="file" accept="image/png,image/jpeg,image/webp" className="hidden" disabled={assetUploading} onChange={handleAssetFile} />
          </label>
        </div>
        {assets.length > 0 && <div className="space-y-1.5">{assets.map(asset => {
          const selected = selectedAssetIds.has(asset.asset_id)
          return <div key={asset.asset_id} className="flex items-center gap-2 rounded-lg border bg-white p-2">
            <button className={cn('w-4 h-4 rounded border flex items-center justify-center', selected && 'bg-sky-600 border-sky-600')}
              onClick={() => setSelectedAssetIds(previous => { const next = new Set(previous); next.has(asset.asset_id) ? next.delete(asset.asset_id) : next.add(asset.asset_id); setPromptSpec(null); return next })}>
              {selected && <CheckCircle2 className="w-3 h-3 text-white" />}
            </button>
            <img src={asset.url} alt={asset.name} className="w-9 h-9 rounded object-cover border" />
            <div className="min-w-0 flex-1"><p className="text-[11px] font-semibold truncate">{asset.name} · {asset.kind}</p>
              <p className="text-[10px] text-muted-foreground truncate">{asset.use_instruction || 'Không có hướng dẫn riêng'}</p></div>
            {asset.required && <Badge className="text-[9px]">Required</Badge>}
          </div>
        })}</div>}
      </div>

      {/* Custom prompt */}
      <div className="rounded-xl border border-border overflow-hidden">
        <button
          onClick={() => setPromptExpanded(e => !e)}
          className="w-full flex items-center justify-between px-3 py-2.5 bg-muted/30 hover:bg-muted/50 transition-colors text-xs font-semibold text-muted-foreground"
          id="btn-toggle-custom-prompt"
        >
          <span className="flex items-center gap-1.5">
            <Pencil className="w-3.5 h-3.5" />
            Prompt tùy chỉnh
            {customPrompt.trim() && (
              <Badge className="text-[9px] h-4 px-1.5 bg-violet-100 text-violet-700 border-violet-200">Đã thêm</Badge>
            )}
          </span>
          {promptExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>
        {promptExpanded && (
          <div className="p-3 bg-white">
            <p className="text-[10px] text-muted-foreground mb-2">
              Thêm yêu cầu phong cách: màu sắc, bố cục, vibe, v.v. Ví dụ: <em>"retro style, warm orange palette, bold typography"</em>
            </p>
            <textarea
              id="custom-prompt-input"
              value={customPrompt}
              onChange={e => { setCustomPrompt(e.target.value); setPromptSpec(null) }}
              placeholder="Ví dụ: minimalist design, pastel blue tones, no text overlay..."
              rows={3}
              className="w-full text-xs border border-border rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-violet-300 focus:border-violet-400 placeholder:text-muted-foreground/60"
            />
            {customPrompt.trim() && (
              <button
                onClick={() => setCustomPrompt('')}
                className="text-[10px] text-red-500 hover:text-red-600 mt-1 flex items-center gap-0.5"
              >
                <X className="w-2.5 h-2.5" /> Xoá prompt
              </button>
            )}
          </div>
        )}
      </div>

      <Button variant="outline" className="w-full gap-2" onClick={handleComposePrompt}
        disabled={!selectedFormatId || composingPrompt} id="btn-compose-creative-prompt">
        {composingPrompt ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wand2 className="w-4 h-4" />}
        {promptSpec ? 'Tạo lại prompt spec' : 'AI soạn prompt theo format & assets'}
      </Button>
      {promptSpec && <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-[11px] text-emerald-900" data-testid="creative-prompt-spec">
        <p className="font-bold">Prompt spec đã sẵn sàng · {promptSpec.target_width}×{promptSpec.target_height}</p>
        <p className="mt-1"><strong>Direction:</strong> {promptSpec.creative_direction}</p>
        <p className="mt-1"><strong>Promise:</strong> {promptSpec.primary_promise}</p>
        <p className="mt-1"><strong>CTA:</strong> {promptSpec.cta}</p>
      </div>}

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 p-2.5 rounded-xl bg-red-50 border border-red-200 text-xs text-red-700">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* The server still enforces the per-actor daily generation limit. */}
      <Button
        onClick={handleGenerate}
        disabled={!selectedFormatId || pendingGenerationCount >= MAX_PENDING_GENERATIONS}
        className="w-full gap-2"
        id="btn-ai-generate"
      >
        {pendingGenerationCount >= MAX_PENDING_GENERATIONS ? (
          <>
            <Clock3 className="w-4 h-4" />
            Hàng đợi đã đầy ({MAX_PENDING_GENERATIONS}/{MAX_PENDING_GENERATIONS})
          </>
        ) : (
          <>
            <Sparkles className="w-4 h-4" />
            Tạo ảnh AI {selectedFormatId ? `— ${AD_FORMATS_MAP[selectedFormatId]?.label}` : ''}
          </>
        )}
      </Button>
      {pendingGenerationCount > 0 && (
        <p className="text-center text-[10px] text-muted-foreground" data-testid="generated-image-queue-summary">
          {activeGenerationCount}/{MAX_CONCURRENT_GENERATIONS} đang tạo
          {' · '}{queuedGenerationCount} đang chờ
          {' · '}{pendingGenerationCount}/{MAX_PENDING_GENERATIONS} yêu cầu
        </p>
      )}

      {(pendingGenerationCount > 0 || readyToCrop.length > 0) && (
        <div className="grid grid-cols-2 gap-2" data-testid="generated-image-job-list">
          {visibleJobs.filter(job => job.status === 'queued').map((job, index) => {
            const fmt = AD_FORMATS_MAP[job.metadata?.format_id] || {}
            return (
              <div key={job.job_id} className="h-36 rounded-xl border border-slate-200 bg-slate-50 flex flex-col items-center justify-center gap-2 p-3 text-center">
                <Clock3 className="w-6 h-6 text-slate-500" />
                <p className="text-[11px] font-semibold text-slate-700">Đang chờ · #{index + 1}</p>
                <p className="text-[10px] text-slate-500">{fmt.label || 'AI creative'}</p>
              </div>
            )
          })}
          {visibleJobs.filter(job => ['reserved', 'generating'].includes(job.status)).map(job => {
            const fmt = AD_FORMATS_MAP[job.metadata?.format_id] || {}
            return (
              <div key={job.job_id} className="h-36 rounded-xl border border-violet-200 bg-violet-50/60 flex flex-col items-center justify-center gap-2 p-3 text-center">
                <Loader2 className="w-6 h-6 text-violet-500 animate-spin" />
                <p className="text-[11px] font-semibold text-violet-800">Đang tạo creative</p>
                <p className="text-[10px] text-violet-600">{fmt.label || 'AI creative'}</p>
              </div>
            )
          })}
          {readyToCrop.map(job => {
            const formatId = job.metadata?.format_id || ''
            const fmt = AD_FORMATS_MAP[formatId] || {}
            return (
              <div key={job.job_id} className="rounded-xl border border-amber-200 bg-amber-50 overflow-hidden">
                <img
                  src={creativeImageSource(job.result.raw_url)}
                  crossOrigin={creativeImageCrossOrigin(job.result.raw_url)}
                  alt={fmt.label || 'Generated creative'}
                  className="w-full h-24 object-cover"
                />
                <div className="p-2">
                  <p className="text-[10px] font-semibold truncate">{fmt.label || formatId}</p>
                  <Button size="sm" variant="outline" className="w-full h-7 mt-1 text-[10px]"
                    onClick={() => {
                      setDeferredCropIds(previous => {
                        const next = new Set(previous)
                        next.delete(job.job_id)
                        return next
                      })
                      setPendingCrop({
                        jobId: job.job_id,
                        src: creativeImageSource(job.result.raw_url),
                        formatId,
                        width: job.result.width || fmt.width,
                        height: job.result.height || fmt.height,
                      })
                    }}>
                    Crop / scale
                  </Button>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Gallery */}
      {generatedImages.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              <ImageIcon className="w-3.5 h-3.5 inline mr-1" />
              Ảnh đã tạo ({generatedImages.length})
            </p>
            {selectedIds.size > 0 && (
              <p className="text-[10px] text-violet-600 font-medium">{selectedIds.size} đã chọn</p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-2">
            {generatedImages.map(img => (
              <GenImageCard
                key={img.id}
                img={img}
                selected={selectedIds.has(img.id)}
                onToggle={toggleSelect}
                onRemove={removeGen}
                onPreview={setLightboxImg}
              />
            ))}
          </div>
        </div>
      )}

      {/* Add to Creative button */}
      {selectedIds.size > 0 && (
        <Button
          onClick={handleAddToCreative}
          variant="outline"
          className="w-full gap-2 border-violet-300 text-violet-700 hover:bg-violet-50"
          id="btn-add-to-creative"
        >
          <PlusCircle className="w-4 h-4" />
          Thêm {selectedIds.size} ảnh vào Creative
        </Button>
      )}

      {generatedImages.length === 0 && !generating && pendingGenerationCount === 0 && readyToCrop.length === 0 && (
        <div className="flex flex-col items-center gap-2 py-6 text-center text-muted-foreground">
          <Sparkles className="w-8 h-8 text-violet-300" />
          <p className="text-xs">Chọn định dạng và bấm <strong>Tạo ảnh AI</strong> để bắt đầu.</p>
        </div>
      )}

      {/* Lightbox for generated images */}
      <GenLightbox img={lightboxImg} onClose={() => setLightboxImg(null)} />
    </div>
  )
}
