import { useState } from "react"
import { Download } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import EmptyState from "@/components/shared/EmptyState"
import PriceTrendChart from "@/components/charts/PriceTrendChart"
import { useKBPrices } from "@/hooks/useData"
import { dataApi } from "@/api/data"
import { formatPrice, formatDate } from "@/lib/format"
import type { Complex } from "@/types/complex"

interface PriceTabProps {
  complexId: number | undefined
  complexes: Complex[]
}

export default function PriceTab({ complexId, complexes }: PriceTabProps) {
  const [areaId, setAreaId] = useState<number | undefined>()

  const complex = complexes.find((c) => c.id === complexId)
  const areas = complex?.areas ?? []

  const { data: prices, isLoading } = useKBPrices({
    complex_id: complexId,
    area_id: areaId,
    limit: 200,
  })

  if (!complexId) {
    return <EmptyState message="단지를 선택하세요" />
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {areas.length > 0 && (
            <select
              className="rounded-md border bg-background px-2 py-1.5 text-sm"
              value={areaId ?? ""}
              onChange={(e) =>
                setAreaId(e.target.value ? Number(e.target.value) : undefined)
              }
            >
              <option value="">전체 면적</option>
              {areas.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.exclusive_m2}㎡ {a.pyeong ? `(${a.pyeong}평)` : ""}
                </option>
              ))}
            </select>
          )}
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() =>
            dataApi.exportPricesCsv({
              complex_id: complexId,
              area_id: areaId,
            })
          }
        >
          <Download className="mr-1.5 h-4 w-4" />
          CSV 내보내기
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">시세 추이</CardTitle>
        </CardHeader>
        <CardContent>
          <PriceTrendChart data={prices ?? []} />
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6">
          {isLoading ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              로딩중...
            </p>
          ) : !prices || prices.length === 0 ? (
            <EmptyState message="시세 데이터가 없습니다" />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>기준일</TableHead>
                  <TableHead>일반가</TableHead>
                  <TableHead>상위평균</TableHead>
                  <TableHead>하위평균</TableHead>
                  <TableHead>수집일</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {prices.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell>{p.as_of_date}</TableCell>
                    <TableCell className="font-medium">
                      {formatPrice(p.general_price)}
                    </TableCell>
                    <TableCell>{formatPrice(p.high_avg_price)}</TableCell>
                    <TableCell>{formatPrice(p.low_avg_price)}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDate(p.fetched_at)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
