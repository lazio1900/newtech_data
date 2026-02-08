import { useState } from "react"
import { Card, CardContent } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import StatusBadge from "@/components/shared/StatusBadge"
import EmptyState from "@/components/shared/EmptyState"
import { useListings } from "@/hooks/useData"
import { LISTING_STATUS_LABELS } from "@/lib/constants"
import { formatPrice, formatDate, formatM2 } from "@/lib/format"

interface ListingTabProps {
  complexId: number | undefined
}

export default function ListingTab({ complexId }: ListingTabProps) {
  const [statusFilter, setStatusFilter] = useState<string | undefined>()
  const { data: listings, isLoading } = useListings({
    complex_id: complexId,
    status: statusFilter,
    limit: 200,
  })

  if (!complexId) {
    return <EmptyState message="단지를 선택하세요" />
  }

  return (
    <Card>
      <CardContent className="pt-6">
        <div className="mb-4 flex items-center gap-2">
          <span className="text-sm text-muted-foreground">상태:</span>
          <select
            className="rounded-md border bg-background px-2 py-1 text-sm"
            value={statusFilter ?? ""}
            onChange={(e) =>
              setStatusFilter(e.target.value || undefined)
            }
          >
            <option value="">전체</option>
            {Object.entries(LISTING_STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>

        {isLoading ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            로딩중...
          </p>
        ) : !listings || listings.length === 0 ? (
          <EmptyState message="매물 데이터가 없습니다" />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>매물ID</TableHead>
                <TableHead>호가</TableHead>
                <TableHead>전용면적</TableHead>
                <TableHead>층</TableHead>
                <TableHead>상태</TableHead>
                <TableHead>수집일</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {listings.map((l) => (
                <TableRow key={l.id}>
                  <TableCell className="text-xs font-mono text-muted-foreground">
                    {l.source_listing_id}
                  </TableCell>
                  <TableCell className="font-medium">
                    {formatPrice(l.ask_price)}
                  </TableCell>
                  <TableCell>{formatM2(l.exclusive_m2)}</TableCell>
                  <TableCell>{l.floor ?? "-"}층</TableCell>
                  <TableCell>
                    <StatusBadge
                      status={l.status}
                      label={LISTING_STATUS_LABELS[l.status] || l.status}
                    />
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {formatDate(l.fetched_at)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}
