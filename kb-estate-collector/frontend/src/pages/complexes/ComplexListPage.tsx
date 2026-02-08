import { useState } from "react"
import { Link } from "react-router-dom"
import { Plus, Search, MapPin } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
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
import ComplexFormDialog from "./ComplexFormDialog"
import {
  useComplexes,
  useCreateComplex,
  useDiscoverRegion,
} from "@/hooks/useComplexes"
import { PRIORITY_LABELS } from "@/lib/constants"
import { toast } from "sonner"

interface DiscoverResult {
  region_code: string
  total_found: number
  new_registered: number
  already_exists: number
}

export default function ComplexListPage() {
  const [search, setSearch] = useState("")
  const [showCreate, setShowCreate] = useState(false)
  const [showDiscover, setShowDiscover] = useState(false)
  const [discoverResult, setDiscoverResult] = useState<DiscoverResult | null>(null)

  const { data: complexes, isLoading } = useComplexes({ limit: 500 })
  const createMutation = useCreateComplex()
  const discoverMutation = useDiscoverRegion()

  const filtered = complexes?.filter(
    (c) =>
      c.name.includes(search) ||
      c.address.includes(search) ||
      (c.region_code && c.region_code.includes(search))
  )

  return (
    <div>
      <PageHeader
        title="단지 관리"
        description="아파트 단지 목록 관리 및 지역 발견"
        actions={
          <>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowDiscover(true)}
            >
              <MapPin className="mr-1.5 h-4 w-4" />
              지역 발견
            </Button>
            <Button size="sm" onClick={() => setShowCreate(true)}>
              <Plus className="mr-1.5 h-4 w-4" />
              단지 등록
            </Button>
          </>
        }
      />

      <Card>
        <CardContent className="pt-6">
          <div className="mb-4 flex items-center gap-2">
            <Search className="h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="이름, 주소, 지역코드로 검색..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="max-w-sm"
            />
          </div>

          {isLoading ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              로딩중...
            </p>
          ) : !filtered || filtered.length === 0 ? (
            <EmptyState message="등록된 단지가 없습니다" />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>이름</TableHead>
                  <TableHead>주소</TableHead>
                  <TableHead>지역코드</TableHead>
                  <TableHead>우선순위</TableHead>
                  <TableHead>상태</TableHead>
                  <TableHead>면적</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((c) => (
                  <TableRow key={c.id} className="cursor-pointer hover:bg-accent">
                    <TableCell>
                      <Link
                        to={`/complexes/${c.id}`}
                        className="font-medium text-primary hover:underline"
                      >
                        {c.name}
                      </Link>
                    </TableCell>
                    <TableCell className="max-w-[200px] truncate text-sm text-muted-foreground">
                      {c.address}
                    </TableCell>
                    <TableCell className="text-sm">{c.region_code || "-"}</TableCell>
                    <TableCell>
                      <StatusBadge
                        status={c.priority}
                        label={PRIORITY_LABELS[c.priority]}
                      />
                    </TableCell>
                    <TableCell>
                      <StatusBadge
                        status={c.is_active ? "active" : "disabled"}
                        label={c.is_active ? "활성" : "비활성"}
                      />
                    </TableCell>
                    <TableCell className="text-sm">
                      {c.areas?.length ?? 0}개
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <ComplexFormDialog
        open={showCreate}
        onOpenChange={setShowCreate}
        loading={createMutation.isPending}
        onSubmit={(data) => {
          createMutation.mutate(data, {
            onSuccess: () => {
              toast.success("단지가 등록되었습니다")
              setShowCreate(false)
            },
            onError: () => toast.error("단지 등록에 실패했습니다"),
          })
        }}
      />

      <Dialog
        open={showDiscover}
        onOpenChange={(open) => {
          setShowDiscover(open)
          if (!open) setDiscoverResult(null)
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>지역 기반 단지 발견</DialogTitle>
          </DialogHeader>

          {discoverResult ? (
            <div className="space-y-3">
              <p className="text-sm font-medium">
                {discoverResult.region_code} 지역 발견 완료
              </p>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="rounded-lg border p-3">
                  <div className="text-2xl font-bold">{discoverResult.total_found}</div>
                  <div className="text-xs text-muted-foreground">총 발견</div>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="text-2xl font-bold text-blue-600">
                    {discoverResult.new_registered}
                  </div>
                  <div className="text-xs text-muted-foreground">신규 등록</div>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="text-2xl font-bold text-gray-400">
                    {discoverResult.already_exists}
                  </div>
                  <div className="text-xs text-muted-foreground">이미 등록</div>
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setDiscoverResult(null)}
                >
                  다른 지역 발견
                </Button>
                <Button
                  size="sm"
                  onClick={() => {
                    setShowDiscover(false)
                    setDiscoverResult(null)
                  }}
                >
                  닫기
                </Button>
              </div>
            </div>
          ) : (
            <>
              <p className="text-sm text-muted-foreground">
                지역코드를 입력하면 KB부동산에서 해당 지역의 아파트 단지를
                자동으로 발견하고 등록합니다.
              </p>
              <RegionCodeInput
                loading={discoverMutation.isPending}
                buttonLabel="발견 시작"
                onSubmit={(code) => {
                  discoverMutation.mutate(code, {
                    onSuccess: (res) => {
                      setDiscoverResult(res)
                      toast.success(
                        `${res.total_found}개 단지 발견, ${res.new_registered}개 신규 등록`
                      )
                    },
                    onError: () => toast.error("지역 발견에 실패했습니다"),
                  })
                }}
              />
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
