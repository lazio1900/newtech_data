import { useState } from "react"
import { Plus, Play, Pause, MapPin } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
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
import RegionCodeInput from "@/components/shared/RegionCodeInput"
import JobFormDialog from "./JobFormDialog"
import {
  useJobs,
  useCreateJob,
  useRunJob,
  usePauseJob,
  useResumeJob,
  useRunRegion,
} from "@/hooks/useJobs"
import { JOB_TYPE_LABELS, JOB_STATUS_LABELS } from "@/lib/constants"
import { formatDateTime } from "@/lib/format"
import { toast } from "sonner"

export default function JobListPage() {
  const [showCreate, setShowCreate] = useState(false)
  const [showRegion, setShowRegion] = useState(false)

  const { data: jobs, isLoading } = useJobs()
  const createMutation = useCreateJob()
  const runMutation = useRunJob()
  const pauseMutation = usePauseJob()
  const resumeMutation = useResumeJob()
  const regionMutation = useRunRegion()

  return (
    <div>
      <PageHeader
        title="수집 작업"
        description="데이터 수집 작업 관리"
        actions={
          <>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowRegion(true)}
            >
              <MapPin className="mr-1.5 h-4 w-4" />
              지역 수집
            </Button>
            <Button size="sm" onClick={() => setShowCreate(true)}>
              <Plus className="mr-1.5 h-4 w-4" />
              작업 생성
            </Button>
          </>
        }
      />

      <Card>
        <CardContent className="pt-6">
          {isLoading ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              로딩중...
            </p>
          ) : !jobs || jobs.length === 0 ? (
            <EmptyState message="등록된 작업이 없습니다" />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>작업명</TableHead>
                  <TableHead>유형</TableHead>
                  <TableHead>스케줄</TableHead>
                  <TableHead>상태</TableHead>
                  <TableHead>생성일</TableHead>
                  <TableHead className="text-right">작업</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobs.map((job) => (
                  <TableRow key={job.id}>
                    <TableCell className="font-medium">{job.name}</TableCell>
                    <TableCell className="text-sm">
                      {JOB_TYPE_LABELS[job.job_type] || job.job_type}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {job.cron_schedule || "-"}
                    </TableCell>
                    <TableCell>
                      <StatusBadge
                        status={job.status}
                        label={JOB_STATUS_LABELS[job.status] || job.status}
                      />
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDateTime(job.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        {job.status === "ACTIVE" && (
                          <>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() =>
                                runMutation.mutate(job.id, {
                                  onSuccess: (res) =>
                                    toast.success(
                                      res.message || "작업이 실행되었습니다"
                                    ),
                                  onError: () =>
                                    toast.error("실행에 실패했습니다"),
                                })
                              }
                              disabled={runMutation.isPending}
                            >
                              <Play className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() =>
                                pauseMutation.mutate(job.id, {
                                  onSuccess: () =>
                                    toast.success("작업이 일시정지되었습니다"),
                                  onError: () =>
                                    toast.error("일시정지에 실패했습니다"),
                                })
                              }
                              disabled={pauseMutation.isPending}
                            >
                              <Pause className="h-4 w-4" />
                            </Button>
                          </>
                        )}
                        {job.status === "PAUSED" && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() =>
                              resumeMutation.mutate(job.id, {
                                onSuccess: () =>
                                  toast.success("작업이 재개되었습니다"),
                                onError: () =>
                                  toast.error("재개에 실패했습니다"),
                              })
                            }
                            disabled={resumeMutation.isPending}
                          >
                            <Play className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <JobFormDialog
        open={showCreate}
        onOpenChange={setShowCreate}
        loading={createMutation.isPending}
        onSubmit={(data) => {
          createMutation.mutate(data, {
            onSuccess: () => {
              toast.success("작업이 생성되었습니다")
              setShowCreate(false)
            },
            onError: () => toast.error("작업 생성에 실패했습니다"),
          })
        }}
      />

      <Dialog open={showRegion} onOpenChange={setShowRegion}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>지역 전체 수집</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            지역코드를 입력하면 단지 발견 + 시세 + 실거래가 + 매물을 한번에
            수집합니다.
          </p>
          <RegionCodeInput
            loading={regionMutation.isPending}
            buttonLabel="수집 시작"
            onSubmit={(code) => {
              regionMutation.mutate(code, {
                onSuccess: (res) => {
                  toast.success(res.message || "지역 수집이 시작되었습니다")
                  setShowRegion(false)
                },
                onError: () => toast.error("지역 수집에 실패했습니다"),
              })
            }}
          />
        </DialogContent>
      </Dialog>
    </div>
  )
}
