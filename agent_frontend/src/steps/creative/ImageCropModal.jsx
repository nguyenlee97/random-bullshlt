import { useRef, useState, useEffect, useCallback } from 'react'
import { X, Crop, Maximize2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

/**
 * ImageCropModal
 * Shows the raw AI-generated image and lets the user drag a locked-ratio crop box.
 *
 * Props:
 *   src        — raw base64 string (no data: prefix) from API
 *   targetW    — target output width  (e.g. 2032)
 *   targetH    — target output height (e.g.  528)
 *   label      — format label for display
 *   onConfirm  — (croppedDataUrl: string) => void
 *   onScale    — () => void  [stretch raw image to target dims, no crop]
 *   onCancel   — () => void
 */
export default function ImageCropModal({ src, targetW, targetH, label, onConfirm, onScale, onCancel }) {
  const containerRef = useRef(null)
  const imgRef       = useRef(null)
  const [imgNatural, setImgNatural] = useState({ w: 0, h: 0 })
  const [display,    setDisplay]    = useState({ w: 0, h: 0, offsetX: 0, offsetY: 0 })

  // Crop box in display-space pixels
  const [box, setBox] = useState(null)         // { x, y, w, h }
  const dragState = useRef(null)               // { mode, startX, startY, origBox }

  const TARGET_RATIO = targetW / targetH

  // ── Compute display size + initial crop box once image loads ─────────────────
  const handleImgLoad = useCallback(() => {
    const img = imgRef.current
    if (!img) return
    const natW = img.naturalWidth
    const natH = img.naturalHeight
    setImgNatural({ w: natW, h: natH })

    const container = containerRef.current
    const maxW = container ? container.clientWidth - 32 : 600
    const maxH = Math.min(window.innerHeight * 0.55, 500)

    // Fit the image inside the available area preserving natural ratio
    const scale = Math.min(maxW / natW, maxH / natH, 1)
    const dispW = Math.round(natW * scale)
    const dispH = Math.round(natH * scale)
    const offX  = Math.round((maxW - dispW) / 2)
    setDisplay({ w: dispW, h: dispH, offsetX: offX, offsetY: 0 })

    // Initial crop box: largest box of target ratio that fits inside the display image
    const srcRatio = natW / natH
    let boxW, boxH
    if (srcRatio > TARGET_RATIO) {
      // image is wider → box is height-limited
      boxH = dispH
      boxW = Math.round(boxH * TARGET_RATIO)
    } else {
      // image is taller → box is width-limited
      boxW = dispW
      boxH = Math.round(boxW / TARGET_RATIO)
    }
    const boxX = Math.round((dispW - boxW) / 2)
    const boxY = Math.round((dispH - boxH) / 2)
    setBox({ x: boxX, y: boxY, w: boxW, h: boxH })
  }, [TARGET_RATIO])

  // ── Mouse drag handling ───────────────────────────────────────────────────────
  const clampBox = useCallback((b, dispW, dispH) => {
    let { x, y, w, h } = b
    // Enforce min size
    w = Math.max(w, 40)
    h = Math.max(h, Math.round(40 / TARGET_RATIO))
    // Clamp to image bounds
    x = Math.max(0, Math.min(x, dispW - w))
    y = Math.max(0, Math.min(y, dispH - h))
    w = Math.min(w, dispW - x)
    h = Math.min(h, dispH - y)
    return { x, y, w, h }
  }, [TARGET_RATIO])

  const onMouseDown = useCallback((e, mode) => {
    e.preventDefault()
    dragState.current = {
      mode,
      startX: e.clientX,
      startY: e.clientY,
      origBox: { ...box },
    }
  }, [box])

  useEffect(() => {
    const onMove = (e) => {
      if (!dragState.current || !box) return
      const { mode, startX, startY, origBox } = dragState.current
      const dx = e.clientX - startX
      const dy = e.clientY - startY

      let next = { ...origBox }

      if (mode === 'move') {
        next.x = origBox.x + dx
        next.y = origBox.y + dy
      } else if (mode === 'se') {
        // resize from bottom-right, keep aspect ratio
        const newW = Math.max(40, origBox.w + dx)
        next.w = newW
        next.h = Math.round(newW / TARGET_RATIO)
      } else if (mode === 'sw') {
        const newW = Math.max(40, origBox.w - dx)
        next.w = newW
        next.h = Math.round(newW / TARGET_RATIO)
        next.x = origBox.x + origBox.w - newW
      } else if (mode === 'ne') {
        const newW = Math.max(40, origBox.w + dx)
        next.w = newW
        next.h = Math.round(newW / TARGET_RATIO)
        next.y = origBox.y + origBox.h - next.h
      } else if (mode === 'nw') {
        const newW = Math.max(40, origBox.w - dx)
        next.w = newW
        next.h = Math.round(newW / TARGET_RATIO)
        next.x = origBox.x + origBox.w - newW
        next.y = origBox.y + origBox.h - next.h
      }

      setBox(clampBox(next, display.w, display.h))
    }

    const onUp = () => { dragState.current = null }

    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup',   onUp)
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup',   onUp)
    }
  }, [box, display, clampBox, TARGET_RATIO])

  // ── Crop to canvas ────────────────────────────────────────────────────────────
  const handleConfirm = useCallback(() => {
    if (!box || !imgNatural.w) return
    // Convert display-space box to natural image coordinates
    const scaleX = imgNatural.w / display.w
    const scaleY = imgNatural.h / display.h
    const sx = Math.round(box.x * scaleX)
    const sy = Math.round(box.y * scaleY)
    const sw = Math.round(box.w * scaleX)
    const sh = Math.round(box.h * scaleY)

    const canvas = document.createElement('canvas')
    canvas.width  = targetW
    canvas.height = targetH
    const ctx = canvas.getContext('2d')
    const img = new window.Image()
    img.onload = () => {
      ctx.drawImage(img, sx, sy, sw, sh, 0, 0, targetW, targetH)
      onConfirm(canvas.toDataURL('image/png'))
    }
    img.src = `data:image/png;base64,${src}`
  }, [box, imgNatural, display, targetW, targetH, src, onConfirm])

  // ── Handle scale-stretch ──────────────────────────────────────────────────────
  const handleScale = useCallback(() => {
    const canvas = document.createElement('canvas')
    canvas.width  = targetW
    canvas.height = targetH
    const ctx = canvas.getContext('2d')
    const img = new window.Image()
    img.onload = () => {
      ctx.drawImage(img, 0, 0, img.naturalWidth, img.naturalHeight, 0, 0, targetW, targetH)
      onScale(canvas.toDataURL('image/png'))
    }
    img.src = `data:image/png;base64,${src}`
  }, [src, targetW, targetH, onScale])

  const dataUrl = `data:image/png;base64,${src}`

  // ── Handle window resize ──────────────────────────────────────────────────────
  useEffect(() => {
    const onResize = () => { if (imgRef.current?.complete) handleImgLoad() }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [handleImgLoad])

  return (
    <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-sm flex items-center justify-center p-3">
      <div
        ref={containerRef}
        className="relative bg-[#0f0f0f] rounded-2xl shadow-2xl w-full max-w-2xl flex flex-col max-h-[95vh] overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/10 flex-shrink-0">
          <div>
            <p className="text-white font-semibold text-sm flex items-center gap-2">
              <Crop className="w-4 h-4 text-violet-400" />
              Crop ảnh — <span className="text-violet-300">{label}</span>
            </p>
            <p className="text-white/50 text-xs mt-0.5">
              Tỉ lệ cố định {targetW}:{targetH} · Kéo góc để resize, kéo giữa để di chuyển
            </p>
          </div>
          <button
            onClick={onCancel}
            className="w-7 h-7 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center transition-colors"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Image area */}
        <div className="flex-1 overflow-auto p-4 flex items-center justify-center bg-[#0a0a0a]">
          <div className="relative" style={{ width: display.w || 'auto', height: display.h || 'auto' }}>
            {/* Raw image */}
            <img
              ref={imgRef}
              src={dataUrl}
              alt="Generated"
              onLoad={handleImgLoad}
              className="block select-none pointer-events-none"
              style={{ width: display.w, height: display.h }}
              draggable={false}
            />

            {/* Dark overlay outside crop box */}
            {box && (
              <svg
                className="absolute inset-0 pointer-events-none"
                width={display.w}
                height={display.h}
              >
                <defs>
                  <mask id="cropMask">
                    <rect width={display.w} height={display.h} fill="white" />
                    <rect x={box.x} y={box.y} width={box.w} height={box.h} fill="black" />
                  </mask>
                </defs>
                <rect
                  width={display.w}
                  height={display.h}
                  fill="rgba(0,0,0,0.55)"
                  mask="url(#cropMask)"
                />
              </svg>
            )}

            {/* Crop box */}
            {box && (
              <div
                className="absolute border-2 border-violet-400 cursor-move"
                style={{ left: box.x, top: box.y, width: box.w, height: box.h }}
                onMouseDown={e => onMouseDown(e, 'move')}
              >
                {/* Rule-of-thirds grid */}
                <div className="absolute inset-0 pointer-events-none opacity-30">
                  <div className="absolute border-white/40 border-l" style={{ left: '33.3%', top: 0, bottom: 0, borderLeftWidth: 1 }} />
                  <div className="absolute border-white/40 border-l" style={{ left: '66.6%', top: 0, bottom: 0, borderLeftWidth: 1 }} />
                  <div className="absolute border-white/40 border-t" style={{ top: '33.3%', left: 0, right: 0, borderTopWidth: 1 }} />
                  <div className="absolute border-white/40 border-t" style={{ top: '66.6%', left: 0, right: 0, borderTopWidth: 1 }} />
                </div>

                {/* Corner handles */}
                {[
                  { mode: 'nw', style: { top: -5,    left: -5,    cursor: 'nw-resize' } },
                  { mode: 'ne', style: { top: -5,    right: -5,   cursor: 'ne-resize' } },
                  { mode: 'sw', style: { bottom: -5, left: -5,    cursor: 'sw-resize' } },
                  { mode: 'se', style: { bottom: -5, right: -5,   cursor: 'se-resize' } },
                ].map(({ mode, style }) => (
                  <div
                    key={mode}
                    className="absolute w-3 h-3 bg-violet-400 rounded-sm border border-white/60 shadow"
                    style={style}
                    onMouseDown={e => { e.stopPropagation(); onMouseDown(e, mode) }}
                  />
                ))}

                {/* Dimension badge */}
                <div className="absolute -bottom-6 left-0 text-[10px] text-violet-300 whitespace-nowrap select-none pointer-events-none">
                  {targetW} × {targetH}px
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer actions */}
        <div className="flex items-center gap-2 px-4 py-3 border-t border-white/10 flex-shrink-0 bg-[#0f0f0f]">
          <Button
            onClick={handleConfirm}
            disabled={!box}
            className="flex-1 gap-1.5 bg-violet-600 hover:bg-violet-500 text-white"
            id="btn-crop-confirm"
          >
            <Crop className="w-3.5 h-3.5" />
            Crop & Dùng
          </Button>
          <Button
            onClick={handleScale}
            variant="outline"
            className="flex-1 gap-1.5 bg-transparent border-white/30 text-white hover:bg-white/10 hover:text-white hover:border-white/50"
            id="btn-crop-scale"
          >
            <Maximize2 className="w-3.5 h-3.5" />
            Giữ nguyên & Scale
          </Button>
        </div>
      </div>
    </div>
  )
}
