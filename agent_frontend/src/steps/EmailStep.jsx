import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { fmt } from '@/lib/utils'
import { Mail, Send, Loader2, Check, Edit } from 'lucide-react'

export default function EmailStep({ brief, zones, selectedZoneIds, audiences, data, onChange, isDone }) {
  const [sending, setSending] = useState(false)
  const selected = (zones || []).filter(z => (selectedZoneIds || []).includes(z.id))

  const handleSend = async () => {
    setSending(true)
    await new Promise(r => setTimeout(r, 1200))
    onChange({ sent: true })
    setSending(false)
  }

  const brandSlug = (brief?.brand || 'brand').toLowerCase().replace(/\s/g, '')
  const time = new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
  const dateRange = brief?.startDate && brief?.endDate
    ? `${brief.startDate} → ${brief.endDate}`
    : `${brief?.duration || '?'} tuần`

  const emailBody = `Hi Account & Ad Opt teams,

Camp Ads Agent đã hoàn tất setup + phân tích chiến dịch ${brief?.brand}.

Tóm tắt:
• Objective: ${brief?.objective} · KPI: ${brief?.kpi}
• Ngân sách: ${brief?.budget}M · Thời gian: ${dateRange}
• Audience: ~${fmt(audiences?.size || 0)} người dùng (${(audiences?.attrs || []).length} segments)
• ${selected.length} ad zones đã xác nhận: ${selected.map(z => z.name).join(', ')}

Performance tham chiếu 500 camp:
• 312 good · 96 watch · 92 bad

Đề xuất ưu tiên:
1. Pause 92 camp 'bad'
2. Scale +20% budget cho 312 camp 'good'
3. Re-test creative cho 96 camp 'watch'
4. Shift budget sang zone reach cao nhất

— Camp Ads Agent`

  return (
    <div className="space-y-4">
      <Card className="border-blue-200">
        <CardHeader className="pb-2 pt-3 flex-row items-center gap-2">
          <Mail className="w-4 h-4 text-blue-500" />
          <CardTitle className="text-sm text-blue-700">Email Preview</CardTitle>
        </CardHeader>
        <CardContent className="pt-0 pb-3 space-y-2">
          {[
            ['To', 'account@adtima.vn, adopt@adtima.vn'],
            ['Cc', `${brandSlug}-pm@adtima.vn`],
            ['Subject', `[Camp Ads Agent] Báo cáo & đề xuất ${brief?.brand}`],
          ].map(([k, v]) => (
            <div key={k} className="flex gap-3 text-xs">
              <span className="font-semibold text-muted-foreground w-14 flex-shrink-0">{k}:</span>
              <span className="text-foreground">{v}</span>
            </div>
          ))}
          <div className="pt-2 border-t border-border">
            <pre className="text-xs text-muted-foreground whitespace-pre-wrap font-sans leading-relaxed max-h-48 overflow-y-auto">{emailBody}</pre>
          </div>
        </CardContent>
      </Card>

      {data.sent ? (
        <Card className="border-brand-200 bg-brand-50">
          <CardContent className="py-3 flex items-center gap-2">
            <Check className="w-4 h-4 text-brand-500" />
            <p className="text-sm font-semibold text-brand-700">Email đã gửi lúc {time} — 2 người nhận, 1 cc</p>
          </CardContent>
        </Card>
      ) : (
        <div className="flex gap-2">
          <Button onClick={handleSend} disabled={sending} className="gap-1.5" id="send-email-btn">
            {sending ? <><Loader2 className="w-4 h-4 animate-spin" />Đang gửi...</> : <><Send className="w-4 h-4" />Gửi email</>}
          </Button>
          <Button variant="outline" className="gap-1.5"><Edit className="w-4 h-4" />Chỉnh sửa</Button>
        </div>
      )}
    </div>
  )
}
