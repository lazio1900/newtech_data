import { useState } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { ArrowLeft } from "lucide-react"
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
import { useRun, useRunTasks } from "@/hooks/useRuns"
import { RUN_STATUS_LABELS, TASK_STATUS_LABELS } from "@/lib/constants"
import { formatDateTime, formatDuration } from "@/lib/format"
import type { TaskStatus } from "@/types/run"

const TASK_FILTERS: { label: string; value: string | undefined }[] = [
  { label: "전체", value: undefined },
  { label: "성공", value: "SUCCESS" },
  { label: "실패", value: "FAILED" },
  { label: "실행중", value: "RUNNING" },
  { label: "대기", value: "PENDING" },
]

export default function RunDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const runId = Number(id)

  const { data: run, isLoading } = useRun(runId)
  const [taskFilter, setTaskFilter] = useState<string | undefined>()
  const { data: tasks } = useRunTasks(runId, {
    status_filter: taskFilter,
    limit: 200,
  })

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

      <div className="mb-6 grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
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
          <span className="text-muted-foreground">시작 / 종료</span>
          <p className="mt-1 font-medium">
            {formatDateTime(run.started_at)} ~ {formatDateTime(run.finished_at)}
          </p>
        </div>
        <div className="rounded-md border p-3">
          <span className="text-muted-foreground">소요 시간</span>
          <p className="mt-1 font-medium">
            {formatDuration(run.started_at, run.finished_at)}
          </p>
        </div>
        <div className="rounded-md border p-3">
          <span className="text-muted-foreground">태스크</span>
          <p className="mt-1 font-medium">
            총 {run.total_tasks} / 성공{" "}
            <span className="text-green-600">{run.success_count}</span> / 실패{" "}
            <span className="text-red-600">{run.failed_count}</span> / 스킵{" "}
            {run.skipped_count}
          </p>
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
                  onClick={() => setTaskFilter(f.value)}
                  className="h-7 px-2.5 text-xs"
                >
                  {f.label}
                </Button>
              ))}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {!tasks || tasks.length === 0 ? (
            <EmptyState message="태스크가 없습니다" />
          ) : (
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
                {tasks.map((task) => (
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
                    <TableCell className="max-w-[200px] truncate text-xs text-red-600">
                      {task.error_message || "-"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
