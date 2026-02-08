import { Link } from "react-router-dom"
import { Card, CardContent } from "@/components/ui/card"
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
import { useRuns } from "@/hooks/useRuns"
import { RUN_STATUS_LABELS } from "@/lib/constants"
import { formatDateTime, formatDuration } from "@/lib/format"

export default function RunListPage() {
  const { data: runs, isLoading } = useRuns({ limit: 100 })

  return (
    <div>
      <PageHeader title="실행 이력" description="데이터 수집 실행 내역" />

      <Card>
        <CardContent className="pt-6">
          {isLoading ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              로딩중...
            </p>
          ) : !runs || runs.length === 0 ? (
            <EmptyState message="실행 이력이 없습니다" />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead>상태</TableHead>
                  <TableHead>시작 시간</TableHead>
                  <TableHead>소요 시간</TableHead>
                  <TableHead>태스크</TableHead>
                  <TableHead>성공</TableHead>
                  <TableHead>실패</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.map((run) => (
                  <TableRow key={run.id} className="cursor-pointer hover:bg-accent">
                    <TableCell>
                      <Link
                        to={`/runs/${run.id}`}
                        className="font-medium text-primary hover:underline"
                      >
                        #{run.id}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <StatusBadge
                        status={run.status}
                        label={RUN_STATUS_LABELS[run.status] || run.status}
                      />
                    </TableCell>
                    <TableCell className="text-sm">
                      {formatDateTime(run.started_at)}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDuration(run.started_at, run.finished_at)}
                    </TableCell>
                    <TableCell className="text-sm">{run.total_tasks}</TableCell>
                    <TableCell className="text-sm text-green-600">
                      {run.success_count}
                    </TableCell>
                    <TableCell className="text-sm text-red-600">
                      {run.failed_count}
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
