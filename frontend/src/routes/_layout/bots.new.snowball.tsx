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

export const Route = createFileRoute("/_layout/bots/new/snowball")({
  component: SnowballBotPage,
  head: () => ({
    meta: [{ title: "Create Snowball Bot - AutoTrade" }],
  }),
})

function SnowballBotPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { data: accounts } = useQuery({
    queryKey: ["accounts"],
    queryFn: () => AccountsService.readAccounts({ skip: 0, limit: 100 }),
  })

  const [accountId, setAccountId] = useState("")
  const [name, setName] = useState("")
  const [symbol, setSymbol] = useState("BTC/KRW")
  const [initialBuyAmount, setInitialBuyAmount] = useState("100")
  const [dropTriggerPct, setDropTriggerPct] = useState("5")
  const [multiplier, setMultiplier] = useState("2.0")
  const [maxAdds, setMaxAdds] = useState("5")
  const [takeProfitPct, setTakeProfitPct] = useState("5")
  const [stopLossPct, setStopLossPct] = useState("")

  const mutation = useMutation({
    mutationFn: () =>
      BotsService.createBot({
        requestBody: {
          name: name.trim() || "Snowball Bot",
          bot_type: "position_snowball",
          account_id: accountId,
          symbol: symbol.trim().toUpperCase(),
          investment_amount: initialBuyAmount.trim(),
          stop_loss_pct: stopLossPct.trim() || undefined,
          take_profit_pct: takeProfitPct.trim() || undefined,
          config: {
            drop_pct: dropTriggerPct.trim(),
            amount_per_buy: initialBuyAmount.trim(),
            take_profit_pct: takeProfitPct.trim(),
            max_buys: Number(maxAdds),
            multiplier: multiplier.trim(),
          },
        },
      }),
    onSuccess: () => {
      showSuccessToast("Snowball bot created")
      queryClient.invalidateQueries({ queryKey: ["bots"] })
      navigate({ to: "/bots" })
    },
    onError: handleError.bind(showErrorToast),
  })

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!accountId || !symbol.trim() || !initialBuyAmount.trim()) {
      showErrorToast("Account, symbol, and initial buy amount are required.")
      return
    }
    mutation.mutate()
  }

  const estimatedMaxCapital =
    Number(initialBuyAmount) *
    (Number.isFinite(Number(multiplier))
      ? Number(multiplier) ** Number(maxAdds)
      : 0)

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
          <CardTitle>Position Snowball Bot 만들기</CardTitle>
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
                  placeholder="BTC Snowball Bot"
                />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Trading Pair *</Label>
                <Input
                  value={symbol}
                  onChange={(e) => setSymbol(e.target.value)}
                  placeholder="BTC/KRW"
                />
              </div>
              <div className="space-y-2">
                <Label>Initial Buy Amount (KRW) *</Label>
                <Input
                  value={initialBuyAmount}
                  onChange={(e) => setInitialBuyAmount(e.target.value)}
                />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-4">
              <div className="space-y-2">
                <Label>Drop Trigger %</Label>
                <Input
                  value={dropTriggerPct}
                  onChange={(e) => setDropTriggerPct(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>Add Multiplier</Label>
                <Input
                  value={multiplier}
                  onChange={(e) => setMultiplier(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>Max Add Count</Label>
                <Input
                  value={maxAdds}
                  onChange={(e) => setMaxAdds(e.target.value)}
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

            <div className="space-y-2">
              <Label>Stop Loss %</Label>
              <Input
                value={stopLossPct}
                onChange={(e) => setStopLossPct(e.target.value)}
                placeholder="optional"
              />
            </div>

            <div className="rounded-md border bg-muted/30 p-3 text-sm text-muted-foreground">
              예상 최대 누적 투자금(대략):{" "}
              {Number.isFinite(estimatedMaxCapital)
                ? estimatedMaxCapital.toFixed(2)
                : "0"}{" "}
              KRW
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
