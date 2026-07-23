import * as React from 'react'
import { PublicLanding } from 'agent-frontend'

// Trang hoàn chỉnh — là scroll container riêng nên card hiển thị từ hero;
// cuộn bên trong card để xem các block sau.
export const FullPage = () => (
  <div style={{ height: '100%', minHeight: 780 }}>
    <PublicLanding onEnterAgent={() => {}} onOpenDemo={() => {}} />
  </div>
)
