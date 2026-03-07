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

export const Route = createFileRoute("/_layout/bots/new/spot-grid")({
  component: SpotGridBotPage,
  head: () => ({
    meta: [{ title: "Create Spot Grid Bot - AutoTrade" }],
  }),
})

function SpotGridBotPage() {
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
  const [upperPrice, setUpperPrice] = useState("75000")
  const [lowerPrice, setLowerPrice] = useState("55000")
  const [gridCount, setGridCount] = useState("20")
  const [gridType, setGridType] = useState("arithmetic")
  const [investmentAmount, setInvestmentAmount] = useState("1000")
  const [stopLossPct, setStopLossPct] = useState("")
  const [takeProfitPct, setTakeProfitPct] = useState("")

  const mutation = useMutation({
    mutationFn: () =>
      BotsService.createBot({
        requestBody: {
          name: name.trim() || "Spot Grid Bot",
          bot_type: "spot_grid",
          account_id: accountId,
          symbol: symbol.trim().toUpperCase(),
          investment_amount: investmentAmount.trim(),
          stop_loss_pct: stopLossPct.trim() || undefined,
          take_profit_pct: takeProfitPct.trim() || undefined,
        },
      }),
    onSuccess: () => {
      showSuccessToast("Spot Grid bot created")
      queryClient.invalidateQueries({ queryKey: ["bots"] })
      navigate({ to: "/bots" })
    },
    onError: handleError.bind(showErrorToast),
  })

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!accountId || !symbol.trim() || !investmentAmount.trim()) {
      showErrorToast("Account, symbol, and investment amount are required.")
      return
    }
    mutation.mutate()
  }

  const spread = Math.max(0, Number(upperPrice) - Number(lowerPrice))
  const perGrid = Number(gridCount) > 0 ? Number(investmentAmount) / Number(gridCount) : 0

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <Button variant="outline" size="sm" onClick={() => navigate({ to: "/bots/new" })}>
          <ArrowLeft className="mr-2 size-4" />
          Back
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Spot Grid Bot 만들기</CardTitle>
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
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="BTC Grid Bot" />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Trading Pair *</Label>
                <Input value={symbol} onChange={(e) => setSymbol(e.target.value)} placeholder="BTC/USDT" />
              </div>
              <div className="space-y-2">
                <Label>Total Investment (USDT) *</Label>
                <Input value={investmentAmount} onChange={(e) => setInvestmentAmount(e.target.value)} />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <Label>Upper Price</Label>
                <Input value={upperPrice} onChange={(e) => setUpperPrice(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>Lower Price</Label>
                <Input value={lowerPrice} onChange={(e) => setLowerPrice(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>Grid Count</Label>
                <Input value={gridCount} onChange={(e) => setGridCount(e.target.value)} />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <Label>Grid Type</Label>
                <Select value={gridType} onValueChange={setGridType}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="arithmetic">Arithmetic</SelectItem>
                    <SelectItem value="geometric">Geometric</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Stop Loss %</Label>
                <Input value={stopLossPct} onChange={(e) => setStopLossPct(e.target.value)} placeholder="optional" />
              </div>
              <div className="space-y-2">
                <Label>Take Profit %</Label>
                <Input value={takeProfitPct} onChange={(e) => setTakeProfitPct(e.target.value)} placeholder="optional" />
              </div>
            </div>

            <div className="rounded-md border bg-muted/30 p-3 text-sm text-muted-foreground">
              예상 스프레드: {spread.toLocaleString()} / 그리드당 투자금:{" "}
              {Number.isFinite(perGrid) ? perGrid.toFixed(2) : "0"}
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
