import { useRef, useState } from 'react'
import { Label } from '@/components/ui/label'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { Upload, FileText, X, ZoomIn, CheckCircle2, AlertCircle, Sparkles, Wand2 } from 'lucide-react'
import AdImageGenerator from './creative/AdImageGenerator'

function fmtSize(bytes) {
  if (bytes >= 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + ' MB'
  return (bytes / 1024).toFixed(0) + ' KB'
}

// ─── Read image/video resolution on frontend ──────────────────────────────────
function readResolution(file, dataUrl) {
  return new Promise((resolve) => {
    if (file.type.startsWith('image/')) {
      const img = new window.Image()
      img.onload = () => resolve({ width: img.naturalWidth, height: img.naturalHeight })
      img.onerror = () => resolve({})
      img.src = dataUrl
    } else if (file.type.startsWith('video/')) {
      const video = document.createElement('video')
      video.onloadedmetadata = () => resolve({ width: video.videoWidth, height: video.videoHeight })
      video.onerror = () => resolve({})
      video.src = dataUrl
    } else {
      resolve({})
    }
  })
}

// ─── File card (shared between upload + AI gallery) ───────────────────────────
function FileCard({ file, onRemove, onPreview }) {
  const isImage = file.type?.startsWith('image/')
  const isVideo = file.type?.startsWith('video/')
  const canPreview = isImage || isVideo
  const res = file.width && file.height ? `${file.width}×${file.height}px` : null

  return (
    <div className="group relative rounded-xl border border-border bg-white overflow-hidden hover:border-brand-300 hover:shadow-sm transition-all">
      <div className="h-28 bg-muted/40 flex items-center justify-center overflow-hidden relative">
        {isImage ? (
          <img src={file.dataUrl} alt={file.name} className="w-full h-full object-cover" />
        ) : isVideo ? (
          <video src={file.dataUrl} className="w-full h-full object-cover" muted />
        ) : (
          <FileText className="w-10 h-10 text-muted-foreground" />
        )}
        {canPreview && (
          <div onClick={() => onPreview(file)}
            className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center cursor-pointer">
            <div className="w-9 h-9 rounded-full bg-white/90 flex items-center justify-center">
              <ZoomIn className="w-4 h-4" />
            </div>
          </div>
        )}
        <button onClick={() => onRemove(file.id)}
          className="absolute top-1.5 right-1.5 w-6 h-6 rounded-full bg-black/60 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-500">
          <X className="w-3 h-3" />
        </button>
        {/* AI badge */}
        {file.aiGenerated && (
          <div className="absolute top-1.5 left-1.5">
            <Badge className="text-[8px] h-4 px-1 bg-violet-500 text-white gap-0.5">
              <Sparkles className="w-2 h-2" />AI
            </Badge>
          </div>
        )}
      </div>
      <div className="px-2.5 py-2">
        <p className="text-xs font-semibold text-foreground truncate" title={file.name}>{file.name}</p>
        <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
          <Badge variant="muted" className="text-[10px] h-4 px-1.5">
            {file.type?.split('/')[1]?.toUpperCase() || 'FILE'}
          </Badge>
          {res ? (
            <span className="text-[10px] text-brand-600 font-semibold">{res}</span>
          ) : (
            <span className="text-[10px] text-muted-foreground">{fmtSize(file.size)}</span>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Lightbox ─────────────────────────────────────────────────────────────────
function Lightbox({ file, onClose }) {
  if (!file) return null
  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
      <div className="relative max-w-5xl max-h-full" onClick={e => e.stopPropagation()}>
        <button onClick={onClose} className="absolute -top-3 -right-3 z-10 w-8 h-8 rounded-full bg-white shadow-lg flex items-center justify-center hover:bg-gray-100">
          <X className="w-4 h-4" />
        </button>
        {file.type?.startsWith('image/') ? (
          <img src={file.dataUrl} alt={file.name} className="max-w-full max-h-[85vh] object-contain rounded-lg shadow-2xl" />
        ) : (
          <video src={file.dataUrl} controls autoPlay className="max-w-full max-h-[85vh] rounded-lg shadow-2xl" />
        )}
        <p className="text-white/80 text-sm text-center mt-3 font-medium">{file.name}</p>
      </div>
    </div>
  )
}

// ─── Tab bar ──────────────────────────────────────────────────────────────────
function TabBar({ tab, setTab }) {
  return (
    <div className="flex gap-1 p-1 rounded-xl bg-muted/50 border border-border mb-4">
      {[
        { id: 'upload', label: '📎 Upload' },
        { id: 'ai',     label: 'AI Tạo Ảnh', icon: true, badge: true },
      ].map(t => (
        <button
          key={t.id}
          onClick={() => setTab(t.id)}
          className={cn(
            'flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-semibold transition-all duration-150',
            tab === t.id
              ? 'bg-white shadow-sm text-foreground'
              : 'text-muted-foreground hover:text-foreground',
          )}
          id={`creative-tab-${t.id}`}
        >
          {t.icon ? (
            <span className="flex items-center gap-1"><Wand2 className="w-3.5 h-3.5" />{t.label}</span>
          ) : t.label}
          {t.badge && (
            <Badge className="text-[8px] h-4 px-1 bg-violet-100 text-violet-700 border-violet-200">Beta</Badge>
          )}
        </button>
      ))}
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function CreativeStep({ data, onChange, isDone, brief, segment }) {
  const fileInputRef = useRef(null)
  const [lightboxFile, setLightboxFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [tab, setTab] = useState('upload')
  const files = data.files || []

  const processFiles = async (rawFiles) => {
    const toRead = Array.from(rawFiles).filter(f => f.type.startsWith('image/') || f.type.startsWith('video/'))
    for (const file of toRead) {
      await new Promise((resolve) => {
        const reader = new FileReader()
        reader.onload = async () => {
          const { width, height } = await readResolution(file, reader.result)
          const newFile = {
            id: `${file.name}-${file.size}-${Date.now()}`,
            name: file.name,
            type: file.type,
            size: file.size,
            dataUrl: reader.result,
            width: width || null,
            height: height || null,
          }
          onChange(prev => {
            const prevFiles = prev.files || []
            if (prevFiles.some(f => f.id === newFile.id)) return prev
            return { ...prev, files: [...prevFiles, newFile], uploaded: true }
          })
          resolve()
        }
        reader.readAsDataURL(file)
      })
    }
  }

  const handleFileChange = (e) => { processFiles(e.target.files); e.target.value = '' }
  const handleDrop = (e) => { e.preventDefault(); setDragging(false); processFiles(e.dataTransfer.files) }
  const removeFile = (id) => onChange(prev => {
    const updated = (prev.files || []).filter(f => f.id !== id)
    return { ...prev, files: updated, uploaded: updated.length > 0 }
  })

  // Merge AI-generated images into the files pool, then flip to upload tab
  const handleAddAiImages = (aiImages) => {
    onChange(prev => {
      const existing = prev.files || []
      const toAdd = aiImages.filter(img => !existing.some(f => f.id === img.id))
      return { ...prev, files: [...existing, ...toAdd], uploaded: true }
    })
    setTab('upload')
  }

  if (isDone) {
    return (
      <Card className="border-brand-200 bg-brand-50">
        <CardContent className="py-4 flex items-center gap-3">
          <CheckCircle2 className="w-5 h-5 text-brand-500 flex-shrink-0" />
          <div>
            <p className="text-sm font-semibold text-brand-700">Creative đã được duyệt</p>
            <p className="text-xs text-brand-600 mt-0.5">
              {files.length} file(s) đã upload
              {files.some(f => f.aiGenerated) && ' (bao gồm ảnh AI)'}
            </p>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      <TabBar tab={tab} setTab={setTab} />

      {/* ── Upload tab ── */}
      {tab === 'upload' && (
        <div className="space-y-4">
          <div>
            <Label className="mb-2 block">Upload Creative</Label>
            <div
              onDragOver={e => { e.preventDefault(); setDragging(true) }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={cn(
                'border-2 border-dashed rounded-xl p-6 cursor-pointer transition-all text-center',
                dragging ? 'border-brand-500 bg-brand-50 scale-[1.01]' : 'border-border hover:border-brand-400 hover:bg-brand-50/40'
              )}
              id="creative-drop-zone"
            >
              <div className="flex flex-col items-center gap-2 text-muted-foreground">
                <div className={cn('w-12 h-12 rounded-xl flex items-center justify-center transition-all', dragging ? 'bg-brand-100' : 'bg-muted/60')}>
                  <Upload className={cn('w-6 h-6', dragging ? 'text-brand-500' : 'text-muted-foreground')} />
                </div>
                <div>
                  <p className="text-sm font-semibold text-foreground">{dragging ? 'Thả file vào đây' : 'Kéo thả hoặc bấm để chọn'}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">PNG · JPG · MP4 — Nhiều file cùng lúc · Resolution tự động đọc</p>
                </div>
                {files.length > 0 && <Badge variant="green" className="mt-1">{files.length} file đã chọn · Thêm nữa</Badge>}
              </div>
            </div>
            <input ref={fileInputRef} id="creative-file-input" type="file" accept="image/*,video/*" multiple className="hidden" onChange={handleFileChange} />
          </div>

          {files.length > 0 && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <Label>{files.length} file đã upload</Label>
                <button onClick={() => onChange(prev => ({ ...prev, files: [], uploaded: false }))}
                  className="text-xs text-red-500 hover:text-red-600 font-medium flex items-center gap-1">
                  <X className="w-3 h-3" /> Xoá tất cả
                </button>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {files.map(file => (
                  <FileCard key={file.id} file={file} onRemove={removeFile} onPreview={setLightboxFile} />
                ))}
              </div>
            </div>
          )}

          {files.length === 0 && (
            <Card className="border-amber-100 bg-amber-50">
              <CardContent className="py-3 flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
                <p className="text-xs text-amber-700">
                  Upload ít nhất 1 creative để tiếp tục, hoặc dùng tab{' '}
                  <button onClick={() => setTab('ai')} className="font-semibold underline inline-flex items-center gap-0.5">
                    <Wand2 className="w-3 h-3" />AI Tạo Ảnh
                  </button>{' '}
                  để tạo ảnh tự động từ brief.
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* ── AI Tạo Ảnh tab ── */}
      {tab === 'ai' && (
        <AdImageGenerator brief={brief} segment={segment} onAddToCreative={handleAddAiImages} />
      )}

      <Lightbox file={lightboxFile} onClose={() => setLightboxFile(null)} />
    </div>
  )
}
