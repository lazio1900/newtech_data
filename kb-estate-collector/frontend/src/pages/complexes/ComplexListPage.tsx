import { useState, useMemo } from "react"
import { Link, useNavigate } from "react-router-dom"
import { Plus, Search, MapPin, Play, Loader2 } from "lucide-react"
import { Checkbox } from "@/components/ui/checkbox"
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
  useCollectComplex,
  useBatchCollectComplexes,
  useComplexLastRuns,
} from "@/hooks/useComplexes"
import {
  PRIORITY_LABELS,
  RUN_STATUS_LABELS,
  SIDO_REGIONS,
  COMMON_REGIONS,
} from "@/lib/constants"
import { formatRelativeTime } from "@/lib/format"
import { toast } from "sonner"

interface DiscoverResult {
  region_code: string
  total_found: number
  new_registered: number
  already_exists: number
}

export default function ComplexListPage() {
  const navigate = useNavigate()
  const [search, setSearch] = useState("")
  const [selectedSido, setSelectedSido] = useState<string | null>(null)
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [showDiscover, setShowDiscover] = useState(false)
  const [discoverResult, setDiscoverResult] = useState<DiscoverResult | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())

  const { data: complexes, isLoading } = useComplexes({ limit: 1000 })
  const createMutation = useCreateComplex()
  const discoverMutation = useDiscoverRegion()
  const collectMutation = useCollectComplex()
  const batchCollectMutation = useBatchCollectComplexes()
  const { data: lastRuns } = useComplexLastRuns()

  // 시/도별, 시/군/구별 단지 수 계산
  const { sidoCounts, regionCounts } = useMemo(() => {
    const sido: Record<string, number> = {}
    const region: Record<string, number> = {}
    for (const c of complexes ?? []) {
      if (c.region_code) {
        const sidoKey = c.region_code.slice(0, 2)
        sido[sidoKey] = (sido[sidoKey] || 0) + 1
        const regionKey = c.region_code.slice(0, 5)
        region[regionKey] = (region[regionKey] || 0) + 1
      }
    }
    return { sidoCounts: sido, regionCounts: region }
  }, [complexes])

  // 선택된 시/도에 해당하는 시/군/구 목록
  const filteredRegions = useMemo(() => {
    if (!selectedSido) return {}
    const result: Record<string, string> = {}
    for (const [code, name] of Object.entries(COMMON_REGIONS)) {
      if (code.startsWith(selectedSido)) {
        result[code] = name
      }
    }
    return result
  }, [selectedSido])

  // 필터링된 단지 목록
  const filtered = useMemo(() => {
    if (!complexes) return []
    let list = complexes

    if (selectedRegion) {
      list = list.filter(
        (c) => c.region_code && c.region_code.startsWith(selectedRegion),
      )
    } else if (selectedSido) {
      list = list.filter(
        (c) => c.region_code && c.region_code.startsWith(selectedSido),
      )
    }

    if (search.trim()) {
      const q = search.trim().toLowerCase()
      list = list.filter(
        (c) =>
          c.name.toLowerCase().includes(q) ||
          c.address.toLowerCase().includes(q) ||
          c.kb_complex_id?.includes(q) ||
          c.region_code?.includes(q),
      )
    }

    return list
  }, [complexes, selectedSido, selectedRegion, search])

  const allSelected =
    filtered.length > 0 && filtered.every((c) => selectedIds.has(c.id))

  const toggleAll = () => {
    if (allSelected) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(filtered.map((c) => c.id)))
    }
  }

  const toggleOne = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

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

      {/* 검색 + 지역 필터 */}
      <Card className="mb-4">
        <CardContent className="pt-5 pb-4 space-y-3">
          {/* 검색 입력 */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="단지명, 주소, 지역코드로 검색..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>

          {/* 시/도 선택 */}
          <div>
            <div className="mb-1.5 flex items-center gap-1.5 text-xs text-muted-foreground">
              <MapPin className="h-3 w-3" />
              <span>시/도</span>
              {(selectedSido || selectedRegion) && (
                <button
                  onClick={() => {
                    setSelectedSido(null)
                    setSelectedRegion(null)
                  }}
                  className="ml-1 rounded px-1.5 py-0.5 text-xs hover:bg-accent"
                >
                  전체 보기
                </button>
              )}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(SIDO_REGIONS).map(([code, name]) => {
                const count = sidoCounts[code] || 0
                const isActive = selectedSido === code
                return (
                  <button
                    key={code}
                    onClick={() => {
                      setSelectedSido(isActive ? null : code)
                      setSelectedRegion(null)
                    }}
                    className={`rounded-md border px-2.5 py-1 text-xs transition-colors ${
                      isActive
                        ? "border-primary bg-primary text-primary-foreground"
                        : count > 0
                          ? "hover:bg-accent"
                          : "text-muted-foreground/50 opacity-60"
                    }`}
                  >
                    {name}
                    {count > 0 && (
                      <span
                        className={`ml-1 ${
                          isActive
                            ? "text-primary-foreground/70"
                            : "text-muted-foreground"
                        }`}
                      >
                        {count}
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          </div>

          {/* 시/군/구 선택 (시/도 선택 후) */}
          {selectedSido && Object.keys(filteredRegions).length > 0 && (
            <div>
              <div className="mb-1.5 text-xs text-muted-foreground">
                시/군/구
              </div>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(filteredRegions).map(([code, name]) => {
                  const count = regionCounts[code] || 0
                  const isActive = selectedRegion === code
                  return (
                    <button
                      key={code}
                      onClick={() =>
                        setSelectedRegion(isActive ? null : code)
                      }
                      className={`rounded-md border px-2.5 py-1 text-xs transition-colors ${
                        isActive
                          ? "border-primary bg-primary text-primary-foreground"
                          : count > 0
                            ? "hover:bg-accent"
                            : "text-muted-foreground/50 opacity-60"
                      }`}
                    >
                      {name}
                      {count > 0 && (
                        <span
                          className={`ml-1 ${
                            isActive
                              ? "text-primary-foreground/70"
                              : "text-muted-foreground"
                          }`}
                        >
                          {count}
                        </span>
                      )}
                    </button>
                  )
                })}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 단지 테이블 */}
      <Card>
        <CardContent className="pt-6">
          {isLoading ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              로딩중...
            </p>
          ) : filtered.length === 0 ? (
            <EmptyState message="해당하는 단지가 없습니다" />
          ) : (
            <>
              <div className="mb-3 flex items-center justify-between">
                <span className="text-xs text-muted-foreground">
                  {filtered.length}개 단지
                  {selectedIds.size > 0 && (
                    <span className="ml-1.5 font-medium text-primary">
                      ({selectedIds.size}개 선택)
                    </span>
                  )}
                </span>
                {selectedIds.size > 0 && (
                  <Button
                    size="sm"
                    onClick={() => {
                      const ids = Array.from(selectedIds)
                      batchCollectMutation.mutate(ids, {
                        onSuccess: (res) => {
                          toast.success(
                            `${res.count}개 단지 수집이 시작되었습니다`,
                          )
                          setSelectedIds(new Set())
                          navigate(`/runs/${res.run_id}`)
                        },
                        onError: () =>
                          toast.error("수집 시작에 실패했습니다"),
                      })
                    }}
                    disabled={batchCollectMutation.isPending}
                  >
                    {batchCollectMutation.isPending ? (
                      <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                    ) : (
                      <Play className="mr-1.5 h-4 w-4" />
                    )}
                    크롤링 실행 ({selectedIds.size})
                  </Button>
                )}
              </div>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10">
                      <Checkbox
                        checked={allSelected}
                        onCheckedChange={toggleAll}
                      />
                    </TableHead>
                    <TableHead>이름</TableHead>
                    <TableHead>주소</TableHead>
                    <TableHead>우선순위</TableHead>
                    <TableHead>면적</TableHead>
                    <TableHead>마지막 수집</TableHead>
                    <TableHead className="text-right">수집</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.map((c) => {
                    const lastRun = lastRuns?.[c.id]
                    return (
                      <TableRow key={c.id} className="cursor-pointer hover:bg-accent">
                        <TableCell>
                          <Checkbox
                            checked={selectedIds.has(c.id)}
                            onCheckedChange={() => toggleOne(c.id)}
                          />
                        </TableCell>
                        <TableCell>
                          <Link
                            to={`/complexes/${c.id}`}
                            className="font-medium text-primary hover:underline"
                          >
                            {c.name}
                          </Link>
                        </TableCell>
                        <TableCell className="max-w-[240px] truncate text-sm text-muted-foreground">
                          {c.address}
                        </TableCell>
                        <TableCell>
                          <StatusBadge
                            status={c.priority}
                            label={PRIORITY_LABELS[c.priority]}
                          />
                        </TableCell>
                        <TableCell className="text-sm">
                          {c.areas?.length ?? 0}개
                        </TableCell>
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
                              <span className="text-xs text-muted-foreground">
                                {formatRelativeTime(lastRun.started_at)}
                              </span>
                            </div>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation()
                              collectMutation.mutate(c.id, {
                                onSuccess: (res) => {
                                  toast.success(
                                    `${c.name} 수집이 시작되었습니다`,
                                  )
                                  navigate(`/runs/${res.run_id}`)
                                },
                                onError: () =>
                                  toast.error("수집 시작에 실패했습니다"),
                              })
                            }}
                            disabled={collectMutation.isPending}
                          >
                            <Play className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            </>
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
                  <div className="text-2xl font-bold">
                    {discoverResult.total_found}
                  </div>
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
                        `${res.total_found}개 단지 발견, ${res.new_registered}개 신규 등록`,
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
