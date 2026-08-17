import * as React from 'react'
import { AdImageGenerator } from 'agent-frontend'

// Preview tĩnh không có backend: stub fetch (component gọi API quota khi mount
// nhưng vẫn render đầy đủ danh sách format + khu vực asset khi API vắng mặt).
if (typeof window !== 'undefined' && !(window as any).__dsFetchStubbed) {
  ;(window as any).__dsFetchStubbed = true
  window.fetch = () => Promise.resolve(new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }))
}

export const FormatCatalog = () => (
  <div style={{ width: 1100 }}>
    <AdImageGenerator brief={{ brand: 'GreenNode EV', objective: 'Awareness' }} onAddToCreative={() => {}} />
  </div>
)
