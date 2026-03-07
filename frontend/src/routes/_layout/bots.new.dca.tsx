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

export const Route = createFileRoute("/_layout/bots/new/dca")({
  component: DcaBotPage,
  head: () => ({
    meta: [{ title: "Create Spot DCA Bot - AutoTrade" }],
  }),
})

function DcaBotPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { data: accounts } = useQuery({
    queryKey: ["accounts"],
    queryFn: () => AccountsService.readAccounts({ skip: 0, limit: 100 }),
  })

  const [accountId, setAccountId] = useState("")
  const [name, setName] = useState("")
  const [symbol, setSymbol] = useState("BTC/USDT")
  const [buyAmount, setBuyAmount] = useState("100")
  const [frequency, setFrequency] = useState("daily")
  const [buyTime, setBuyTime] = useState("09:00")
  const [runMode, setRunMode] = useState("count")
  const [cycles, setCycles] = useState("30")
  const [endDate, setEndDate] = useState("")
  const [takeProfitPct, setTakeProfitPct] = useState("20")

  const mutation = useMutation({
    mutationFn: () =>
      BotsService.createBot({
        requestBody: {
          name: name.trim() || "Spot DCA Bot",
          bot_type: "spot_dca",
          account_id: accountId,
          symbol: symbol.trim().toUpperCase(),
          investment_amount: buyAmount.trim(),
          take_profit_pct: takeProfitPct.trim() || undefined,
          config: {
            amount_per_order: buyAmount.trim(),
            interval_seconds:
              frequency === "daily"
                ? 86400
                : frequency === "weekly"
                  ? 604800
                  : 2592000,
            order_type: "market",
            total_orders: runMode === "count" ? Number(cycles) : undefined,
          },
        },
      }),
    onSuccess: () => {
      showSuccessToast("Spot DCA bot created")
      queryClient.invalidateQueries({ queryKey: ["bots"] })
      navigate({ to: "/bots" })
    },
    onError: handleError.bind(showErrorToast),
  })

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!accountId || !symbol.trim() || !buyAmount.trim()) {
      showErrorToast("Account, symbol, and buy amount are required.")
      return
    }
    mutation.mutate()
  }

  const totalPlanned =
    runMode === "count"
      ? Number(buyAmount || 0) * Number(cycles || 0)
      : Number(buyAmount || 0)

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
          <CardTitle>Spot DCA Bot 만들기</CardTitle>
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
                  placeholder="BTC DCA Bot"
                />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <Label>Trading Pair *</Label>
                <Input
                  value={symbol}
                  onChange={(e) => setSymbol(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>Buy Amount per Cycle *</Label>
                <Input
                  value={buyAmount}
                  onChange={(e) => setBuyAmount(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>Take Profit %</Label>
                <Input
                  value={takeProfitPct}
                  onChange={(e) => setTakeProfitPct(e.target.value)}
                />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <Label>Frequency</Label>
                <Select value={frequency} onValueChange={setFrequency}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="daily">Daily</SelectItem>
                    <SelectItem value="weekly">Weekly</SelectItem>
                    <SelectItem value="monthly">Monthly</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Buy Time</Label>
                <Input
                  type="time"
                  value={buyTime}
                  onChange={(e) => setBuyTime(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>Run Mode</Label>
                <Select value={runMode} onValueChange={setRunMode}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="count">By Count</SelectItem>
                    <SelectItem value="date">Until Date</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {runMode === "count" ? (
              <div className="space-y-2">
                <Label>Cycles</Label>
                <Input
                  value={cycles}
                  onChange={(e) => setCycles(e.target.value)}
                />
              </div>
            ) : (
              <div className="space-y-2">
                <Label>End Date</Label>
                <Input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                />
              </div>
            )}

            <div className="rounded-md border bg-muted/30 p-3 text-sm text-muted-foreground">
              계획 투자금(대략):{" "}
              {Number.isFinite(totalPlanned) ? totalPlanned.toFixed(2) : "0"}
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
