import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
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

interface ScheduleDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  sidoName: string
  currentCron: string | null
  loading?: boolean
  onSave: (cron: string | null) => void
}

const DAYS = [
  { value: "1", label: "월요일" },
  { value: "2", label: "화요일" },
  { value: "3", label: "수요일" },
  { value: "4", label: "목요일" },
  { value: "5", label: "금요일" },
  { value: "6", label: "토요일" },
  { value: "0", label: "일요일" },
]

const HOURS = Array.from({ length: 24 }, (_, i) => ({
  value: String(i),
  label: `${String(i).padStart(2, "0")}시`,
}))

export type Interval = "daily" | "weekly" | "biweekly" | "monthly"

function parseCron(cron: string | null): {
  interval: Interval
  day: string
  hour: string
  minute: string
} {
  if (!cron) return { interval: "weekly", day: "6", hour: "10", minute: "0" }

  const parts = cron.split(" ")
  if (parts.length !== 5) return { interval: "weekly", day: "6", hour: "10", minute: "0" }

  const [minuteStr, hourStr, dayOfMonth, , dayOfWeek] = parts
  const hour = hourStr || "10"
  const minute = minuteStr || "0"

  if (dayOfMonth !== "*" && !dayOfMonth.includes("-")) {
    return { interval: "monthly", day: "6", hour, minute }
  }
  if (dayOfWeek === "*") {
    return { interval: "daily", day: "6", hour, minute }
  }
  if (dayOfMonth.includes("-") || cron.includes("*/2")) {
    return { interval: "biweekly", day: dayOfWeek || "6", hour, minute }
  }
  return { interval: "weekly", day: dayOfWeek || "6", hour, minute }
}

export function buildCron(interval: Interval, day: string, hour: string, minute = "0"): string {
  switch (interval) {
    case "daily":
      return `${minute} ${hour} * * *`
    case "weekly":
      return `${minute} ${hour} * * ${day}`
    case "biweekly":
      return `${minute} ${hour} 1-7,15-21 * ${day}`
    case "monthly":
      return `${minute} ${hour} 1 * *`
  }
}

function describeSchedule(interval: Interval, day: string, hour: string, minute = "0"): string {
  const dayLabel = DAYS.find((d) => d.value === day)?.label || ""
  const hourLabel = `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`

  switch (interval) {
    case "daily":
      return `매일 ${hourLabel}`
    case "weekly":
      return `매주 ${dayLabel} ${hourLabel}`
    case "biweekly":
      return `격주 ${dayLabel} ${hourLabel}`
    case "monthly":
      return `매월 1일 ${hourLabel}`
  }
}

export default function ScheduleDialog({
  open,
  onOpenChange,
  sidoName,
  currentCron,
  loading,
  onSave,
}: ScheduleDialogProps) {
  const parsed = parseCron(currentCron)
  const [interval, setInterval] = useState<Interval>(parsed.interval)
  const [day, setDay] = useState(parsed.day)
  const [hour, setHour] = useState(parsed.hour)

  useEffect(() => {
    if (open) {
      const p = parseCron(currentCron)
      setInterval(p.interval)
      setDay(p.day)
      setHour(p.hour)
    }
  }, [open, currentCron])

  const preview = describeSchedule(interval, day, hour)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>{sidoName} 스케줄 설정</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* 주기 */}
          <div>
            <label className="mb-1.5 block text-sm font-medium">수집 주기</label>
            <Select
              value={interval}
              onValueChange={(v) => setInterval(v as Interval)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="daily">매일</SelectItem>
                <SelectItem value="weekly">매주</SelectItem>
                <SelectItem value="biweekly">격주 (2주)</SelectItem>
                <SelectItem value="monthly">매월</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* 요일 (주간/격주일 때만) */}
          {(interval === "weekly" || interval === "biweekly") && (
            <div>
              <label className="mb-1.5 block text-sm font-medium">요일</label>
              <Select value={day} onValueChange={setDay}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DAYS.map((d) => (
                    <SelectItem key={d.value} value={d.value}>
                      {d.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* 시간 */}
          <div>
            <label className="mb-1.5 block text-sm font-medium">시간</label>
            <Select value={hour} onValueChange={setHour}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {HOURS.map((h) => (
                  <SelectItem key={h.value} value={h.value}>
                    {h.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* 미리보기 */}
          <div className="rounded-md border bg-muted/30 px-3 py-2">
            <span className="text-xs text-muted-foreground">스케줄 미리보기</span>
            <p className="mt-0.5 text-sm font-medium">{preview}</p>
          </div>
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          {currentCron && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onSave(null)}
              disabled={loading}
              className="mr-auto"
            >
              스케줄 해제
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => onOpenChange(false)}
          >
            취소
          </Button>
          <Button
            size="sm"
            onClick={() => onSave(buildCron(interval, day, hour))}
            disabled={loading}
          >
            {loading ? "저장중..." : "저장"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** 크론 표현식을 사람이 읽을 수 있는 텍스트로 변환 */
export function cronToLabel(cron: string | null): string {
  if (!cron) return "-"
  const p = parseCron(cron)
  return describeSchedule(p.interval, p.day, p.hour, p.minute)
}
