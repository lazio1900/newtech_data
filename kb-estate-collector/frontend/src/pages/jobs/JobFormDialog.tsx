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
import type { JobCreate, JobType } from "@/types/job"
import { JOB_TYPE_LABELS } from "@/lib/constants"

interface JobFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (data: JobCreate) => void
  loading?: boolean
}

export default function JobFormDialog({
  open,
  onOpenChange,
  onSubmit,
  loading,
}: JobFormDialogProps) {
  const [form, setForm] = useState<JobCreate>({
    name: "",
    job_type: "KB_PRICE",
    description: "",
    cron_schedule: "",
    max_concurrency: 5,
    rate_limit_per_minute: 60,
  })

  const handleSubmit = () => {
    if (!form.name) return
    onSubmit(form)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>수집 작업 생성</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium">작업명 *</label>
            <Input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="강남구 시세 수집"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">유형</label>
            <Select
              value={form.job_type}
              onValueChange={(v) => setForm({ ...form, job_type: v as JobType })}
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
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">설명</label>
            <Input
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="선택사항"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Cron 스케줄</label>
            <Input
              value={form.cron_schedule}
              onChange={(e) => setForm({ ...form, cron_schedule: e.target.value })}
              placeholder="0 9 * * * (매일 09시)"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium">동시실행 수</label>
              <Input
                type="number"
                value={form.max_concurrency}
                onChange={(e) =>
                  setForm({ ...form, max_concurrency: Number(e.target.value) })
                }
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">분당 제한</label>
              <Input
                type="number"
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
          <Button onClick={handleSubmit} disabled={loading || !form.name}>
            {loading ? "생성중..." : "생성"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
