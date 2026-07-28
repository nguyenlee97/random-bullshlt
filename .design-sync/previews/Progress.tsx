import * as React from 'react'
import { Progress } from 'agent-frontend'

export const Values = () => (
  <div style={{ display: 'grid', gap: 18, padding: 20, width: 360 }}>
    <Progress value={18} />
    <Progress value={62} />
    <Progress value={100} />
  </div>
)
