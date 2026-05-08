import { Fragment, useState } from "react"
import { useNavigate, Link } from "react-router-dom"
import { Play, Settings, Loader2, CalendarClock, ChevronRight, ChevronDown } from "lucide-react"
import { SigunguSubRows } from "./BatchSubRows"
import { batchesApi } from "@/api/batches"
void batchesApi  // scoped schedule 다이얼로그는 후속 작업, 호출 시 사용
import { Checkbox } from "@/components/ui/checkbox"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
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
import ScheduleDialog, { cronToLabel, buildCron } from "./ScheduleDialog"
import type { Interval } from "./ScheduleDialog"
import {
  useBatches,
  useRunBatch,
  useUpdateBatchSchedule,
} from "@/hooks/useBatches"
import { RUN_STATUS_LABELS, SIDO_REGIONS } from "@/lib/constants"
import { formatRelativeTime, formatDuration } from "@/lib/format"
import { toast } from "sonner"
import type { Batch } from "@/types/batch"

const DAYS_LABEL: Record<string, string> = {
  "1": "월", "2": "화", "3": "수", "4": "목",
  "5": "금", "6": "토", "0": "일",
}

// 시/도 순서 (SIDO_REGIONS 키 순서)
const SIDO_ORDER = Object.keys(SIDO_REGIONS)

export default function BatchSettingsPage() {
  const navigate = useNavigate()
  const { data: batches, isLoading } = useBatches()
  const runMutation = useRunBatch()
  const scheduleMutation = useUpdateBatchSchedule()

  const [scheduleTarget, setScheduleTarget] = useState<Batch | null>(null)
  // scoped 스케줄 — 다이얼로그 후속 작업 (지금은 토스트로만 안내)
  const [runningCodes, setRunningCodes] = useState<Set<string>>(new Set())
  const [selectedCodes, setSelectedCodes] = useState<Set<string>>(new Set())
  const [batchRunning, setBatchRunning] = useState(false)
  const [expandedSido, setExpandedSido] = useState<string | null>(null)

  // 시차 스케줄 다이얼로그
  const [showStagger, setShowStagger] = useState(false)
  const [staggerDay, setStaggerDay] = useState("6")
  const [staggerStartHour, setStaggerStartHour] = useState("10")
  const [staggerInterval, setStaggerInterval] = useState("30") // 분 간격
  const [staggerSaving, setStaggerSaving] = useState(false)

  // 단지가 등록된 배치만 상단
  const sortedBatches = [...(batches || [])].sort(
    (a, b) => b.complex_count - a.complex_count,
  )

  const selectableBatches = sortedBatches.filter((b) => b.complex_count > 0)
  const allSelected =
    selectableBatches.length > 0 &&
    selectableBatches.every((b) => selectedCodes.has(b.sido_code))

  const toggleAll = () => {
    if (allSelected) {
      setSelectedCodes(new Set())
    } else {
      setSelectedCodes(new Set(selectableBatches.map((b) => b.sido_code)))
    }
  }

  const toggleOne = (code: string) => {
    setSelectedCodes((prev) => {
      const next = new Set(prev)
      if (next.has(code)) next.delete(code)
      else next.add(code)
      return next
    })
  }

  async function handleBatchRun() {
    const codes = Array.from(selectedCodes)
    if (codes.length === 0) return

    setBatchRunning(true)
    let lastRunId: number | null = null
    let successCount = 0
    let failCount = 0

    for (const code of codes) {
      try {
        const res = await runMutation.mutateAsync(code)
        lastRunId = res.run_id
        successCount++
      } catch {
        failCount++
      }
    }

    setBatchRunning(false)
    setSelectedCodes(new Set())

    if (failCount > 0) {
      toast.warning(`${successCount}개 시작, ${failCount}개 실패`)
    } else {
      toast.success(`${successCount}개 시/도 크롤링 시작`)
    }
    if (lastRunId) navigate(`/runs/${lastRunId}`)
  }

  async function handleStaggerSave() {
    setStaggerSaving(true)
    const intervalMin = parseInt(staggerInterval)
    const startHour = parseInt(staggerStartHour)
    const day = staggerDay

    // 단지가 있는 시/도만 스케줄 설정 (SIDO_ORDER 순서)
    const targets = SIDO_ORDER.filter((code) => {
      const b = batches?.find((bb) => bb.sido_code === code)
      return b && b.complex_count > 0
    })

    let failCount = 0
    for (let i = 0; i < targets.length; i++) {
      const totalMinutes = startHour * 60 + i * intervalMin
      const h = Math.floor(totalMinutes / 60)
      const m = totalMinutes % 60
      const cron = buildCron("weekly" as Interval, day, String(h), String(m))

      try {
        await scheduleMutation.mutateAsync({
          sidoCode: targets[i],
          cronSchedule: cron,
        })
      } catch {
        failCount++
      }
    }

    setStaggerSaving(false)
    setShowStagger(false)

    if (failCount > 0) {
      toast.warning(`스케줄 설정 완료 (${failCount}개 실패)`)
    } else {
      toast.success(
        `${targets.length}개 시/도에 ${DAYS_LABEL[day]}요일 ${staggerStartHour}시부터 ${intervalMin}분 간격으로 설정`,
      )
    }
  }

  // 시차 미리보기
  const staggerPreview = () => {
    const intervalMin = parseInt(staggerInterval)
    const startHour = parseInt(staggerStartHour)
    const targets = SIDO_ORDER.filter((code) => {
      const b = batches?.find((bb) => bb.sido_code === code)
      return b && b.complex_count > 0
    })
    const items: string[] = []
    for (let i = 0; i < Math.min(targets.length, 4); i++) {
      const totalMinutes = startHour * 60 + i * intervalMin
      const h = Math.floor(totalMinutes / 60)
      const m = totalMinutes % 60
      const name = SIDO_REGIONS[targets[i]]
      items.push(
        `${name} ${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`,
      )
    }
    if (targets.length > 4) items.push(`... 외 ${targets.length - 4}개`)
    return items
  }

  return (
    <div>
      <PageHeader
        title="배치 설정"
        description="시/도별 정기 크롤링 설정 및 실행"
        actions={
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowStagger(true)}
          >
            <CalendarClock className="mr-1.5 h-4 w-4" />
            일괄 스케줄
          </Button>
        }
      />

      <Card>
        <CardContent className="pt-6">
          {isLoading ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              로딩중...
            </p>
          ) : (
            <>
              {/* 선택 시 액션 바 */}
              {selectedCodes.size > 0 && (
                <div className="mb-3 flex items-center justify-between rounded-md border border-primary/20 bg-primary/5 px-3 py-2">
                  <span className="text-sm">
                    <span className="font-medium">{selectedCodes.size}</span>개
                    시/도 선택됨
                  </span>
                  <Button
                    size="sm"
                    onClick={handleBatchRun}
                    disabled={batchRunning}
                  >
                    {batchRunning ? (
                      <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                    ) : (
                      <Play className="mr-1.5 h-4 w-4" />
                    )}
                    크롤링 실행 ({selectedCodes.size})
                  </Button>
                </div>
              )}

              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10">
                      <Checkbox
                        checked={allSelected}
                        onCheckedChange={toggleAll}
                      />
                    </TableHead>
                    <TableHead className="w-20">시/도</TableHead>
                    <TableHead className="w-16 text-center">단지</TableHead>
                    <TableHead className="w-36">스케줄</TableHead>
                    <TableHead>최근 실행</TableHead>
                    <TableHead className="w-24">소요시간</TableHead>
                    <TableHead className="w-28">결과</TableHead>
                    <TableHead className="w-20 text-right">실행</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sortedBatches.map((batch) => {
                    const lastRun = batch.last_runs[0]
                    const isRunning = runningCodes.has(batch.sido_code)
                    const hasComplexes = batch.complex_count > 0
                    const isExpanded = expandedSido === batch.sido_code

                    return (
                      <Fragment key={batch.sido_code}>
                      <TableRow className={hasComplexes ? "" : "opacity-50"}>
                        {/* 체크박스 */}
                        <TableCell>
                          <Checkbox
                            checked={selectedCodes.has(batch.sido_code)}
                            onCheckedChange={() => toggleOne(batch.sido_code)}
                            disabled={!hasComplexes}
                          />
                        </TableCell>

                        {/* 시/도 (▶/▼ 토글) */}
                        <TableCell className="font-medium">
                          <button
                            onClick={() =>
                              setExpandedSido(isExpanded ? null : batch.sido_code)
                            }
                            disabled={!hasComplexes}
                            className="inline-flex items-center gap-1 hover:text-primary disabled:opacity-50"
                          >
                            {isExpanded
                              ? <ChevronDown className="h-3 w-3" />
                              : <ChevronRight className="h-3 w-3" />}
                            {batch.sido_name}
                          </button>
                        </TableCell>

                        {/* 단지 수 */}
                        <TableCell className="text-center text-sm">
                          {hasComplexes ? (
                            batch.complex_count
                          ) : (
                            <span className="text-muted-foreground">0</span>
                          )}
                        </TableCell>

                        {/* 스케줄 */}
                        <TableCell>
                          <button
                            onClick={() => setScheduleTarget(batch)}
                            className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs hover:bg-accent"
                          >
                            <Settings className="h-3 w-3 text-muted-foreground" />
                            <span
                              className={
                                batch.cron_schedule
                                  ? "text-sm"
                                  : "text-sm text-muted-foreground"
                              }
                            >
                              {cronToLabel(batch.cron_schedule)}
                            </span>
                          </button>
                        </TableCell>

                        {/* 최근 실행 */}
                        <TableCell className="text-sm">
                          {lastRun ? (
                            <div className="flex items-center gap-1.5">
                              <StatusBadge
                                status={lastRun.status}
                                label={
                                  RUN_STATUS_LABELS[lastRun.status] ||
                                  lastRun.status
                                }
                              />
                              <Link
                                to={`/runs/${lastRun.id}`}
                                className="text-xs text-muted-foreground hover:text-primary hover:underline"
                              >
                                {formatRelativeTime(lastRun.started_at)}
                              </Link>
                            </div>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>

                        {/* 소요시간 */}
                        <TableCell className="text-xs text-muted-foreground">
                          {lastRun
                            ? formatDuration(
                                lastRun.started_at,
                                lastRun.finished_at,
                              )
                            : "-"}
                        </TableCell>

                        {/* 결과 */}
                        <TableCell className="text-sm">
                          {lastRun ? (
                            <span>
                              <span className="text-green-600">
                                {lastRun.success_count}
                              </span>
                              {" / "}
                              <span className="text-red-600">
                                {lastRun.failed_count}
                              </span>
                              {lastRun.skipped_count > 0 && (
                                <>
                                  {" / "}
                                  <span className="text-gray-400">
                                    {lastRun.skipped_count}
                                  </span>
                                </>
                              )}
                            </span>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>

                        {/* 재실행 */}
                        <TableCell className="text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={
                              !hasComplexes ||
                              isRunning ||
                              batchRunning
                            }
                            onClick={() => {
                              setRunningCodes((prev) => new Set(prev).add(batch.sido_code))
                              runMutation.mutate(batch.sido_code, {
                                onSuccess: (res) => {
                                  toast.success(res.message)
                                  setRunningCodes((prev) => {
                                    const next = new Set(prev)
                                    next.delete(batch.sido_code)
                                    return next
                                  })
                                  navigate(`/runs/${res.run_id}`)
                                },
                                onError: () => {
                                  toast.error("실행에 실패했습니다")
                                  setRunningCodes((prev) => {
                                    const next = new Set(prev)
                                    next.delete(batch.sido_code)
                                    return next
                                  })
                                },
                              })
                            }}
                          >
                            {isRunning ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Play className="h-4 w-4" />
                            )}
                          </Button>
                        </TableCell>
                      </TableRow>
                      {isExpanded && (
                        <SigunguSubRows
                          sidoCode={batch.sido_code}
                          onScheduleClick={(_scope, _code, name) =>
                            toast.info(`${name} 단위 스케줄 설정은 곧 지원됩니다`)
                          }
                        />
                      )}
                      </Fragment>
                    )
                  })}
                </TableBody>
              </Table>
            </>
          )}
        </CardContent>
      </Card>

      {/* 이전 실행 이력 */}
      {sortedBatches.some((b) => b.last_runs.length > 1) && (
        <Card className="mt-4">
          <CardContent className="pt-6">
            <h3 className="mb-3 text-sm font-medium">이전 실행 이력</h3>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>시/도</TableHead>
                  <TableHead>실행 ID</TableHead>
                  <TableHead>상태</TableHead>
                  <TableHead>시작</TableHead>
                  <TableHead>소요시간</TableHead>
                  <TableHead>성공/실패</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedBatches
                  .flatMap((batch) =>
                    batch.last_runs.slice(1).map((run) => ({
                      ...run,
                      sido_name: batch.sido_name,
                    })),
                  )
                  .sort(
                    (a, b) =>
                      new Date(b.started_at || 0).getTime() -
                      new Date(a.started_at || 0).getTime(),
                  )
                  .slice(0, 20)
                  .map((run) => (
                    <TableRow key={run.id}>
                      <TableCell className="text-sm">{run.sido_name}</TableCell>
                      <TableCell>
                        <Link
                          to={`/runs/${run.id}`}
                          className="text-sm font-medium text-primary hover:underline"
                        >
                          #{run.id}
                        </Link>
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
                      <TableCell className="text-xs text-muted-foreground">
                        {formatDuration(run.started_at, run.finished_at)}
                      </TableCell>
                      <TableCell className="text-sm">
                        <span className="text-green-600">
                          {run.success_count}
                        </span>
                        {" / "}
                        <span className="text-red-600">
                          {run.failed_count}
                        </span>
                      </TableCell>
                    </TableRow>
                  ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* 개별 스케줄 설정 */}
      {scheduleTarget && (
        <ScheduleDialog
          open={!!scheduleTarget}
          onOpenChange={(open) => {
            if (!open) setScheduleTarget(null)
          }}
          sidoName={scheduleTarget.sido_name}
          currentCron={scheduleTarget.cron_schedule}
          loading={scheduleMutation.isPending}
          onSave={(cron) => {
            scheduleMutation.mutate(
              {
                sidoCode: scheduleTarget.sido_code,
                cronSchedule: cron,
              },
              {
                onSuccess: () => {
                  toast.success(
                    cron
                      ? "스케줄이 설정되었습니다"
                      : "스케줄이 해제되었습니다",
                  )
                  setScheduleTarget(null)
                },
                onError: () => toast.error("스케줄 저장에 실패했습니다"),
              },
            )
          }}
        />
      )}

      {/* 시차 일괄 스케줄 다이얼로그 */}
      <Dialog open={showStagger} onOpenChange={setShowStagger}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>일괄 스케줄 설정</DialogTitle>
          </DialogHeader>

          <p className="text-sm text-muted-foreground">
            단지가 등록된 시/도에 시차를 두어 스케줄을 자동 설정합니다.
            KB API 부하를 분산하여 안정적으로 수집합니다.
          </p>

          <div className="space-y-4 py-2">
            {/* 요일 */}
            <div>
              <label className="mb-1.5 block text-sm font-medium">요일</label>
              <Select value={staggerDay} onValueChange={setStaggerDay}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {[
                    { v: "1", l: "월요일" },
                    { v: "2", l: "화요일" },
                    { v: "3", l: "수요일" },
                    { v: "4", l: "목요일" },
                    { v: "5", l: "금요일" },
                    { v: "6", l: "토요일" },
                    { v: "0", l: "일요일" },
                  ].map((d) => (
                    <SelectItem key={d.v} value={d.v}>
                      {d.l}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* 시작 시간 */}
            <div>
              <label className="mb-1.5 block text-sm font-medium">
                시작 시간
              </label>
              <Select
                value={staggerStartHour}
                onValueChange={setStaggerStartHour}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Array.from({ length: 24 }, (_, i) => (
                    <SelectItem key={i} value={String(i)}>
                      {String(i).padStart(2, "0")}시
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* 간격 */}
            <div>
              <label className="mb-1.5 block text-sm font-medium">
                시/도 간 간격
              </label>
              <Select
                value={staggerInterval}
                onValueChange={setStaggerInterval}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="15">15분</SelectItem>
                  <SelectItem value="30">30분</SelectItem>
                  <SelectItem value="60">1시간</SelectItem>
                  <SelectItem value="120">2시간</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* 미리보기 */}
            <div className="rounded-md border bg-muted/30 px-3 py-2.5">
              <span className="text-xs text-muted-foreground">
                미리보기 ({DAYS_LABEL[staggerDay]}요일)
              </span>
              <div className="mt-1 space-y-0.5">
                {staggerPreview().map((item, i) => (
                  <p key={i} className="text-sm">
                    {item}
                  </p>
                ))}
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowStagger(false)}
            >
              취소
            </Button>
            <Button
              size="sm"
              onClick={handleStaggerSave}
              disabled={staggerSaving}
            >
              {staggerSaving ? (
                <>
                  <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                  설정중...
                </>
              ) : (
                "일괄 설정"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
