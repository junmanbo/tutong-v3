import { createFileRoute } from "@tanstack/react-router"
import { Check, Sparkles } from "lucide-react"

import { plans } from "@/components/Billing/data"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export const Route = createFileRoute("/_layout/billing/plans")({
  component: BillingPlansPage,
  head: () => ({
    meta: [{ title: "요금제 - AutoTrade" }],
  }),
})

function BillingPlansPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">플랜 선택</h1>
        <p className="text-muted-foreground">
          거래 규모에 맞는 구독 플랜을 선택하세요.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {plans.map((plan) => (
          <Card
            key={plan.name}
            className={plan.isCurrent ? "border-primary shadow-sm" : ""}
          >
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>{plan.name}</CardTitle>
                {plan.isCurrent && (
                  <Badge className="gap-1">
                    <Sparkles className="size-3.5" />
                    현재 플랜
                  </Badge>
                )}
              </div>
              <p className="text-2xl font-bold">{plan.price}</p>
            </CardHeader>
            <CardContent className="space-y-3">
              <ul className="space-y-2">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-center gap-2 text-sm">
                    <Check className="size-4 text-green-600" />
                    {feature}
                  </li>
                ))}
              </ul>
              <Button
                className="w-full"
                variant={plan.isCurrent ? "outline" : "default"}
              >
                {plan.isCurrent ? "현재 플랜" : "업그레이드"}
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
