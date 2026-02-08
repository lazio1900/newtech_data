import { useState, useEffect } from "react"
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
import type { Complex, ComplexCreate, PriorityLevel } from "@/types/complex"

interface ComplexFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (data: ComplexCreate) => void
  initial?: Complex | null
  loading?: boolean
}

export default function ComplexFormDialog({
  open,
  onOpenChange,
  onSubmit,
  initial,
  loading,
}: ComplexFormDialogProps) {
  const [form, setForm] = useState<ComplexCreate>({
    name: "",
    address: "",
    region_code: "",
    kb_complex_id: "",
    priority: "NORMAL",
    is_active: true,
    collect_listings: false,
  })

  useEffect(() => {
    if (initial) {
      setForm({
        name: initial.name,
        address: initial.address,
        region_code: initial.region_code || "",
        kb_complex_id: initial.kb_complex_id || "",
        priority: initial.priority,
        is_active: initial.is_active,
        collect_listings: initial.collect_listings,
      })
    } else {
      setForm({
        name: "",
        address: "",
        region_code: "",
        kb_complex_id: "",
        priority: "NORMAL",
        is_active: true,
        collect_listings: false,
      })
    }
  }, [initial, open])

  const handleSubmit = () => {
    if (!form.name || !form.address) return
    onSubmit(form)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{initial ? "단지 수정" : "단지 등록"}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium">이름 *</label>
            <Input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="래미안역삼"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">주소 *</label>
            <Input
              value={form.address}
              onChange={(e) => setForm({ ...form, address: e.target.value })}
              placeholder="서울특별시 강남구 역삼동"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium">지역코드</label>
              <Input
                value={form.region_code}
                onChange={(e) => setForm({ ...form, region_code: e.target.value })}
                placeholder="11680"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">KB 단지 ID</label>
              <Input
                value={form.kb_complex_id}
                onChange={(e) =>
                  setForm({ ...form, kb_complex_id: e.target.value })
                }
                placeholder="12345"
              />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">우선순위</label>
            <Select
              value={form.priority}
              onValueChange={(v) =>
                setForm({ ...form, priority: v as PriorityLevel })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="HIGH">높음</SelectItem>
                <SelectItem value="NORMAL">보통</SelectItem>
                <SelectItem value="LOW">낮음</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex gap-6">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                className="rounded"
              />
              활성화
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.collect_listings}
                onChange={(e) =>
                  setForm({ ...form, collect_listings: e.target.checked })
                }
                className="rounded"
              />
              매물 수집
            </label>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            취소
          </Button>
          <Button onClick={handleSubmit} disabled={loading || !form.name || !form.address}>
            {loading ? "저장중..." : initial ? "수정" : "등록"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
