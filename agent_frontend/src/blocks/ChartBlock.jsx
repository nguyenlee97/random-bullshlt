import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export default function ChartBlock({ block }) {
  const chartData = block.data.labels.map((label, index) => {
    const entry = { label }
    block.data.series.forEach((series) => { entry[series.name] = series.values[index] })
    return entry
  })

  return (
    <Card className="mt-2">
      <CardHeader className="pb-2 pt-3">
        <CardTitle className="text-xs text-muted-foreground">{block.title}</CardTitle>
      </CardHeader>
      <CardContent className="pt-0 pb-3">
        <ResponsiveContainer width="100%" height={180}>
          {block.chartType === 'line' ? (
            <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="label" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {block.data.series.map((series) => (
                <Line key={series.name} type="monotone" dataKey={series.name} stroke={series.color} strokeWidth={2} dot={{ r: 3 }} />
              ))}
            </LineChart>
          ) : (
            <BarChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="label" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {block.data.series.map((series) => (
                <Bar key={series.name} dataKey={series.name} fill={series.color} radius={[3, 3, 0, 0]} />
              ))}
            </BarChart>
          )}
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}
