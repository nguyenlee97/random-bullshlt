import * as React from 'react'
import { LandingHowItWorks } from 'agent-frontend'

const lightPlane: React.CSSProperties = {
  background: '#eef5ff',
  fontFamily: 'Inter, system-ui, sans-serif',
  padding: '32px 0 48px',
}

export const Default = () => (
  <div style={lightPlane}>
    <LandingHowItWorks />
  </div>
)
