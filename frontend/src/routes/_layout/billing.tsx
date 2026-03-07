import { Link, createFileRoute } from "@tanstack/react-router"
import { CreditCard, ReceiptText } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export const Route = createFileRoute("/_layout/billing")({
  component: BillingPage,
  head: () => ({
    meta: [{ title: "Billing - AutoTrade" }],
  }),
})

function BillingPage() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Billing</h1>
          <p className="text-muted-foreground">
            Navigate to plan management and payment history.
          </p>
        </div>
        <Badge variant="outline" className="gap-1">
          <CreditCard className="size-3.5" />
          Subscription Active
        </Badge>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Plans</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Compare plans and change your subscription.
            </p>
            <Link to="/billing/plans">
              <Button className="w-full">Go to Plans</Button>
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ReceiptText className="size-4" />
              Payment History
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Review payment receipts and billing activity.
            </p>
            <Link to="/billing/history">
              <Button className="w-full" variant="outline">
                Go to History
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
