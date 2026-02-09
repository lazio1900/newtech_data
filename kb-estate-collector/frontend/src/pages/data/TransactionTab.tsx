import { Card, CardContent } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import EmptyState from "@/components/shared/EmptyState"
import { useTransactions } from "@/hooks/useData"
import { useComplex } from "@/hooks/useComplexes"
import { formatPrice, formatDate, formatM2 } from "@/lib/format"

interface TransactionTabProps {
  complexId: number | undefined
}

export default function TransactionTab({ complexId }: TransactionTabProps) {
  const { data: transactions, isLoading } = useTransactions({
    complex_id: complexId,
    limit: 200,
  })
  const { data: complex } = useComplex(complexId ?? 0)

  return (
    <Card>
      <CardContent className="pt-6">
        {isLoading ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            로딩중...
          </p>
        ) : !transactions || transactions.length === 0 ? (
          <EmptyState message="실거래가 데이터가 없습니다" />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                {!complexId && <TableHead>단지</TableHead>}
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
                  {!complexId && (
                    <TableCell className="text-sm">
                      {complex?.name ?? `#${t.complex_id}`}
                    </TableCell>
                  )}
                  <TableCell>{formatDate(t.contract_date)}</TableCell>
                  <TableCell className="font-medium">
                    {formatPrice(t.price)}
                  </TableCell>
                  <TableCell>{formatM2(t.exclusive_m2)}</TableCell>
                  <TableCell>{t.floor ?? "-"}층</TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {t.source}
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
