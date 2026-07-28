import * as React from 'react'
import {
  Select, SelectTrigger, SelectValue, SelectContent,
  SelectGroup, SelectLabel, SelectItem, SelectSeparator,
} from 'agent-frontend'

// SelectSeparator chỉ có ý nghĩa bên trong SelectContent đang mở.
export const InsideOpenSelect = () => (
  <div style={{ width: 300, height: 320, padding: 16 }}>
    <Select open defaultValue="awareness">
      <SelectTrigger><SelectValue /></SelectTrigger>
      <SelectContent>
        <SelectGroup>
          <SelectLabel>Mục tiêu chính</SelectLabel>
          <SelectItem value="awareness">Awareness</SelectItem>
          <SelectItem value="traffic">Traffic</SelectItem>
        </SelectGroup>
        <SelectSeparator />
        <SelectGroup>
          <SelectLabel>Nâng cao</SelectLabel>
          <SelectItem value="conversion">Conversion</SelectItem>
        </SelectGroup>
      </SelectContent>
    </Select>
  </div>
)
