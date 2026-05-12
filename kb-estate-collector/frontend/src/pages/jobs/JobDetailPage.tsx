import { useState } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { ArrowLeft, Play, Pause, Save } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import PageHeader from "@/components/layout/PageHeader"
import StatusBadge from "@/components/shared/StatusBadge"
import {
  useJob,
  useUpdateJob,
  useRunJob,
  usePauseJob,
  useResumeJob,
} from "@/hooks/useJobs"
import { useRuns } from "@/hooks/useRuns"
import {
  JOB_TYPE_LABELS,
  JOB_STATUS_LABELS,
  RUN_STATUS_LABELS,
  CRON_PRESETS,
} from "@/lib/constants"
import { formatDateTime, formatRelativeTime, formatDuration } from "@/lib/format"
import { toast } from "sonner"

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const jobId = Number(id)

  const { data: job, isLoading } = useJob(jobId)
  const { data: runs } = useRuns({ job_id: jobId, limit: 20 })
  const updateMutation = useUpdateJob()
  const runMutation = useRunJob()
  const pauseMutation = usePauseJob()
  const resumeMutation = useResumeJob()

  const [editName, setEditName] = useState("")
  const [editDesc, setEditDesc] = useState("")
  const [editCron, setEditCron] = useState("")
  const [editing, setEditing] = useState(false)

  function startEditing() {
    if (!job) return
    setEditName(job.name)
    setEditDesc(job.description || "")
    setEditCron(job.cron_schedule || "")
    setEditing(true)
  }

  function saveChanges() {
    if (!job) return
    updateMutation.mutate(
      {
        id: job.id,
        data: {
          name: editName,
          description: editDesc || undefined,
          cron_schedule: editCron || undefined,
        },
      },
      {
        onSuccess: () => {
          toast.success("설정이 저장되었습니다")
          setEditing(false)
        },
        onError: () => toast.error("저장에 실패했습니다"),
      },
    )
  }

  if (isLoading) {
    return (
      <div className="py-12 text-center text-sm text-muted-foreground">
        로딩중...
      </div>
    )
  }

  if (!job) {
    return (
      <div className="py-12 text-center text-sm text-muted-foreground">
        작업을 찾을 수 없습니다
      </div>
    )
  }

  return (
    <div>
      <PageHeader
        title={job.name}
        description={job.description || JOB_TYPE_LABELS[job.job_type] || ""}
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate("/jobs")}
            >
              <ArrowLeft className="mr-1.5 h-4 w-4" />
              목록
            </Button>
            {job.status === "active" && (
              <>
                <Button
                  size="sm"
                  onClick={() =>
                    runMutation.mutate(job.id, {
                      onSuccess: (res) => {
                        toast.success("작업이 실행되었습니다")
                        navigate(`/runs/${res.run_id}`)
                      },
                      onError: () => toast.error("실행에 실패했습니다"),
                    })
                  }
                  disabled={runMutation.isPending}
                >
                  <Play className="mr-1.5 h-4 w-4" />
                  즉시 실행
                </Button>
                <Button
                  variant="outline"
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
                  <Pause className="mr-1.5 h-4 w-4" />
                  일시정지
                </Button>
              </>
            )}
            {job.status === "paused" && (
              <Button
                size="sm"
                onClick={() =>
                  resumeMutation.mutate(job.id, {
                    onSuccess: () => toast.success("작업이 재개되었습니다"),
                    onError: () => toast.error("재개에 실패했습니다"),
                  })
                }
                disabled={resumeMutation.isPending}
              >
                <Play className="mr-1.5 h-4 w-4" />
                재개
              </Button>
            )}
          </div>
        }
      />

      {/* 정보 요약 카드 */}
      <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Card>
          <CardContent className="pt-4 pb-4">
            <div className="text-xs text-muted-foreground">유형</div>
            <div className="mt-1 text-sm font-medium">
              {JOB_TYPE_LABELS[job.job_type] || job.job_type}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-4">
            <div className="text-xs text-muted-foreground">상태</div>
            <div className="mt-1">
              <StatusBadge
                status={job.status}
                label={JOB_STATUS_LABELS[job.status] || job.status}
              />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-4">
            <div className="text-xs text-muted-foreground">스케줄</div>
            <div className="mt-1 text-sm font-medium">
              {job.cron_schedule || "수동 실행"}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-4">
            <div className="text-xs text-muted-foreground">마지막 실행</div>
            <div className="mt-1">
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
                <span className="text-sm text-muted-foreground">-</span>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 탭 */}
      <Tabs defaultValue="settings">
        <TabsList>
          <TabsTrigger value="settings">설정</TabsTrigger>
          <TabsTrigger value="history">실행 이력</TabsTrigger>
        </TabsList>

        <TabsContent value="settings">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base">작업 설정</CardTitle>
              {!editing ? (
                <Button variant="outline" size="sm" onClick={startEditing}>
                  수정
                </Button>
              ) : (
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setEditing(false)}
                  >
                    취소
                  </Button>
                  <Button
                    size="sm"
                    onClick={saveChanges}
                    disabled={updateMutation.isPending}
                  >
                    <Save className="mr-1.5 h-4 w-4" />
                    저장
                  </Button>
                </div>
              )}
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium">작업명</label>
                  {editing ? (
                    <Input
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      className="mt-1"
                    />
                  ) : (
                    <p className="mt-1 text-sm">{job.name}</p>
                  )}
                </div>
                <div>
                  <label className="text-sm font-medium">설명</label>
                  {editing ? (
                    <Input
                      value={editDesc}
                      onChange={(e) => setEditDesc(e.target.value)}
                      placeholder="작업 설명 (선택)"
                      className="mt-1"
                    />
                  ) : (
                    <p className="mt-1 text-sm text-muted-foreground">
                      {job.description || "-"}
                    </p>
                  )}
                </div>
                <div>
                  <label className="text-sm font-medium">Cron 스케줄</label>
                  {editing ? (
                    <div className="mt-1 flex items-center gap-2">
                      <Input
                        value={editCron}
                        onChange={(e) => setEditCron(e.target.value)}
                        placeholder="예) 0 9 * * *"
                        className="max-w-xs"
                      />
                      <Select
                        onValueChange={(v) => setEditCron(v)}
                        value=""
                      >
                        <SelectTrigger className="w-[160px]">
                          <SelectValue placeholder="프리셋 선택" />
                        </SelectTrigger>
                        <SelectContent>
                          {CRON_PRESETS.map((p) => (
                            <SelectItem key={p.value} value={p.value}>
                              {p.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  ) : (
                    <p className="mt-1 text-sm">
                      {job.cron_schedule || "없음 (수동 실행)"}
                    </p>
                  )}
                </div>
                <div>
                  <label className="text-sm font-medium">대상 설정</label>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {job.target_config || "전체 활성 단지"}
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium">생성일</label>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {formatDateTime(job.created_at)}
                    </p>
                  </div>
                  <div>
                    <label className="text-sm font-medium">수정일</label>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {formatDateTime(job.updated_at)}
                    </p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="history">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">실행 이력</CardTitle>
            </CardHeader>
            <CardContent>
              {!runs || runs.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted-foreground">
                  실행 이력이 없습니다
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>ID</TableHead>
                      <TableHead>상태</TableHead>
                      <TableHead>시작</TableHead>
                      <TableHead>소요시간</TableHead>
                      <TableHead>성공/실패/스킵</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {runs.map((run) => (
                      <TableRow
                        key={run.id}
                        className="cursor-pointer hover:bg-accent"
                        onClick={() => navigate(`/runs/${run.id}`)}
                      >
                        <TableCell className="text-sm font-medium">
                          #{run.id}
                        </TableCell>
                        <TableCell>
                          <StatusBadge
                            status={run.status}
                            label={
                              RUN_STATUS_LABELS[run.status] || run.status
                            }
                          />
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {formatRelativeTime(run.started_at)}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {formatDuration(run.started_at, run.finished_at)}
                        </TableCell>
                        <TableCell className="text-sm">
                          <span className="text-jb-sys-success">
                            {run.success_count}
                          </span>
                          {" / "}
                          <span className="text-jb-sys-error">
                            {run.failed_count}
                          </span>
                          {" / "}
                          <span className="text-jb-text-low">
                            {run.skipped_count}
                          </span>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
