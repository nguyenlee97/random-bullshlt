import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { AGENT_SCENARIOS } from '@/api/agentApi'
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { BarChart2, Loader2, TrendingUp, TrendingDown, Minus } from 'lucide-react'

const weeklyData = [
  { week: 'Tuần 1', 'Reach (M)': 1.2, 'CPM (k)': 58, 'CTR (%)': 1.1 },
  { week: 'Tuần 2', 'Reach (M)': 1.8, 'CPM (k)': 53, 'CTR (%)': 1.35 },
  { week: 'Tuần 3', 'Reach (M)': 2.1, 'CPM (k)': 52, 'CTR (%)': 1.42 },
  { week: 'Tuần 4', 'Reach (M)': 2.4, 'CPM (k)': 49, 'CTR (%)': 1.58 },
]

export default function ReportStep({ data, onChange, isDone }) {
  const [loading, setLoading] = useState(false)

  const runAnalysis = async () => {
    setLoading(true)
    await new Promise(r => setTimeout(r, 2000))
    onChange({ analyzed: true })
    setLoading(false)
  }

  if (!data.analyzed) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-4">
        <div className="w-16 h-16 rounded-2xl bg-violet-50 border border-violet-200 flex items-center justify-center">
          <BarChart2 className="w-8 h-8 text-violet-500" />
        </div>
        <div className="text-center">
          <p className="font-semibold text-foreground">Phân tích 500 Campaigns</p>
          <p className="text-xs text-muted-foreground mt-1">Extract dữ liệu · vẽ chart · LLM đánh giá · đề xuất hành động</p>
        </div>
        <Button onClick={runAnalysis} disabled={loading} size="lg" className="gap-2" id="run-report-btn">
          {loading ? <><Loader2 className="w-4 h-4 animate-spin" />Đang phân tích...</> : <><BarChart2 className="w-4 h-4" />Phân tích báo cáo</>}
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <Card>
        <CardHeader className="pb-2 pt-3">
          <CardTitle className="text-xs text-muted-foreground">Reach & CPM theo tuần</CardTitle>
        </CardHeader>
        <CardContent className="pt-0 pb-3">
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={weeklyData} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f2" />
              <XAxis dataKey="week" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="Reach (M)" fill="#1F7A3D" radius={[3, 3, 0, 0]} />
              <Bar dataKey="CPM (k)" fill="#9A6700" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2 pt-3">
          <CardTitle className="text-xs text-muted-foreground">CTR trend (%)</CardTitle>
        </CardHeader>
        <CardContent className="pt-0 pb-3">
          <ResponsiveContainer width="100%" height={120}>
            <LineChart data={weeklyData} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f2" />
              <XAxis dataKey="week" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
              <Line type="monotone" dataKey="CTR (%)" stroke="#185FA5" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <div className="grid grid-cols-3 gap-2">
        {[
          { label: 'Good', count: 312, color: 'text-brand-600', bg: 'bg-brand-50 border-brand-200', Icon: TrendingUp },
          { label: 'Watch', count: 96, color: 'text-amber-600', bg: 'bg-amber-50 border-amber-200', Icon: Minus },
          { label: 'Bad', count: 92, color: 'text-red-600', bg: 'bg-red-50 border-red-200', Icon: TrendingDown },
        ].map(({ label, count, color, bg, Icon }) => (
          <Card key={label} className={`border ${bg}`}>
            <CardContent className="py-3 text-center">
              <Icon className={`w-4 h-4 mx-auto mb-1 ${color}`} />
              <p className={`text-xl font-black ${color}`}>{count}</p>
              <p className={`text-[10px] font-semibold ${color}`}>{label}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
