import { useEffect, useRef } from 'react'
import { ScrollArea } from '@/components/ui/scroll-area'
import MessageBubble from './MessageBubble'
import { MessageSquare } from 'lucide-react'

function EmptyState() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-3 p-8 text-center">
      <div className="w-14 h-14 rounded-2xl bg-brand-50 border border-brand-100 flex items-center justify-center">
        <MessageSquare className="w-7 h-7 text-brand-500" />
      </div>
      <div>
        <p className="font-semibold text-sm text-foreground">Chờ agent khởi động...</p>
        <p className="text-xs text-muted-foreground mt-0.5">Agent sẽ chào và dẫn dắt bạn qua từng bước</p>
      </div>
    </div>
  )
}

export default function ChatThread({ messages }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (messages.length === 0) return <EmptyState />

  return (
    <ScrollArea className="flex-1">
      <div className="flex flex-col gap-4 p-4">
        {messages.map(msg => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  )
}
