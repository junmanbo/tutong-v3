import { createFileRoute } from "@tanstack/react-router"
import { Check, Sparkles } from "lucide-react"

import { plans } from "@/components/Billing/data"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export const Route = createFileRoute("/_layout/billing/plans")({
  component: BillingPlansPage,
  head: () => ({
    meta: [{ title: "Billing Plans - AutoTrade" }],
  }),
})

function BillingPlansPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Plan Selection</h1>
        <p className="text-muted-foreground">
          Choose the subscription that fits your trading scale.
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
                    Current
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
                {plan.isCurrent ? "Current Plan" : "Upgrade"}
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
