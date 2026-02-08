import { useState } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { ArrowLeft, Pencil, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
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
import ConfirmDialog from "@/components/shared/ConfirmDialog"
import EmptyState from "@/components/shared/EmptyState"
import PriceTrendChart from "@/components/charts/PriceTrendChart"
import ComplexFormDialog from "./ComplexFormDialog"
import { useComplex, useUpdateComplex, useDeleteComplex } from "@/hooks/useComplexes"
import { useKBPrices, useTransactions, useListings } from "@/hooks/useData"
import { PRIORITY_LABELS, LISTING_STATUS_LABELS } from "@/lib/constants"
import { formatPrice, formatDate, formatM2 } from "@/lib/format"
import { toast } from "sonner"

export default function ComplexDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const complexId = Number(id)

  const { data: complex, isLoading } = useComplex(complexId)
  const [showEdit, setShowEdit] = useState(false)
  const [showDelete, setShowDelete] = useState(false)
  const [selectedAreaId, setSelectedAreaId] = useState<number | undefined>()

  const updateMutation = useUpdateComplex()
  const deleteMutation = useDeleteComplex()

  const areaId = selectedAreaId ?? complex?.areas?.[0]?.id
  const { data: prices } = useKBPrices({
    complex_id: complexId,
    area_id: areaId,
    limit: 100,
  })
  const { data: transactions } = useTransactions({
    complex_id: complexId,
    limit: 100,
  })
  const { data: listings } = useListings({ complex_id: complexId, limit: 100 })

  if (isLoading) {
    return <p className="py-8 text-center text-muted-foreground">로딩중...</p>
  }

  if (!complex) {
    return <EmptyState message="단지를 찾을 수 없습니다" />
  }

  return (
    <div>
      <PageHeader
        title={complex.name}
        actions={
          <>
            <Button variant="ghost" size="sm" onClick={() => navigate("/complexes")}>
              <ArrowLeft className="mr-1.5 h-4 w-4" />
              목록
            </Button>
            <Button variant="outline" size="sm" onClick={() => setShowEdit(true)}>
              <Pencil className="mr-1.5 h-4 w-4" />
              수정
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowDelete(true)}
              className="text-destructive"
            >
              <Trash2 className="mr-1.5 h-4 w-4" />
              삭제
            </Button>
          </>
        }
      />

      <div className="mb-6 grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-md border p-3">
          <span className="text-muted-foreground">주소</span>
          <p className="mt-1 font-medium">{complex.address}</p>
        </div>
        <div className="rounded-md border p-3">
          <span className="text-muted-foreground">KB 단지 ID</span>
          <p className="mt-1 font-medium">{complex.kb_complex_id || "-"}</p>
        </div>
        <div className="rounded-md border p-3">
          <span className="text-muted-foreground">우선순위 / 상태</span>
          <div className="mt-1 flex gap-2">
            <StatusBadge
              status={complex.priority}
              label={PRIORITY_LABELS[complex.priority]}
            />
            <StatusBadge
              status={complex.is_active ? "ACTIVE" : "DISABLED"}
              label={complex.is_active ? "활성" : "비활성"}
            />
          </div>
        </div>
        <div className="rounded-md border p-3">
          <span className="text-muted-foreground">지역코드 / 매물수집</span>
          <p className="mt-1 font-medium">
            {complex.region_code || "-"} / {complex.collect_listings ? "ON" : "OFF"}
          </p>
        </div>
      </div>

      <Tabs defaultValue="areas">
        <TabsList>
          <TabsTrigger value="areas">면적 타입</TabsTrigger>
          <TabsTrigger value="prices">시세 추이</TabsTrigger>
          <TabsTrigger value="transactions">실거래가</TabsTrigger>
          <TabsTrigger value="listings">매물</TabsTrigger>
        </TabsList>

        <TabsContent value="areas">
          <Card>
            <CardContent className="pt-6">
              {!complex.areas || complex.areas.length === 0 ? (
                <EmptyState message="면적 정보가 없습니다" />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>전용면적</TableHead>
                      <TableHead>공급면적</TableHead>
                      <TableHead>평형</TableHead>
                      <TableHead>KB 코드</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {complex.areas.map((a) => (
                      <TableRow key={a.id}>
                        <TableCell>{formatM2(a.exclusive_m2)}</TableCell>
                        <TableCell>{formatM2(a.supply_m2)}</TableCell>
                        <TableCell>{a.pyeong ? `${a.pyeong}평` : "-"}</TableCell>
                        <TableCell className="text-muted-foreground">
                          {a.kb_area_code || "-"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="prices">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">KB 시세 추이</CardTitle>
                {complex.areas && complex.areas.length > 1 && (
                  <select
                    className="rounded border px-2 py-1 text-sm"
                    value={areaId}
                    onChange={(e) => setSelectedAreaId(Number(e.target.value))}
                  >
                    {complex.areas.map((a) => (
                      <option key={a.id} value={a.id}>
                        {formatM2(a.exclusive_m2)}
                        {a.pyeong ? ` (${a.pyeong}평)` : ""}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            </CardHeader>
            <CardContent>
              <PriceTrendChart data={prices ?? []} />
              {prices && prices.length > 0 && (
                <Table className="mt-4">
                  <TableHeader>
                    <TableRow>
                      <TableHead>기준일</TableHead>
                      <TableHead>일반가</TableHead>
                      <TableHead>상위평균</TableHead>
                      <TableHead>하위평균</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {prices.map((p) => (
                      <TableRow key={p.id}>
                        <TableCell>{p.as_of_date}</TableCell>
                        <TableCell>{formatPrice(p.general_price)}</TableCell>
                        <TableCell>{formatPrice(p.high_avg_price)}</TableCell>
                        <TableCell>{formatPrice(p.low_avg_price)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="transactions">
          <Card>
            <CardContent className="pt-6">
              {!transactions || transactions.length === 0 ? (
                <EmptyState message="실거래가 데이터가 없습니다" />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>계약일</TableHead>
                      <TableHead>거래가</TableHead>
                      <TableHead>전용면적</TableHead>
                      <TableHead>층</TableHead>
                      <TableHead>출처</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {transactions.map((t) => (
                      <TableRow key={t.id}>
                        <TableCell>{formatDate(t.contract_date)}</TableCell>
                        <TableCell className="font-medium">
                          {formatPrice(t.price)}
                        </TableCell>
                        <TableCell>{formatM2(t.exclusive_m2)}</TableCell>
                        <TableCell>{t.floor ?? "-"}층</TableCell>
                        <TableCell>{t.source}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="listings">
          <Card>
            <CardContent className="pt-6">
              {!listings || listings.length === 0 ? (
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
                        <TableCell className="text-xs text-muted-foreground">
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
                        <TableCell className="text-xs">
                          {formatDate(l.fetched_at)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <ComplexFormDialog
        open={showEdit}
        onOpenChange={setShowEdit}
        initial={complex}
        loading={updateMutation.isPending}
        onSubmit={(data) => {
          updateMutation.mutate(
            { id: complexId, data },
            {
              onSuccess: () => {
                toast.success("단지가 수정되었습니다")
                setShowEdit(false)
              },
              onError: () => toast.error("수정에 실패했습니다"),
            }
          )
        }}
      />

      <ConfirmDialog
        open={showDelete}
        onOpenChange={setShowDelete}
        title="단지 삭제"
        description={`"${complex.name}" 단지를 삭제하시겠습니까? 관련된 모든 데이터가 삭제됩니다.`}
        confirmLabel="삭제"
        destructive
        onConfirm={() => {
          deleteMutation.mutate(complexId, {
            onSuccess: () => {
              toast.success("단지가 삭제되었습니다")
              navigate("/complexes")
            },
            onError: () => toast.error("삭제에 실패했습니다"),
          })
        }}
      />
    </div>
  )
}
