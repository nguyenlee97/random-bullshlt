import * as React from 'react'
import { SplitDivider } from 'agent-frontend'

// Thanh kéo chia đôi layout mobile (chat trên / workspace dưới).
export const Default = () => (
  <div style={{ width: 390, padding: '24px 0', background: '#f1f5f9' }}>
    <SplitDivider onDrag={() => {}} splitRatio={0.5} onWorkspaceExpand={() => {}} onChatExpand={() => {}} />
  </div>
)

export const WithActivityDots = () => (
  <div style={{ width: 390, padding: '24px 0', background: '#f1f5f9' }}>
    <SplitDivider onDrag={() => {}} splitRatio={0.5} onWorkspaceExpand={() => {}} onChatExpand={() => {}} chatHasNew workspaceHasNew />
  </div>
)
