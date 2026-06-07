import { Fragment, useState } from "react"
import { ChevronRight, ChevronDown, AlertTriangle, CheckCircle2 } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useWeeklySchedule } from "@/hooks/useBatches"
import type { ChunkDetail } from "@/types/schedule"

const hhmm = (h: number, m: number) =>
  `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`

export default function WeeklySchedulePanel() {
  const { data, isLoading } = useWeeklySchedule()
  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  if (isLoading) {
    return (
      <Card className="mb-4">
        <CardContent className="pt-6">
          <p className="py-8 text-center text-sm text-muted-foreground">
            스케줄 불러오는 중...
          </p>
        </CardContent>
      </Card>
    )
  }
  if (!data) return null

  const chunkMap = new Map<number, ChunkDetail>(
    data.chunks.map((c) => [c.job_id, c]),
  )
  const toggle = (id: number) =>
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  return (
    <Card className="mb-4">
      <CardContent className="pt-6">
        {/* 헤더 + 커버리지 */}
        <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold">주간 스케줄</h3>
            <p className="text-xs text-muted-foreground">
              crawl_jobs 기준 · 실측 소요 반영 · 거대지역 청크 포함
            </p>
          </div>
          <div className="flex items-center gap-2">
            {data.coverage.map((c) => (
              <span
                key={c.sido}
                title={`${c.sido_name} 시군구 ${c.chunk_codes}개 청크 분할 / DB ${c.db_codes}개`}
                className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs ${
                  c.ok
                    ? "border-jb-sys-success/30 text-jb-sys-success"
                    : "border-jb-sys-error/30 text-jb-sys-error"
                }`}
              >
                {c.ok ? (
                  <CheckCircle2 className="h-3 w-3" />
                ) : (
                  <AlertTriangle className="h-3 w-3" />
                )}
                {c.sido_name} {c.chunk_codes}/{c.db_codes}
              </span>
            ))}
          </div>
        </div>

        {/* 주간 표 */}
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-24">요일·시각</TableHead>
              <TableHead>잡</TableHead>
              <TableHead className="w-28">대상</TableHead>
              <TableHead className="w-16 text-right">단지</TableHead>
              <TableHead className="w-20 text-right">소요</TableHead>
              <TableHead className="w-28">종료</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.schedule.map((s, i) => {
              const prev = data.schedule[i - 1]
              const dayStart = !prev || prev.dow !== s.dow
              const chunk = chunkMap.get(s.job_id)
              const isOpen = expanded.has(s.job_id)
              const estimated = s.dur_source.startsWith("추정")
              return (
                <Fragment key={s.job_id}>
                  <TableRow className={dayStart ? "border-t-2 border-t-border" : ""}>
                    <TableCell className="font-medium tabular-nums">
                      {s.dow_name} {hhmm(s.hour, s.minute)}
                    </TableCell>
                    <TableCell>
                      {chunk ? (
                        <button
                          onClick={() => toggle(s.job_id)}
                          className="inline-flex items-center gap-1 rounded text-sm hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1"
                        >
                          {isOpen ? (
                            <ChevronDown className="h-3 w-3" />
                          ) : (
                            <ChevronRight className="h-3 w-3" />
                          )}
                          {s.name}
                          <Badge variant="secondary" className="ml-1 text-[10px]">
                            청크
                          </Badge>
                        </button>
                      ) : (
                        <span className="pl-4 text-sm">{s.name}</span>
                      )}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {s.summary}
                    </TableCell>
                    <TableCell className="text-right text-sm tabular-nums">
                      {s.complexes.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right text-sm tabular-nums">
                      {s.dur_hours.toFixed(1)}h
                      {estimated && (
                        <span className="ml-1 text-[10px] text-muted-foreground">추정</span>
                      )}
                    </TableCell>
                    <TableCell className="text-sm tabular-nums text-muted-foreground">
                      {s.end_dow_name} {hhmm(s.end_hour, s.end_minute)}
                      {s.crosses_day && (
                        <span className="ml-1 text-[10px] text-jb-sys-error">+1d</span>
                      )}
                    </TableCell>
                  </TableRow>
                  {chunk && isOpen && (
                    <TableRow className="bg-muted/20 hover:bg-muted/20">
                      <TableCell />
                      <TableCell colSpan={5} className="py-2">
                        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                          {chunk.codes.map((cc) => (
                            <span key={cc.region_code}>
                              <span className="tabular-nums">{cc.region_code}</span>{" "}
                              {cc.name}{" "}
                              <span className="text-foreground tabular-nums">
                                {cc.complexes.toLocaleString()}
                              </span>
                            </span>
                          ))}
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </Fragment>
              )
            })}
          </TableBody>
        </Table>

        {/* 겹침 — 큐 가드로 손실 없음, 직렬화만 발생 */}
        {data.clashes.length > 0 && (
          <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2.5 dark:border-amber-900/40 dark:bg-amber-950/20">
            <div className="flex items-center gap-1.5 text-xs font-medium text-amber-700 dark:text-amber-400">
              <AlertTriangle className="h-3.5 w-3.5" />
              겹침 {data.clashes.length}건 (소요 기준 다음 잡 시작과 충돌)
            </div>
            <p className="mt-1 text-[11px] text-muted-foreground">
              큐-인지 가드로 데이터 손실은 없고 처리만 직렬화됩니다. 슬랙이 거의 없다는 신호.
            </p>
            <ul className="mt-1.5 space-y-0.5 text-xs text-muted-foreground">
              {data.clashes.map((c) => (
                <li key={c.job_id}>
                  <span className="text-foreground">{c.name}</span>(
                  {c.dur_hours.toFixed(1)}h) → {c.next_name} 시작과 ~
                  {c.overlap_hours.toFixed(1)}h 겹침
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* PAUSED 안내 */}
        {data.paused.length > 0 && (
          <p className="mt-3 text-[11px] text-muted-foreground">
            청크로 대체된 PAUSED 잡 {data.paused.length}개 (서울·경기 monolith 등) — 스케줄 미동작.
          </p>
        )}
      </CardContent>
    </Card>
  )
}
