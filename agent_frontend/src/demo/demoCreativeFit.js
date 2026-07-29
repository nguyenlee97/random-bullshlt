export function calculateCoverCrop(
  sourceWidth,
  sourceHeight,
  targetWidth,
  targetHeight,
  anchor = 'center',
) {
  const sourceRatio = sourceWidth / sourceHeight
  const targetRatio = targetWidth / targetHeight
  let sx = 0
  let sy = 0
  let sw = sourceWidth
  let sh = sourceHeight

  if (sourceRatio > targetRatio) {
    sw = sourceHeight * targetRatio
    sx = anchor === 'left'
      ? 0
      : anchor === 'right'
        ? sourceWidth - sw
        : (sourceWidth - sw) / 2
  } else if (sourceRatio < targetRatio) {
    sh = sourceWidth / targetRatio
    sy = anchor === 'top'
      ? 0
      : anchor === 'bottom'
        ? sourceHeight - sh
        : (sourceHeight - sh) / 2
  }

  return { sx, sy, sw, sh }
}

const canvasBlob = canvas => new Promise((resolve, reject) => {
  canvas.toBlob(
    blob => blob ? resolve(blob) : reject(new Error('Không thể xuất creative đã scale')),
    'image/png',
  )
})

const dataUrlForBlob = blob => new Promise((resolve, reject) => {
  const reader = new FileReader()
  reader.onload = () => resolve(reader.result)
  reader.onerror = () => reject(new Error('Không thể đọc creative đã scale'))
  reader.readAsDataURL(blob)
})

/**
 * Produce actual exact-size PNG bytes for the walkthrough. Metadata alone is
 * not enough because Creative Intelligence deliberately trusts measured pixels.
 */
export async function fitDemoCreative(blob, {
  width,
  height,
  cropAnchor = 'center',
}) {
  const image = await createImageBitmap(blob)
  try {
    const canvas = document.createElement('canvas')
    canvas.width = Number(width)
    canvas.height = Number(height)
    const context = canvas.getContext('2d')
    if (!context) throw new Error('Không thể khởi tạo canvas creative')
    const crop = calculateCoverCrop(
      image.width,
      image.height,
      canvas.width,
      canvas.height,
      cropAnchor,
    )
    context.drawImage(
      image,
      crop.sx,
      crop.sy,
      crop.sw,
      crop.sh,
      0,
      0,
      canvas.width,
      canvas.height,
    )
    const fittedBlob = await canvasBlob(canvas)
    return {
      blob: fittedBlob,
      dataUrl: await dataUrlForBlob(fittedBlob),
    }
  } finally {
    image.close()
  }
}

