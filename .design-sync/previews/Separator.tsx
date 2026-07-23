import * as React from 'react'
import { Separator } from 'agent-frontend'

export const HorizontalInContent = () => (
  <div style={{ width: 340, padding: 20, fontFamily: 'Inter, system-ui, sans-serif' }}>
    <div style={{ fontWeight: 600, fontSize: 14 }}>Campaign hè 2026</div>
    <div style={{ color: '#64748b', fontSize: 13 }}>Objective: Awareness · Budget 500tr</div>
    <Separator style={{ margin: '12px 0' }} />
    <div style={{ color: '#64748b', fontSize: 13 }}>Cập nhật lần cuối: hôm nay</div>
  </div>
)

export const Vertical = () => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 12, height: 28, padding: 20, fontFamily: 'Inter, system-ui, sans-serif', fontSize: 13 }}>
    <span>Brief</span>
    <Separator orientation="vertical" />
    <span>Audience</span>
    <Separator orientation="vertical" />
    <span>Creative</span>
  </div>
)
