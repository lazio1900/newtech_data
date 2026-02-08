import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts"
import type { KBPrice } from "@/types/data"
import { formatPriceCompact } from "@/lib/format"

interface PriceTrendChartProps {
  data: KBPrice[]
}

export default function PriceTrendChart({ data }: PriceTrendChartProps) {
  const chartData = [...data]
    .sort((a, b) => a.as_of_date.localeCompare(b.as_of_date))
    .map((d) => ({
      date: d.as_of_date,
      일반가: d.general_price,
      상위평균: d.high_avg_price,
      하위평균: d.low_avg_price,
    }))

  if (chartData.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
        시세 데이터가 없습니다
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
        <XAxis dataKey="date" tick={{ fontSize: 12 }} />
        <YAxis
          tickFormatter={(v: number) => formatPriceCompact(v)}
          tick={{ fontSize: 12 }}
          width={70}
        />
        <Tooltip
          formatter={(value: number | undefined) => formatPriceCompact(value ?? null)}
          labelFormatter={(label) => `기준일: ${String(label)}`}
        />
        <Legend />
        <Line
          type="monotone"
          dataKey="일반가"
          stroke="hsl(221, 83%, 53%)"
          strokeWidth={2}
          dot={{ r: 3 }}
        />
        <Line
          type="monotone"
          dataKey="상위평균"
          stroke="hsl(0, 84%, 60%)"
          strokeWidth={1.5}
          strokeDasharray="5 5"
          dot={false}
        />
        <Line
          type="monotone"
          dataKey="하위평균"
          stroke="hsl(142, 71%, 45%)"
          strokeWidth={1.5}
          strokeDasharray="5 5"
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
