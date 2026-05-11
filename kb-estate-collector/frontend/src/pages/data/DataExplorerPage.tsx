import { useState, useMemo, useEffect } from "react"
import { Search, MapPin, Building2, X } from "lucide-react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Input } from "@/components/ui/input"
import { Card, CardContent } from "@/components/ui/card"
import PageHeader from "@/components/layout/PageHeader"
import PriceTab from "./PriceTab"
import TransactionTab from "./TransactionTab"
import ListingTab from "./ListingTab"
import { useComplexes, useRegionCounts, useComplex } from "@/hooks/useComplexes"
import { SIDO_REGIONS, COMMON_REGIONS } from "@/lib/constants"

export default function DataExplorerPage() {
  const [searchInput, setSearchInput] = useState("")
  const [debouncedSearch, setDebouncedSearch] = useState("")
  const [selectedSido, setSelectedSido] = useState<string | null>(null)
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null)
  const [selectedComplexId, setSelectedComplexId] = useState<number | undefined>()

  // 검색어 디바운스
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchInput), 300)
    return () => clearTimeout(timer)
  }, [searchInput])

  // 선택된 단지 상세
  const { data: selectedComplex } = useComplex(selectedComplexId ?? 0)

  // 시/도별 단지 수
  const { data: counts } = useRegionCounts()
  const sidoCounts = counts?.sido_counts ?? {}
  const regionCnts = counts?.region_counts ?? {}

  // 선택된 시/도의 시/군/구 목록
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

  // 단지 목록 (지역 또는 검색이 있을 때만 쿼리)
  const regionCode = selectedRegion || selectedSido || undefined
  const showList = !!(regionCode || debouncedSearch.trim())
  const { data: complexData } = useComplexes(
    showList
      ? {
          skip: 0,
          limit: 50,
          search: debouncedSearch || undefined,
          region_code: regionCode,
        }
      : { skip: 0, limit: 0 },
  )

  const complexList = showList ? (complexData?.items ?? []) : []
  const complexTotal = showList ? (complexData?.total ?? 0) : 0

  return (
    <div>
      <PageHeader title="데이터 탐색" description="수집된 데이터 조회 및 내보내기" />

      {/* 선택된 단지 표시 */}
      {selectedComplex && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-primary/30 bg-primary/5 px-4 py-2.5">
          <Building2 className="h-4 w-4 text-primary" />
          <span className="text-sm font-medium">{selectedComplex.name}</span>
          <span className="text-xs text-muted-foreground">
            {selectedComplex.address}
          </span>
          {selectedComplex.areas.length > 0 && (
            <span className="text-xs text-muted-foreground">
              · 면적 {selectedComplex.areas.length}개
            </span>
          )}
          <button
            onClick={() => setSelectedComplexId(undefined)}
            className="ml-auto rounded p-0.5 text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* 지역 선택 + 검색 */}
      {!selectedComplexId && (
        <Card className="mb-4">
          <CardContent className="pt-5 pb-4 space-y-3">
            {/* 검색 입력 */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="단지명 또는 주소로 검색..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
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
                {Object.entries(SIDO_REGIONS)
                  .sort((a, b) => a[1].localeCompare(b[1], "ko"))
                  .map(([code, name]) => {
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
                  {Object.entries(filteredRegions)
                    .sort((a, b) => a[1].localeCompare(b[1], "ko"))
                    .map(([code, name]) => {
                    const count = regionCnts[code] || 0
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

            {/* 단지 목록 */}
            {showList && (
              <div className="max-h-64 overflow-y-auto rounded-md border">
                {complexList.length === 0 ? (
                  <p className="py-6 text-center text-sm text-muted-foreground">
                    해당하는 단지가 없습니다
                  </p>
                ) : (
                  <>
                    <div className="divide-y">
                      {complexList.map((c) => (
                        <button
                          key={c.id}
                          onClick={() => {
                            setSelectedComplexId(c.id)
                            setSearchInput("")
                            setSelectedSido(null)
                            setSelectedRegion(null)
                          }}
                          className="flex w-full items-center gap-3 px-3 py-2 text-left text-sm hover:bg-accent transition-colors"
                        >
                          <div className="min-w-0 flex-1">
                            <div className="font-medium truncate">{c.name}</div>
                            <div className="text-xs text-muted-foreground truncate">
                              {c.address}
                            </div>
                          </div>
                          {c.areas.length > 0 && (
                            <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
                              {c.areas.length}면적
                            </span>
                          )}
                        </button>
                      ))}
                    </div>
                    {complexTotal > complexList.length && (
                      <p className="border-t px-3 py-2 text-center text-xs text-muted-foreground">
                        {complexTotal}개 중 {complexList.length}개 표시 · 검색어를 더 구체적으로 입력하세요
                      </p>
                    )}
                  </>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* 데이터 탭 */}
      <Tabs defaultValue="prices">
        <TabsList>
          <TabsTrigger value="prices">KB 시세</TabsTrigger>
          <TabsTrigger value="transactions">실거래가</TabsTrigger>
          <TabsTrigger value="listings">매물</TabsTrigger>
        </TabsList>

        <TabsContent value="prices">
          <PriceTab complexId={selectedComplexId} />
        </TabsContent>

        <TabsContent value="transactions">
          <TransactionTab complexId={selectedComplexId} />
        </TabsContent>

        <TabsContent value="listings">
          <ListingTab complexId={selectedComplexId} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
