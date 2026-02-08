import { useMemo } from "react"
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  BarChart,
  Bar,
} from "recharts"
import type { KBPrice } from "@/types/data"
import { formatPrice, formatPriceCompact } from "@/lib/format"

interface PriceTrendChartProps {
  data: KBPrice[]
}

export default function PriceTrendChart({ data }: PriceTrendChartProps) {
  // 날짜별로 그룹핑하여 중복 제거 (면적 여러 개 → 같은 날짜에 여러 레코드)
  const chartData = useMemo(() => {
    const byDate: Record<
      string,
      { general: number[]; high: number[]; low: number[] }
    > = {}
    for (const d of data) {
      if (!byDate[d.as_of_date]) {
        byDate[d.as_of_date] = { general: [], high: [], low: [] }
      }
      if (d.general_price != null) byDate[d.as_of_date].general.push(d.general_price)
      if (d.high_avg_price != null) byDate[d.as_of_date].high.push(d.high_avg_price)
      if (d.low_avg_price != null) byDate[d.as_of_date].low.push(d.low_avg_price)
    }

    const avg = (arr: number[]) =>
      arr.length > 0 ? Math.round(arr.reduce((a, b) => a + b, 0) / arr.length) : null

    return Object.entries(byDate)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, vals]) => ({
        date,
        일반가: avg(vals.general),
        상위평균: avg(vals.high),
        하위평균: avg(vals.low),
      }))
  }, [data])

  if (data.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
        시세 데이터가 없습니다
      </div>
    )
  }

  // 날짜가 1-2개뿐이면 통계 카드 + 바 차트 표시
  if (chartData.length <= 2) {
    const latest = chartData[chartData.length - 1]
    return (
      <div className="space-y-4">
        {/* 통계 카드 */}
        <div className="grid grid-cols-3 gap-3">
          <StatCard
            label="일반가"
            value={latest.일반가}
            color="text-blue-600"
          />
          <StatCard
            label="상위평균"
            value={latest.상위평균}
            color="text-red-500"
          />
          <StatCard
            label="하위평균"
            value={latest.하위평균}
            color="text-green-600"
          />
        </div>
        <p className="text-center text-xs text-muted-foreground">
          기준일: {latest.date} · 수집 데이터가 쌓이면 추이 그래프가 표시됩니다
        </p>

        {/* 바 차트 */}
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
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
            <Bar dataKey="일반가" fill="hsl(221, 83%, 53%)" radius={[4, 4, 0, 0]} />
            <Bar dataKey="상위평균" fill="hsl(0, 84%, 60%)" radius={[4, 4, 0, 0]} />
            <Bar dataKey="하위평균" fill="hsl(142, 71%, 45%)" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    )
  }

  // 3개 이상의 날짜 → 라인 차트
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
          dot={{ r: 2 }}
        />
        <Line
          type="monotone"
          dataKey="하위평균"
          stroke="hsl(142, 71%, 45%)"
          strokeWidth={1.5}
          strokeDasharray="5 5"
          dot={{ r: 2 }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}

function StatCard({
  label,
  value,
  color,
}: {
  label: string
  value: number | null
  color: string
}) {
  return (
    <div className="rounded-lg border p-3 text-center">
      <p className="text-xs text-muted-foreground mb-1">{label}</p>
      <p className={`text-lg font-semibold ${color}`}>
        {formatPrice(value)}
      </p>
    </div>
  )
}
