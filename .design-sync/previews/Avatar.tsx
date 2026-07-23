import * as React from 'react'
import { Avatar, AvatarImage, AvatarFallback } from 'agent-frontend'

export const FallbackInitials = () => (
  <div style={{ display: 'flex', gap: 16, alignItems: 'center', padding: 16 }}>
    <Avatar><AvatarFallback>QD</AvatarFallback></Avatar>
    <Avatar><AvatarFallback>PG</AvatarFallback></Avatar>
    <Avatar><AvatarFallback>AA</AvatarFallback></Avatar>
  </div>
)

const sampleFace =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 40 40'%3E%3Crect width='40' height='40' fill='%230068ff'/%3E%3Ccircle cx='20' cy='15' r='7' fill='%23fff'/%3E%3Cellipse cx='20' cy='32' rx='12' ry='8' fill='%23fff'/%3E%3C/svg%3E"

export const WithImage = () => (
  <div style={{ display: 'flex', gap: 16, alignItems: 'center', padding: 16 }}>
    <Avatar>
      <AvatarImage src={sampleFace} alt="Người dùng mẫu" />
      <AvatarFallback>AA</AvatarFallback>
    </Avatar>
  </div>
)
