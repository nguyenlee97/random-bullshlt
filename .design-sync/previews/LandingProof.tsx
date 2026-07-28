import * as React from 'react'
import { LandingProof } from 'agent-frontend'

const lightPlane: React.CSSProperties = {
  background: '#eef5ff',
  fontFamily: 'Inter, system-ui, sans-serif',
  padding: '16px 0 48px',
}

export const Default = () => (
  <div style={lightPlane}>
    <LandingProof />
  </div>
)
