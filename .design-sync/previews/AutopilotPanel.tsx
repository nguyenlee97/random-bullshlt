import * as React from 'react'
import { AutopilotPanel } from 'agent-frontend'

// Preview tĩnh không có backend: stub fetch để tránh pageerror "Failed to fetch"
// (component render đầy đủ guide/empty state kể cả khi API vắng mặt).
if (typeof window !== 'undefined' && !(window as any).__dsFetchStubbed) {
  ;(window as any).__dsFetchStubbed = true
  window.fetch = () => Promise.resolve(new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }))
}

export const EmptyGuideState = () => (
  <div style={{ width: 1140, height: 860, overflow: 'hidden' }}>
    <AutopilotPanel />
  </div>
)
