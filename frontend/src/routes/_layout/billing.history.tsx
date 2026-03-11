import { createFileRoute } from "@tanstack/react-router"

import { paymentHistory } from "@/components/Billing/data"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

export const Route = createFileRoute("/_layout/billing/history")({
  component: BillingHistoryPage,
  head: () => ({
    meta: [{ title: "결제 내역 - AutoTrade" }],
  }),
})

function BillingHistoryPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">결제 내역</h1>
        <p className="text-muted-foreground">
          최근 결제 및 구독 청구 내역입니다.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>청구서</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>날짜</TableHead>
                <TableHead>플랜</TableHead>
                <TableHead>금액</TableHead>
                <TableHead>상태</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {paymentHistory.map((item) => (
                <TableRow key={`${item.date}-${item.plan}`}>
                  <TableCell>{item.date}</TableCell>
                  <TableCell>{item.plan}</TableCell>
                  <TableCell>{item.amount}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{item.status}</Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
