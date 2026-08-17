import * as React from 'react'
import { LandingPain } from 'agent-frontend'

// Vùng sáng của trang — không dùng .public-landing-v2 để tránh gradient tối
// (và để block tự bật scroll-reveal khi render độc lập).
const lightPlane: React.CSSProperties = {
  background: '#eef5ff',
  fontFamily: 'Inter, system-ui, sans-serif',
  padding: '0 0 48px',
}

export const Default = () => (
  <div style={lightPlane}>
    <LandingPain />
  </div>
)
