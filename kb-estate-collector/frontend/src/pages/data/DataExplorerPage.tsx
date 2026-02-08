import { useState } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import PageHeader from "@/components/layout/PageHeader"
import PriceTab from "./PriceTab"
import TransactionTab from "./TransactionTab"
import ListingTab from "./ListingTab"
import { useComplexes } from "@/hooks/useComplexes"

export default function DataExplorerPage() {
  const { data: complexes } = useComplexes({ limit: 1000 })
  const [selectedComplexId, setSelectedComplexId] = useState<number | undefined>()

  return (
    <div>
      <PageHeader title="데이터 탐색" description="수집된 데이터 조회 및 내보내기" />

      <div className="mb-4">
        <label className="mb-1 block text-sm font-medium">단지 선택</label>
        <select
          className="w-full max-w-sm rounded-md border bg-background px-3 py-2 text-sm"
          value={selectedComplexId ?? ""}
          onChange={(e) =>
            setSelectedComplexId(
              e.target.value ? Number(e.target.value) : undefined
            )
          }
        >
          <option value="">단지를 선택하세요</option>
          {complexes?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} ({c.address})
            </option>
          ))}
        </select>
      </div>

      <Tabs defaultValue="prices">
        <TabsList>
          <TabsTrigger value="prices">KB 시세</TabsTrigger>
          <TabsTrigger value="transactions">실거래가</TabsTrigger>
          <TabsTrigger value="listings">매물</TabsTrigger>
        </TabsList>

        <TabsContent value="prices">
          <PriceTab
            complexId={selectedComplexId}
            complexes={complexes ?? []}
          />
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
