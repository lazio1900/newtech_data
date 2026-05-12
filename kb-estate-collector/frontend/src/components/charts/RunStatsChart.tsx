import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts"
import type { CrawlRun } from "@/types/run"

interface RunStatsChartProps {
  runs: CrawlRun[]
}

export default function RunStatsChart({ runs }: RunStatsChartProps) {
  const chartData = [...runs]
    .sort((a, b) => (a.created_at || "").localeCompare(b.created_at || ""))
    .slice(-14)
    .map((r) => ({
      name: `#${r.id}`,
      성공: r.success_count,
      실패: r.failed_count,
      스킵: r.skipped_count,
    }))

  if (chartData.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">
        실행 이력이 없습니다
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
        <XAxis dataKey="name" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip />
        <Legend />
        <Bar dataKey="성공" fill="var(--jb-sys-success)" radius={[2, 2, 0, 0]} />
        <Bar dataKey="실패" fill="var(--jb-sys-error)" radius={[2, 2, 0, 0]} />
        <Bar dataKey="스킵" fill="var(--jb-text-low)" radius={[2, 2, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
