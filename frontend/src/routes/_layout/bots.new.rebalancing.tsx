import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { ArrowLeft } from "lucide-react"
import { type FormEvent, useState } from "react"

import { AccountsService, BotsService } from "@/client"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/bots/new/rebalancing")({
  component: RebalancingBotPage,
  head: () => ({
    meta: [{ title: "Create Rebalancing Bot - AutoTrade" }],
  }),
})

function RebalancingBotPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { data: accounts } = useQuery({
    queryKey: ["accounts"],
    queryFn: () => AccountsService.readAccounts({ skip: 0, limit: 100 }),
  })

  const [accountId, setAccountId] = useState("")
  const [name, setName] = useState("")
  const [baseCurrency, setBaseCurrency] = useState("BTC")
  const [quoteCurrency, setQuoteCurrency] = useState("USDT")
  const [baseWeight, setBaseWeight] = useState("40")
  const [quoteWeight, setQuoteWeight] = useState("60")
  const [rebalanceMode, setRebalanceMode] = useState("time")
  const [rebalanceInterval, setRebalanceInterval] = useState("1w")
  const [deviationPct, setDeviationPct] = useState("5")
  const [investmentAmount, setInvestmentAmount] = useState("5000")

  const mutation = useMutation({
    mutationFn: () =>
      BotsService.createBot({
        requestBody: {
          name: name.trim() || "Rebalancing Bot",
          bot_type: "rebalancing",
          account_id: accountId,
          base_currency: baseCurrency.trim().toUpperCase(),
          quote_currency: quoteCurrency.trim().toUpperCase(),
          investment_amount: investmentAmount.trim(),
          config: {
            assets: {
              [baseCurrency.trim().toUpperCase()]: baseWeight.trim(),
              [quoteCurrency.trim().toUpperCase()]: quoteWeight.trim(),
            },
            quote: quoteCurrency.trim().toUpperCase(),
            threshold_pct: deviationPct.trim(),
            interval_seconds:
              rebalanceInterval === "1d"
                ? 86400
                : rebalanceInterval === "1w"
                  ? 604800
                  : 2592000,
          },
        },
      }),
    onSuccess: () => {
      showSuccessToast("Rebalancing bot created")
      queryClient.invalidateQueries({ queryKey: ["bots"] })
      navigate({ to: "/bots" })
    },
    onError: handleError.bind(showErrorToast),
  })

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (
      !accountId ||
      !baseCurrency.trim() ||
      !quoteCurrency.trim() ||
      !investmentAmount.trim()
    ) {
      showErrorToast("Account, currencies, and investment amount are required.")
      return
    }
    if (
      baseCurrency.trim().toUpperCase() === quoteCurrency.trim().toUpperCase()
    ) {
      showErrorToast("Base and quote currency must be different.")
      return
    }
    mutation.mutate()
  }

  const totalWeight = Number(baseWeight || 0) + Number(quoteWeight || 0)

  return (
    <div className="flex flex-col gap-6">
      <Button
        variant="outline"
        size="sm"
        onClick={() => navigate({ to: "/bots/new" })}
      >
        <ArrowLeft className="mr-2 size-4" />
        Back
      </Button>

      <Card>
        <CardHeader>
          <CardTitle>Rebalancing Bot 만들기</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={onSubmit}>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Exchange Account *</Label>
                <Select value={accountId} onValueChange={setAccountId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select account" />
                  </SelectTrigger>
                  <SelectContent>
                    {accounts?.data.map((acc) => (
                      <SelectItem key={acc.id} value={acc.id}>
                        {acc.label} ({acc.exchange})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Bot Name</Label>
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Portfolio Rebalance Bot"
                />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-4">
              <div className="space-y-2">
                <Label>Asset 1</Label>
                <Input
                  value={baseCurrency}
                  onChange={(e) => setBaseCurrency(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>Target %</Label>
                <Input
                  value={baseWeight}
                  onChange={(e) => setBaseWeight(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>Asset 2</Label>
                <Input
                  value={quoteCurrency}
                  onChange={(e) => setQuoteCurrency(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>Target %</Label>
                <Input
                  value={quoteWeight}
                  onChange={(e) => setQuoteWeight(e.target.value)}
                />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <Label>Rebalance Mode</Label>
                <Select value={rebalanceMode} onValueChange={setRebalanceMode}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="time">Time-based</SelectItem>
                    <SelectItem value="deviation">Deviation-based</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Interval</Label>
                <Select
                  value={rebalanceInterval}
                  onValueChange={setRebalanceInterval}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="1d">Daily</SelectItem>
                    <SelectItem value="1w">Weekly</SelectItem>
                    <SelectItem value="1m">Monthly</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Deviation Trigger %</Label>
                <Input
                  value={deviationPct}
                  onChange={(e) => setDeviationPct(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label>Total Investment (USDT) *</Label>
              <Input
                value={investmentAmount}
                onChange={(e) => setInvestmentAmount(e.target.value)}
              />
            </div>

            <div className="rounded-md border bg-muted/30 p-3 text-sm text-muted-foreground">
              현재 구성 비중 합계: {totalWeight}%{" "}
              {totalWeight === 100 ? "✓" : "(100% 권장)"}
            </div>

            <div className="flex justify-end">
              <LoadingButton type="submit" loading={mutation.isPending}>
                봇 생성
              </LoadingButton>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
