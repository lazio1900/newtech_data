import { Link } from "react-router-dom"
import { Building2, ListChecks, History, TrendingUp } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import PageHeader from "@/components/layout/PageHeader"
import StatusBadge from "@/components/shared/StatusBadge"
import RunStatsChart from "@/components/charts/RunStatsChart"
import { useComplexes } from "@/hooks/useComplexes"
import { useJobs } from "@/hooks/useJobs"
import { useRuns } from "@/hooks/useRuns"
import { RUN_STATUS_LABELS } from "@/lib/constants"
import { formatDateTime, formatDuration } from "@/lib/format"

export default function DashboardPage() {
  const { data: complexes } = useComplexes({ limit: 1000 })
  const { data: jobs } = useJobs()
  const { data: runs } = useRuns({ limit: 50 })

  const complexList = complexes?.items ?? []
  const totalComplexes = complexes?.total ?? 0
  const activeComplexes = complexList.filter((c) => c.is_active).length
  const activeJobs = jobs?.filter((j) => j.status === "active").length ?? 0
  const recentRuns = runs?.slice(0, 5) ?? []
  const lastSuccess = runs?.find((r) => r.status === "success")

  return (
    <div>
      <PageHeader title="대시보드" description="KB 부동산 데이터 수집 현황" />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Link to="/complexes">
          <Card className="cursor-pointer transition-shadow hover:shadow-md">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">총 단지</CardTitle>
              <Building2 className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{totalComplexes}</div>
              <p className="text-xs text-muted-foreground">활성 {activeComplexes}개</p>
            </CardContent>
          </Card>
        </Link>

        <Link to="/batches">
          <Card className="cursor-pointer transition-shadow hover:shadow-md">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">활성 작업</CardTitle>
              <ListChecks className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{activeJobs}</div>
              <p className="text-xs text-muted-foreground">전체 {jobs?.length ?? 0}개</p>
            </CardContent>
          </Card>
        </Link>

        <Link to="/runs">
          <Card className="cursor-pointer transition-shadow hover:shadow-md">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">총 실행</CardTitle>
              <History className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{runs?.length ?? 0}</div>
              <p className="text-xs text-muted-foreground">최근 50건</p>
            </CardContent>
          </Card>
        </Link>

        <Link to="/runs">
          <Card className="cursor-pointer transition-shadow hover:shadow-md">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">최근 성공</CardTitle>
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {lastSuccess ? `${lastSuccess.success_count}건` : "-"}
              </div>
              <p className="text-xs text-muted-foreground">
                {lastSuccess
                  ? formatDateTime(lastSuccess.started_at)
                  : "실행 이력 없음"}
              </p>
            </CardContent>
          </Card>
        </Link>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">최근 실행 이력</CardTitle>
          </CardHeader>
          <CardContent>
            {recentRuns.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">
                실행 이력이 없습니다
              </p>
            ) : (
              <div className="space-y-3">
                {recentRuns.map((run) => (
                  <Link
                    key={run.id}
                    to={`/runs/${run.id}`}
                    className="flex items-center justify-between rounded-md border p-3 transition-colors hover:bg-accent"
                  >
                    <div className="flex items-center gap-3">
                      <StatusBadge
                        status={run.status}
                        label={RUN_STATUS_LABELS[run.status] || run.status}
                      />
                      <span className="text-sm">
                        실행 #{run.id}
                        {run.target_summary && (
                          <span className="ml-2 text-muted-foreground">
                            ({run.target_summary})
                          </span>
                        )}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-muted-foreground">
                      <span>
                        {run.success_count}/{run.total_tasks} 성공
                      </span>
                      <span>{formatDuration(run.started_at, run.finished_at)}</span>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">수집 현황</CardTitle>
          </CardHeader>
          <CardContent>
            <RunStatsChart runs={runs ?? []} />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
