import { Card, CardContent } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import EmptyState from "@/components/shared/EmptyState"
import type { FacilityGroup, Facility } from "@/types/complex"

const FACILITY_LABELS: Record<string, string> = {
  school: "학군",
  subway: "지하철",
  hospital: "병원",
  park: "자연환경",
}

const SUB_TYPE_LABELS: Record<string, string> = {
  // 학교
  kindergarten: "어린이집",
  preschool: "유치원",
  elementary: "초등",
  middle: "중등",
  high: "고등",
  // 공원/자연
  park: "공원",
  garden: "정원",
  playground: "놀이터",
  forest: "숲/임야",
  grassland: "녹지",
  water: "수변",
  river: "하천",
}

const FACILITY_ORDER = ["school", "subway", "hospital", "park"]

function fmtSubType(facilityType: string, subType: string | null): string {
  if (!subType) return "-"
  if (facilityType === "subway") return subType
  return SUB_TYPE_LABELS[subType] || subType
}

function FacilityTable({
  type,
  items,
}: {
  type: string
  items: Facility[]
}) {
  if (items.length === 0) {
    return <EmptyState message="수집된 데이터가 없습니다" />
  }
  return (
    <>
      <div className="mb-3 text-xs text-muted-foreground">
        총 {items.length}건
        {items[0].distance_m != null && ` · 가장 가까운 거리 ${items[0].distance_m}m`}
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-24">분류</TableHead>
            <TableHead>이름</TableHead>
            <TableHead className="w-24 text-right">거리</TableHead>
            {(type === "school" || type === "hospital") && (
              <TableHead className="hidden md:table-cell">주소</TableHead>
            )}
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((f) => (
            <TableRow key={f.id}>
              <TableCell className="text-sm text-muted-foreground">
                {fmtSubType(type, f.sub_type)}
              </TableCell>
              <TableCell className="font-medium">{f.name}</TableCell>
              <TableCell className="text-right text-sm">
                {f.distance_m != null ? `${f.distance_m}m` : "-"}
              </TableCell>
              {(type === "school" || type === "hospital") && (
                <TableCell className="hidden max-w-[280px] truncate text-xs text-muted-foreground md:table-cell">
                  {f.address || "-"}
                </TableCell>
              )}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </>
  )
}

export default function FacilitiesPanel({
  group,
}: {
  group: FacilityGroup | undefined
}) {
  if (!group) {
    return (
      <Card>
        <CardContent className="pt-6">
          <EmptyState message="로딩중..." />
        </CardContent>
      </Card>
    )
  }

  const total = Object.values(group.counts).reduce((a, b) => a + b, 0)
  if (total === 0) {
    return (
      <Card>
        <CardContent className="pt-6">
          <EmptyState message="수집된 주변 시설이 없습니다. 단지 좌표가 채워진 후 시설 수집을 다시 실행해주세요." />
        </CardContent>
      </Card>
    )
  }

  // 첫 탭은 데이터가 있는 첫 카테고리로 자동 설정
  const defaultTab =
    FACILITY_ORDER.find((t) => (group.counts[t] || 0) > 0) || FACILITY_ORDER[0]

  return (
    <Card>
      <CardContent className="pt-6">
        <Tabs defaultValue={defaultTab}>
          <TabsList>
            {FACILITY_ORDER.map((type) => {
              const count = group.counts[type] || 0
              return (
                <TabsTrigger key={type} value={type}>
                  {FACILITY_LABELS[type] || type}
                  <span className="ml-1.5 text-xs text-muted-foreground">
                    {count}
                  </span>
                </TabsTrigger>
              )
            })}
          </TabsList>

          {FACILITY_ORDER.map((type) => (
            <TabsContent key={type} value={type} className="mt-4">
              <FacilityTable type={type} items={group.items[type] || []} />
            </TabsContent>
          ))}
        </Tabs>
      </CardContent>
    </Card>
  )
}
