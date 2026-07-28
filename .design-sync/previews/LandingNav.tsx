import * as React from 'react'
import { LandingNav } from 'agent-frontend'

const darkPlane: React.CSSProperties = {
  background: '#020817',
  color: '#fff',
  fontFamily: 'Inter, system-ui, sans-serif',
  padding: '8px 0 24px',
}

export const Default = () => (
  <div style={darkPlane}>
    <LandingNav onEnterAgent={() => {}} />
  </div>
)

export const WithEcosystemLinks = () => (
  <div style={darkPlane}>
    <LandingNav
      onEnterAgent={() => {}}
      links={[
        { label: 'Ad Server', href: '#' },
        { label: 'DMP', href: '#' },
        { label: 'Analytics', href: '#' },
      ]}
    />
  </div>
)
