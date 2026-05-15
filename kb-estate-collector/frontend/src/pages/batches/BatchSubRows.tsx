import { useState } from "react"
import { Link } from "react-router-dom"
import { ChevronRight, ChevronDown, Loader2, Play, Settings } from "lucide-react"
import { Button } from "@/components/ui/button"
import { TableCell, TableRow } from "@/components/ui/table"
import StatusBadge from "@/components/shared/StatusBadge"
import { RUN_STATUS_LABELS, COMMON_REGIONS } from "@/lib/constants"
import { formatRelativeTime, formatDuration } from "@/lib/format"
import { cronToLabel } from "./ScheduleDialog"
import { useSigunguBatches, useDongBatches } from "@/hooks/useBatches"
import { batchesApi } from "@/api/batches"
import { toast } from "sonner"
import { useQueryClient } from "@tanstack/react-query"
import type { SigunguBatch, DongBatch } from "@/types/batch"

const COLSPAN = 8

interface SigunguSubRowsProps {
  sidoCode: string
  onScheduleClick: (scope: "sigungu" | "dong", code: string, name: string, currentCron: string | null) => void
}

export function SigunguSubRows({ sidoCode, onScheduleClick }: SigunguSubRowsProps) {
  const { data, isLoading } = useSigunguBatches(sidoCode)
  const [expandedRegion, setExpandedRegion] = useState<string | null>(null)
  const [running, setRunning] = useState<Set<string>>(new Set())
  const qc = useQueryClient()

  if (isLoading) {
    return (
      <TableRow>
        <TableCell colSpan={COLSPAN} className="bg-muted/30 text-center text-xs text-muted-foreground">
          시군구 로딩...
        </TableCell>
      </TableRow>
    )
  }
  if (!data || data.length === 0) {
    return (
      <TableRow>
        <TableCell colSpan={COLSPAN} className="bg-muted/30 text-center text-xs text-muted-foreground">
          시군구 데이터 없음
        </TableCell>
      </TableRow>
    )
  }

  const handleRun = (b: SigunguBatch) => {
    setRunning((prev) => new Set(prev).add(b.region_code))
    batchesApi.runScoped("sigungu", b.region_code).then(
      (res) => {
        toast.success(res.message)
        qc.invalidateQueries({ queryKey: ["batches"] })
      },
      () => toast.error("실행에 실패했습니다"),
    ).finally(() => {
      setRunning((prev) => { const n = new Set(prev); n.delete(b.region_code); return n })
    })
  }

  return (
    <>
      {data.map((b) => {
        const lastRun = b.last_runs[0]
        const name = COMMON_REGIONS[b.region_code] || b.sigungu_name || b.region_code
        const isRunning = running.has(b.region_code)
        const isExpanded = expandedRegion === b.region_code
        return (
          <>
            <TableRow key={b.region_code} className="bg-muted/20">
              <TableCell></TableCell>
              <TableCell colSpan={2} className="pl-10 font-medium text-sm">
                <button
                  onClick={() => setExpandedRegion(isExpanded ? null : b.region_code)}
                  className="inline-flex items-center gap-1 hover:text-primary"
                >
                  {isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                  {name}
                  <span className="ml-2 text-xs text-muted-foreground">{b.complex_count}</span>
                </button>
              </TableCell>
              <TableCell>
                <button
                  onClick={() => onScheduleClick("sigungu", b.region_code, name, b.cron_schedule)}
                  className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs hover:bg-accent"
                >
                  <Settings className="h-3 w-3 text-muted-foreground" />
                  <span className={b.cron_schedule ? "text-sm" : "text-sm text-muted-foreground"}>
                    {cronToLabel(b.cron_schedule)}
                  </span>
                </button>
              </TableCell>
              <TableCell className="text-sm">
                {lastRun ? (
                  <div className="flex items-center gap-1.5">
                    <StatusBadge status={lastRun.status} label={RUN_STATUS_LABELS[lastRun.status] || lastRun.status} />
                    <Link to={`/runs/${lastRun.id}`} className="text-xs text-muted-foreground hover:text-primary hover:underline">
                      {formatRelativeTime(lastRun.started_at)}
                    </Link>
                  </div>
                ) : <span className="text-muted-foreground">-</span>}
              </TableCell>
              <TableCell className="text-xs text-muted-foreground">
                {lastRun ? formatDuration(lastRun.started_at, lastRun.finished_at) : "-"}
              </TableCell>
              <TableCell className="text-sm">
                {lastRun ? (
                  <span>
                    <span className="text-jb-sys-success">{lastRun.success_count}</span>
                    {" / "}
                    <span className="text-jb-sys-error">{lastRun.failed_count}</span>
                    {" / "}
                    <span className="text-jb-text-low">{lastRun.skipped_count ?? 0}</span>
                  </span>
                ) : <span className="text-muted-foreground">-</span>}
              </TableCell>
              <TableCell className="text-right">
                <Button variant="ghost" size="sm" disabled={isRunning} onClick={() => handleRun(b)}>
                  {isRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                </Button>
              </TableCell>
            </TableRow>
            {isExpanded && <DongSubRows regionCode={b.region_code} onScheduleClick={onScheduleClick} />}
          </>
        )
      })}
    </>
  )
}

interface DongSubRowsProps {
  regionCode: string
  onScheduleClick: (scope: "sigungu" | "dong", code: string, name: string, currentCron: string | null) => void
}

function DongSubRows({ regionCode, onScheduleClick }: DongSubRowsProps) {
  const { data, isLoading } = useDongBatches(regionCode)
  const [running, setRunning] = useState<Set<string>>(new Set())
  const qc = useQueryClient()

  if (isLoading) {
    return (
      <TableRow>
        <TableCell colSpan={COLSPAN} className="bg-muted/40 pl-16 text-xs text-muted-foreground">
          동 로딩...
        </TableCell>
      </TableRow>
    )
  }
  if (!data || data.length === 0) {
    return (
      <TableRow>
        <TableCell colSpan={COLSPAN} className="bg-muted/40 pl-16 text-xs text-muted-foreground">
          동 데이터 없음 (좌표/dong_code 미보유)
        </TableCell>
      </TableRow>
    )
  }

  const handleRun = (b: DongBatch) => {
    setRunning((prev) => new Set(prev).add(b.dong_code))
    batchesApi.runScoped("dong", b.dong_code).then(
      (res) => {
        toast.success(res.message)
        qc.invalidateQueries({ queryKey: ["batches"] })
      },
      () => toast.error("실행에 실패했습니다"),
    ).finally(() => {
      setRunning((prev) => { const n = new Set(prev); n.delete(b.dong_code); return n })
    })
  }

  return (
    <>
      {data.map((b) => {
        const lastRun = b.last_runs[0]
        const isRunning = running.has(b.dong_code)
        return (
          <TableRow key={b.dong_code} className="bg-muted/40">
            <TableCell></TableCell>
            <TableCell colSpan={2} className="pl-16 text-sm">
              {b.dong_name}
              <span className="ml-2 text-xs text-muted-foreground">{b.complex_count}</span>
            </TableCell>
            <TableCell>
              <button
                onClick={() => onScheduleClick("dong", b.dong_code, b.dong_name, b.cron_schedule)}
                className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs hover:bg-accent"
              >
                <Settings className="h-3 w-3 text-muted-foreground" />
                <span className={b.cron_schedule ? "text-xs" : "text-xs text-muted-foreground"}>
                  {cronToLabel(b.cron_schedule)}
                </span>
              </button>
            </TableCell>
            <TableCell className="text-xs">
              {lastRun ? (
                <div className="flex items-center gap-1.5">
                  <StatusBadge status={lastRun.status} label={RUN_STATUS_LABELS[lastRun.status] || lastRun.status} />
                  <Link to={`/runs/${lastRun.id}`} className="text-xs text-muted-foreground hover:text-primary hover:underline">
                    {formatRelativeTime(lastRun.started_at)}
                  </Link>
                </div>
              ) : <span className="text-muted-foreground">-</span>}
            </TableCell>
            <TableCell className="text-xs text-muted-foreground">
              {lastRun ? formatDuration(lastRun.started_at, lastRun.finished_at) : "-"}
            </TableCell>
            <TableCell className="text-xs">
              {lastRun ? (
                <span>
                  <span className="text-jb-sys-success">{lastRun.success_count}</span>
                  {" / "}
                  <span className="text-jb-sys-error">{lastRun.failed_count}</span>
                  {" / "}
                  <span className="text-jb-text-low">{lastRun.skipped_count ?? 0}</span>
                </span>
              ) : <span className="text-muted-foreground">-</span>}
            </TableCell>
            <TableCell className="text-right">
              <Button variant="ghost" size="sm" disabled={isRunning} onClick={() => handleRun(b)}>
                {isRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              </Button>
            </TableCell>
          </TableRow>
        )
      })}
    </>
  )
}
