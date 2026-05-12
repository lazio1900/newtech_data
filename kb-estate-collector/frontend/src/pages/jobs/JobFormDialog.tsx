import { useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Play } from "lucide-react"
import type { JobCreate, JobType } from "@/types/job"
import {
  JOB_TYPE_LABELS,
  JOB_TYPE_DESCRIPTIONS,
  CRON_PRESETS,
  COMMON_REGIONS,
} from "@/lib/constants"

interface JobFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (data: JobCreate) => void
  onCreateAndRun?: (data: JobCreate) => void
  loading?: boolean
  runLoading?: boolean
}

export default function JobFormDialog({
  open,
  onOpenChange,
  onSubmit,
  onCreateAndRun,
  loading,
  runLoading,
}: JobFormDialogProps) {
  const [form, setForm] = useState<JobCreate>({
    name: "",
    job_type: "kb_price",
    description: "",
    cron_schedule: "",
    max_concurrency: 5,
    rate_limit_per_minute: 60,
  })
  const [regionCode, setRegionCode] = useState("")

  const isRegionAll = form.job_type === "region_all"

  const buildPayload = (): JobCreate => {
    const payload: JobCreate = {
      ...form,
      description: form.description || undefined,
      cron_schedule: form.cron_schedule || undefined,
    }
    if (isRegionAll && regionCode) {
      payload.target_config = JSON.stringify({ region_code: regionCode })
      if (!payload.name) {
        const regionName = COMMON_REGIONS[regionCode]
        payload.name = regionName
          ? `${regionName}(${regionCode}) 전체 수집`
          : `${regionCode} 지역 전체 수집`
      }
    }
    return payload
  }

  const canSubmit = isRegionAll ? !!regionCode : !!form.name

  const handleSubmit = () => {
    if (!canSubmit) return
    onSubmit(buildPayload())
  }

  const handleCreateAndRun = () => {
    if (!canSubmit || !onCreateAndRun) return
    onCreateAndRun(buildPayload())
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>수집 작업 생성</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium">수집 유형 *</label>
            <Select
              value={form.job_type}
              onValueChange={(v) => {
                setForm({ ...form, job_type: v as JobType })
                setRegionCode("")
              }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(JOB_TYPE_LABELS).map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="mt-1 text-xs text-muted-foreground">
              {JOB_TYPE_DESCRIPTIONS[form.job_type]}
            </p>
          </div>

          {isRegionAll && (
            <div>
              <label className="mb-1 block text-sm font-medium">지역코드 *</label>
              <Input
                value={regionCode}
                onChange={(e) => setRegionCode(e.target.value)}
                placeholder="예) 11680 (강남구)"
              />
              <div className="mt-1.5 flex flex-wrap gap-1">
                {Object.entries(COMMON_REGIONS)
                  .sort((a, b) => a[1].localeCompare(b[1], "ko"))
                  .map(([code, name]) => (
                  <button
                    key={code}
                    type="button"
                    className={`rounded-md border px-2 py-0.5 text-xs transition-colors hover:bg-accent hover:text-foreground ${
                      regionCode === code
                        ? "bg-accent text-foreground"
                        : "text-muted-foreground"
                    }`}
                    onClick={() => setRegionCode(code)}
                  >
                    {name}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div>
            <label className="mb-1 block text-sm font-medium">
              작업명 {isRegionAll ? (
                <span className="text-xs text-muted-foreground">(선택 - 자동생성)</span>
              ) : " *"}
            </label>
            <Input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder={
                isRegionAll
                  ? "비워두면 지역명으로 자동 생성"
                  : "예) 서초구 아파트 수집"
              }
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">
              설명 <span className="text-xs text-muted-foreground">(선택)</span>
            </label>
            <Input
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="예) 서초구 아파트 일일 수집"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">
              Cron 스케줄 <span className="text-xs text-muted-foreground">(선택)</span>
            </label>
            <Input
              value={form.cron_schedule}
              onChange={(e) => setForm({ ...form, cron_schedule: e.target.value })}
              placeholder="비워두면 수동 실행만 가능"
            />
            <div className="mt-1.5 flex flex-wrap gap-1">
              {CRON_PRESETS.map((preset) => (
                <button
                  key={preset.value}
                  type="button"
                  className="rounded-md border px-2 py-0.5 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                  onClick={() => setForm({ ...form, cron_schedule: preset.value })}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium">동시실행 수</label>
              <Input
                type="number"
                min={1}
                max={20}
                value={form.max_concurrency}
                onChange={(e) =>
                  setForm({ ...form, max_concurrency: Number(e.target.value) })
                }
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">분당 요청 제한</label>
              <Input
                type="number"
                min={1}
                max={300}
                value={form.rate_limit_per_minute}
                onChange={(e) =>
                  setForm({
                    ...form,
                    rate_limit_per_minute: Number(e.target.value),
                  })
                }
              />
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            취소
          </Button>
          <Button onClick={handleSubmit} disabled={loading || !canSubmit}>
            {loading ? "생성중..." : "생성"}
          </Button>
          {onCreateAndRun && (
            <Button
              onClick={handleCreateAndRun}
              disabled={runLoading || !canSubmit}
              variant="default"
              className="bg-jb-primary-main hover:bg-jb-primary-main/90"
            >
              <Play className="mr-1 h-3.5 w-3.5" />
              {runLoading ? "실행중..." : "생성 + 즉시 실행"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
