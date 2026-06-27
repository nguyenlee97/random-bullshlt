import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import {
  Sparkles, Loader2, CheckCircle2, AlertCircle, ChevronDown, ChevronUp,
  X, PlusCircle, ImageIcon, ZoomIn, Wand2, Pencil,
} from 'lucide-react'
import { AgentAPI } from '@/api/agentApi'
import { AD_FORMATS, AD_FORMATS_MAP } from '@/data/adFormats'
import ImageCropModal from './ImageCropModal'

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
export default function AdImageGenerator({ brief, segment, onAddToCreative }) {
  const [selectedFormatId, setSelectedFormatId] = useState(null)
  const [generating, setGenerating]             = useState(false)
  const [error, setError]                       = useState('')
  const [generatedImages, setGeneratedImages]   = useState([])
  const [selectedIds, setSelectedIds]           = useState(new Set())
  const [remaining, setRemaining]               = useState(10)
  const [briefExpanded, setBriefExpanded]       = useState(false)
  const [lightboxImg, setLightboxImg]           = useState(null)
  const [customPrompt, setCustomPrompt]         = useState('')
  const [promptExpanded, setPromptExpanded]     = useState(false)

  // Pending crop: raw response waiting for user crop action
  // { b64, formatId, width, height }
  const [pendingCrop, setPendingCrop] = useState(null)

  // Fetch initial quota
  useEffect(() => {
    AgentAPI.getImageGenStatus().then(s => setRemaining(s.remaining ?? 10))
  }, [])

  const handleGenerate = useCallback(async () => {
    if (!selectedFormatId || generating || remaining <= 0) return
    setGenerating(true)
    setError('')

    const result = await AgentAPI.generateAdImage(brief, selectedFormatId, customPrompt)

    if (!result.ok) {
      setError(result.error || 'Tạo ảnh thất bại — hãy thử lại')
      setGenerating(false)
      return
    }

    // Update quota from server response
    setRemaining(result.remaining ?? Math.max(0, remaining - 1))

    // Open crop modal instead of auto-cropping
    setPendingCrop({
      b64:      result.imageB64,
      formatId: selectedFormatId,
      width:    result.width,
      height:   result.height,
    })
    setGenerating(false)
  }, [selectedFormatId, generating, remaining, brief, customPrompt])

  // ── After crop modal resolves ─────────────────────────────────────────────
  const finishImage = useCallback((croppedDataUrl, fmtId, w, h) => {
    const timestamp = Date.now()
    const newImg = {
      id: `ai-${fmtId}-${timestamp}`,
      name: `ai-${fmtId}-${timestamp}.png`,
      type: 'image/png',
      size: Math.round(croppedDataUrl.length * 0.75),
      dataUrl: croppedDataUrl,
      width: w,
      height: h,
      formatId: fmtId,
      aiGenerated: true,
    }
    setGeneratedImages(prev => [newImg, ...prev])
    setPendingCrop(null)
  }, [])

  const handleCropConfirm = useCallback((croppedDataUrl) => {
    if (!pendingCrop) return
    const fmt = AD_FORMATS_MAP[pendingCrop.formatId]
    finishImage(croppedDataUrl, pendingCrop.formatId, fmt?.width ?? pendingCrop.width, fmt?.height ?? pendingCrop.height)
  }, [pendingCrop, finishImage])

  const handleScale = useCallback((scaledDataUrl) => {
    if (!pendingCrop) return
    const fmt = AD_FORMATS_MAP[pendingCrop.formatId]
    finishImage(scaledDataUrl, pendingCrop.formatId, fmt?.width ?? pendingCrop.width, fmt?.height ?? pendingCrop.height)
  }, [pendingCrop, finishImage])

  const handleCropCancel = useCallback(() => {
    setPendingCrop(null)
  }, [])

  const toggleSelect = (id) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const removeGen = (id) => {
    setGeneratedImages(prev => prev.filter(i => i.id !== id))
    setSelectedIds(prev => { const n = new Set(prev); n.delete(id); return n })
  }

  const handleAddToCreative = () => {
    const toAdd = generatedImages.filter(i => selectedIds.has(i.id))
    if (!toAdd.length) return
    onAddToCreative(toAdd)
    setSelectedIds(new Set())
  }

  // Quota display helpers
  const quotaColor = remaining === 0 ? 'text-red-600 bg-red-50 border-red-200'
                   : remaining <= 3  ? 'text-amber-700 bg-amber-50 border-amber-200'
                   : 'text-violet-700 bg-violet-50 border-violet-200'

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
          src={pendingCrop.b64}
          targetW={pendingFmt?.width  ?? pendingCrop.width}
          targetH={pendingFmt?.height ?? pendingCrop.height}
          label={pendingFmt?.label ?? pendingCrop.formatId}
          onConfirm={handleCropConfirm}
          onScale={handleScale}
          onCancel={handleCropCancel}
        />
      )}

      {/* Quota counter */}
      <div className={cn('flex items-center justify-between px-3 py-2 rounded-xl border text-xs font-semibold', quotaColor)}>
        <div className="flex items-center gap-1.5">
          <Wand2 className="w-3.5 h-3.5" />
          <span>AI Tạo Ảnh — Beta</span>
        </div>
        <span>{remaining}/10 lượt còn lại</span>
      </div>

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
              onClick={setSelectedFormatId}
            />
          ))}
        </div>
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
              onChange={e => setCustomPrompt(e.target.value)}
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

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 p-2.5 rounded-xl bg-red-50 border border-red-200 text-xs text-red-700">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Generate button */}
      <Button
        onClick={handleGenerate}
        disabled={!selectedFormatId || generating || remaining <= 0}
        className="w-full gap-2"
        id="btn-ai-generate"
      >
        {generating ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            Đang tạo ảnh... (có thể mất 30-60 giây)
          </>
        ) : remaining <= 0 ? (
          <>
            <AlertCircle className="w-4 h-4" />
            Hết lượt tạo ảnh (10/10)
          </>
        ) : (
          <>
            <Sparkles className="w-4 h-4" />
            Tạo ảnh AI {selectedFormatId ? `— ${AD_FORMATS_MAP[selectedFormatId]?.label}` : ''}
          </>
        )}
      </Button>

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

      {generatedImages.length === 0 && !generating && (
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
