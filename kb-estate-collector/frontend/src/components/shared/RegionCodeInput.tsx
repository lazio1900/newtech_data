import { useState, useMemo } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { SIDO_REGIONS, COMMON_REGIONS } from "@/lib/constants"

interface RegionCodeInputProps {
  onSubmit: (regionCodes: string[]) => void
  loading?: boolean
  buttonLabel?: string
}

/** 시/도 코드에 해당하는 시/군/구 코드 목록 */
function getRegionCodes(sidoCode: string): string[] {
  return Object.keys(COMMON_REGIONS).filter((c) => c.startsWith(sidoCode))
}

/** 전체 시/군/구 코드 목록 */
function getAllRegionCodes(): string[] {
  return Object.keys(COMMON_REGIONS)
}

export default function RegionCodeInput({
  onSubmit,
  loading,
  buttonLabel = "실행",
}: RegionCodeInputProps) {
  const [code, setCode] = useState("")
  const [expandedSido, setExpandedSido] = useState<string | null>(null)
  const [selectedCodes, setSelectedCodes] = useState<Set<string>>(new Set())

  const filteredRegions = useMemo(() => {
    if (!expandedSido) return {}
    const result: Record<string, string> = {}
    for (const [c, name] of Object.entries(COMMON_REGIONS)) {
      if (c.startsWith(expandedSido)) {
        result[c] = name
      }
    }
    return result
  }, [expandedSido])

  /** 시/도의 선택 상태: all, partial, none */
  const getSidoStatus = (sidoCode: string) => {
    const codes = getRegionCodes(sidoCode)
    if (codes.length === 0) return "none"
    const selected = codes.filter((c) => selectedCodes.has(c)).length
    if (selected === codes.length) return "all"
    if (selected > 0) return "partial"
    return "none"
  }

  const allCodes = getAllRegionCodes()
  const isAllSelected =
    allCodes.length > 0 && allCodes.every((c) => selectedCodes.has(c))

  const toggleAll = () => {
    if (isAllSelected) {
      setSelectedCodes(new Set())
    } else {
      setSelectedCodes(new Set(allCodes))
    }
  }

  const toggleRegion = (regionCode: string) => {
    setSelectedCodes((prev) => {
      const next = new Set(prev)
      if (next.has(regionCode)) next.delete(regionCode)
      else next.add(regionCode)
      return next
    })
  }

  const expandedAllSelected =
    Object.keys(filteredRegions).length > 0 &&
    Object.keys(filteredRegions).every((c) => selectedCodes.has(c))

  const toggleExpandedAll = () => {
    setSelectedCodes((prev) => {
      const next = new Set(prev)
      const codes = Object.keys(filteredRegions)
      if (expandedAllSelected) {
        codes.forEach((c) => next.delete(c))
      } else {
        codes.forEach((c) => next.add(c))
      }
      return next
    })
  }

  return (
    <div className="space-y-3">
      {/* 직접 입력 */}
      <div className="flex gap-2">
        <Input
          placeholder="지역코드 직접 입력 (예: 11680)"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          className="w-56"
        />
        <Button
          onClick={() => code && onSubmit([code])}
          disabled={!code || loading}
          size="sm"
        >
          {loading ? "처리중..." : buttonLabel}
        </Button>
      </div>

      {/* 시/도 선택 */}
      <div>
        <div className="mb-1.5 flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            시/도 (클릭하여 시/군/구 펼침)
          </span>
          <div className="flex gap-2">
            {selectedCodes.size > 0 && (
              <button
                onClick={() => setSelectedCodes(new Set())}
                disabled={loading}
                className="text-xs text-muted-foreground hover:text-foreground disabled:opacity-50"
              >
                선택 초기화
              </button>
            )}
            <button
              onClick={toggleAll}
              disabled={loading}
              className="text-xs text-primary hover:underline disabled:opacity-50"
            >
              {isAllSelected ? "전체 해제" : "전체 선택"}
            </button>
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(SIDO_REGIONS).map(([sidoCode, name]) => {
            const status = getSidoStatus(sidoCode)
            const isExpanded = expandedSido === sidoCode
            const codes = getRegionCodes(sidoCode)
            const selectedCount = codes.filter((c) =>
              selectedCodes.has(c),
            ).length
            return (
              <button
                key={sidoCode}
                onClick={() =>
                  setExpandedSido(isExpanded ? null : sidoCode)
                }
                disabled={loading || codes.length === 0}
                className={`rounded-md border px-2.5 py-1 text-xs transition-colors disabled:opacity-50 ${
                  status === "all"
                    ? "border-primary bg-primary text-primary-foreground"
                    : status === "partial"
                      ? "border-primary/50 bg-primary/10 text-primary"
                      : isExpanded
                        ? "border-foreground/30 bg-accent"
                        : "hover:bg-accent"
                }`}
              >
                {name}
                {selectedCount > 0 && status !== "all" && (
                  <span className="ml-0.5 opacity-70">
                    {selectedCount}/{codes.length}
                  </span>
                )}
              </button>
            )
          })}
        </div>
      </div>

      {/* 시/군/구 상세 (클릭으로 펼침) */}
      {expandedSido && Object.keys(filteredRegions).length > 0 && (
        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <span className="text-xs text-muted-foreground">
              {SIDO_REGIONS[expandedSido]} 시/군/구
            </span>
            <button
              onClick={toggleExpandedAll}
              disabled={loading}
              className="text-xs text-primary hover:underline disabled:opacity-50"
            >
              {expandedAllSelected ? "전체 해제" : "전체 선택"}
            </button>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(filteredRegions).map(([regionCode, name]) => {
              const isSelected = selectedCodes.has(regionCode)
              return (
                <button
                  key={regionCode}
                  onClick={() => toggleRegion(regionCode)}
                  disabled={loading}
                  className={`rounded-md border px-2.5 py-1 text-xs transition-colors disabled:opacity-50 ${
                    isSelected
                      ? "border-primary bg-primary text-primary-foreground"
                      : "hover:bg-accent"
                  }`}
                >
                  {name}
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* 발견 시작 버튼 */}
      {selectedCodes.size > 0 && (
        <div className="flex items-center justify-between rounded-md border border-primary/20 bg-primary/5 px-3 py-2">
          <span className="text-sm">
            <span className="font-medium">{selectedCodes.size}</span>개 지역
            선택됨
          </span>
          <Button
            size="sm"
            onClick={() => onSubmit(Array.from(selectedCodes))}
            disabled={loading}
          >
            {loading ? "처리중..." : `${buttonLabel} (${selectedCodes.size})`}
          </Button>
        </div>
      )}
    </div>
  )
}
