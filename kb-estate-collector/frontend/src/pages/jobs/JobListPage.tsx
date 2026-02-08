import { useState } from "react"
import { useNavigate } from "react-router-dom"
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
  useCreateAndRunJob,
  useRunJob,
  usePauseJob,
  useResumeJob,
  useRunRegion,
} from "@/hooks/useJobs"
import {
  JOB_TYPE_LABELS,
  JOB_STATUS_LABELS,
  RUN_STATUS_LABELS,
  COMMON_REGIONS,
} from "@/lib/constants"
import { formatRelativeTime } from "@/lib/format"
import { toast } from "sonner"

function parseTargetSummary(targetConfig: string | null): string {
  if (!targetConfig) return "전체 활성 단지"
  try {
    const config = JSON.parse(targetConfig)
    if (config.region_code) {
      const label = COMMON_REGIONS[config.region_code]
      return label ? `${label} 지역` : `${config.region_code} 지역`
    }
    if (config.complex_ids && Array.isArray(config.complex_ids)) {
      return `${config.complex_ids.length}개 단지`
    }
    return "전체 활성 단지"
  } catch {
    return "전체 활성 단지"
  }
}

export default function JobListPage() {
  const navigate = useNavigate()
  const [showCreate, setShowCreate] = useState(false)
  const [showRegion, setShowRegion] = useState(false)

  const { data: jobs, isLoading } = useJobs()
  const createMutation = useCreateJob()
  const createAndRunMutation = useCreateAndRunJob()
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
                  <TableHead>대상</TableHead>
                  <TableHead>스케줄</TableHead>
                  <TableHead>상태</TableHead>
                  <TableHead>마지막 실행</TableHead>
                  <TableHead className="text-right">작업</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobs.map((job) => (
                  <TableRow
                    key={job.id}
                    className="cursor-pointer hover:bg-accent"
                    onClick={() => navigate(`/jobs/${job.id}`)}
                  >
                    <TableCell className="font-medium">{job.name}</TableCell>
                    <TableCell className="text-sm">
                      {JOB_TYPE_LABELS[job.job_type] || job.job_type}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {parseTargetSummary(job.target_config)}
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
                    <TableCell className="text-sm">
                      {job.last_run_status ? (
                        <div className="flex items-center gap-1.5">
                          <StatusBadge
                            status={job.last_run_status}
                            label={
                              RUN_STATUS_LABELS[job.last_run_status] ||
                              job.last_run_status
                            }
                          />
                          <span className="text-xs text-muted-foreground">
                            {formatRelativeTime(job.last_run_at)}
                          </span>
                        </div>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <div
                        className="flex justify-end gap-1"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {job.status === "active" && (
                          <>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() =>
                                runMutation.mutate(job.id, {
                                  onSuccess: (res) => {
                                    toast.success("작업이 실행되었습니다")
                                    navigate(`/runs/${res.run_id}`)
                                  },
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
                        {job.status === "paused" && (
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
        runLoading={createAndRunMutation.isPending}
        onSubmit={(data) => {
          createMutation.mutate(data, {
            onSuccess: () => {
              toast.success("작업이 생성되었습니다")
              setShowCreate(false)
            },
            onError: () => toast.error("작업 생성에 실패했습니다"),
          })
        }}
        onCreateAndRun={(data) => {
          createAndRunMutation.mutate(data, {
            onSuccess: (res) => {
              toast.success("작업이 생성되고 즉시 실행되었습니다")
              setShowCreate(false)
              navigate(`/runs/${res.run_id}`)
            },
            onError: () => toast.error("작업 생성/실행에 실패했습니다"),
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
                  toast.success(res.message)
                  setShowRegion(false)
                  navigate(`/runs/${res.run_id}`)
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
