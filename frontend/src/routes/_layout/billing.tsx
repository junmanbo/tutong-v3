import { createFileRoute, Link } from "@tanstack/react-router"
import { CreditCard, ReceiptText } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export const Route = createFileRoute("/_layout/billing")({
  component: BillingPage,
  head: () => ({
    meta: [{ title: "결제 - AutoTrade" }],
  }),
})

function BillingPage() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">결제</h1>
          <p className="text-muted-foreground">
            플랜 관리 및 결제 내역을 확인합니다.
          </p>
        </div>
        <Badge variant="outline" className="gap-1">
          <CreditCard className="size-3.5" />
          구독 활성
        </Badge>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>플랜</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              플랜을 비교하고 구독을 변경합니다.
            </p>
            <Link to="/billing/plans">
              <Button className="w-full">플랜 보기</Button>
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ReceiptText className="size-4" />
              결제 내역
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              결제 영수증 및 청구 내역을 확인합니다.
            </p>
            <Link to="/billing/history">
              <Button className="w-full" variant="outline">
                내역 보기
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
