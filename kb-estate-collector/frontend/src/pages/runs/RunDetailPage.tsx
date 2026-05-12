import { useState, useMemo } from "react"
import { useParams, useNavigate, Link } from "react-router-dom"
import { ArrowLeft, Building2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import PageHeader from "@/components/layout/PageHeader"
import StatusBadge from "@/components/shared/StatusBadge"
import EmptyState from "@/components/shared/EmptyState"
import Pagination, { paginate } from "@/components/shared/Pagination"
import { useRun, useRunTasks } from "@/hooks/useRuns"
import {
  RUN_STATUS_LABELS,
  TASK_STATUS_LABELS,
  COMMON_REGIONS,
  SIDO_REGIONS,
} from "@/lib/constants"
import { formatDateTime, formatDuration } from "@/lib/format"
import type { TaskStatus, TargetComplex } from "@/types/run"

const TASK_FILTERS: { label: string; value: string | undefined }[] = [
  { label: "전체", value: undefined },
  { label: "성공", value: "success" },
  { label: "실패", value: "failed" },
  { label: "실행중", value: "running" },
  { label: "대기", value: "pending" },
]

export default function RunDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const runId = Number(id)

  const { data: run, isLoading } = useRun(runId)
  const [taskFilter, setTaskFilter] = useState<string | undefined>()
  const [taskPage, setTaskPage] = useState(1)
  const [taskPageSize, setTaskPageSize] = useState(10)
  const { data: tasks } = useRunTasks(runId, {
    status_filter: taskFilter,
    limit: 1000,
  })

  const allTasks = tasks ?? []
  const pagedTasks = useMemo(() => paginate(allTasks, taskPage, taskPageSize), [allTasks, taskPage, taskPageSize])

  if (isLoading) {
    return <p className="py-8 text-center text-muted-foreground">로딩중...</p>
  }

  if (!run) {
    return <EmptyState message="실행을 찾을 수 없습니다" />
  }

  return (
    <div>
      <PageHeader
        title={`실행 #${run.id}`}
        actions={
          <Button variant="ghost" size="sm" onClick={() => navigate("/runs")}>
            <ArrowLeft className="mr-1.5 h-4 w-4" />
            목록
          </Button>
        }
      />

      {/* 요약 정보 */}
      <div className="mb-4 grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-md border p-3">
          <span className="text-muted-foreground">상태</span>
          <div className="mt-1">
            <StatusBadge
              status={run.status}
              label={RUN_STATUS_LABELS[run.status] || run.status}
            />
          </div>
        </div>
        <div className="rounded-md border p-3">
          <span className="text-muted-foreground">시작</span>
          <p className="mt-1 font-medium">{formatDateTime(run.started_at)}</p>
        </div>
        <div className="rounded-md border p-3">
          <span className="text-muted-foreground">완료</span>
          <p className="mt-1 font-medium">{formatDateTime(run.finished_at)}</p>
        </div>
        <div className="rounded-md border p-3">
          <span className="text-muted-foreground">소요 시간</span>
          <p className="mt-1 font-medium">
            {formatDuration(run.started_at, run.finished_at)}
          </p>
        </div>
      </div>

      <div className="mb-6 grid gap-2 text-sm sm:grid-cols-2">
        <div className="rounded-md border p-3">
          <span className="text-muted-foreground">태스크</span>
          <p className="mt-1 font-medium">
            총 {run.total_tasks} / 성공{" "}
            <span className="text-jb-sys-success">{run.success_count}</span> / 실패{" "}
            <span className="text-jb-sys-error">{run.failed_count}</span> / 스킵{" "}
            {run.skipped_count}
          </p>
        </div>
        <div className="rounded-md border p-3">
          <span className="text-muted-foreground">수집 대상</span>
          <div className="mt-1">
            {run.target_complexes && run.target_complexes.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {run.target_complexes.map((c: TargetComplex) => {
                  const regionName = c.region_code
                    ? COMMON_REGIONS[c.region_code.slice(0, 5)] ||
                      SIDO_REGIONS[c.region_code.slice(0, 2)] ||
                      ""
                    : ""
                  return (
                    <Link
                      key={c.id}
                      to={`/complexes/${c.id}`}
                      className="inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs hover:bg-accent"
                    >
                      <Building2 className="h-3 w-3 text-muted-foreground" />
                      <span className="font-medium">{c.name}</span>
                      {regionName && (
                        <span className="text-muted-foreground">
                          ({regionName})
                        </span>
                      )}
                    </Link>
                  )
                })}
              </div>
            ) : (
              <span className="text-muted-foreground">-</span>
            )}
          </div>
        </div>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">태스크 목록</CardTitle>
            <div className="flex gap-1">
              {TASK_FILTERS.map((f) => (
                <Button
                  key={f.label}
                  variant={taskFilter === f.value ? "default" : "outline"}
                  size="sm"
                  onClick={() => { setTaskFilter(f.value); setTaskPage(1) }}
                  className="h-7 px-2.5 text-xs"
                >
                  {f.label}
                </Button>
              ))}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {allTasks.length === 0 ? (
            <EmptyState message="태스크가 없습니다" />
          ) : (
            <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>태스크 키</TableHead>
                  <TableHead>상태</TableHead>
                  <TableHead>수집</TableHead>
                  <TableHead>저장</TableHead>
                  <TableHead>재시도</TableHead>
                  <TableHead>소요시간</TableHead>
                  <TableHead>에러</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pagedTasks.map((task) => (
                  <TableRow key={task.id}>
                    <TableCell className="max-w-[200px] truncate text-xs font-mono">
                      {task.task_key}
                    </TableCell>
                    <TableCell>
                      <StatusBadge
                        status={task.status}
                        label={
                          TASK_STATUS_LABELS[task.status as TaskStatus] ||
                          task.status
                        }
                      />
                    </TableCell>
                    <TableCell className="text-sm">
                      {task.items_collected}
                    </TableCell>
                    <TableCell className="text-sm">{task.items_saved}</TableCell>
                    <TableCell className="text-sm">{task.retry_count}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDuration(task.started_at, task.finished_at)}
                    </TableCell>
                    <TableCell className="max-w-[200px] truncate text-xs text-jb-sys-error">
                      {task.error_message || "-"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <Pagination
              total={allTasks.length}
              page={taskPage}
              pageSize={taskPageSize}
              onPageChange={setTaskPage}
              onPageSizeChange={setTaskPageSize}
            />
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
