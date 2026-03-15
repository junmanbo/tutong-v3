import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { ArrowLeft } from "lucide-react"
import { type FormEvent, useMemo, useState } from "react"

import { AccountsService, BotsService } from "@/client"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import { getUpbitMinOrderMessage, isUpbitKrwMarket } from "@/lib/upbit-order-rules"
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
    meta: [{ title: "포지션 스노우볼 봇 생성 - AutoTrade" }],
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
  const [initialBuyAmount, setInitialBuyAmount] = useState("100000")
  const [dropTriggerPct, setDropTriggerPct] = useState("5")
  const [multiplier, setMultiplier] = useState("2.0")
  const [maxAdds, setMaxAdds] = useState("5")
  const [takeProfitPct, setTakeProfitPct] = useState("5")
  const selectedAccount = useMemo(
    () => accounts?.data.find((acc) => acc.id === accountId),
    [accounts, accountId],
  )

  const mutation = useMutation({
    mutationFn: () =>
      BotsService.createBot({
        requestBody: {
          name: name.trim() || "스노우볼 봇",
          bot_type: "position_snowball",
          account_id: accountId,
          symbol: symbol.trim().toUpperCase(),
          investment_amount: initialBuyAmount.trim(),
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
      showSuccessToast("포지션 스노우볼 봇이 생성되었습니다")
      queryClient.invalidateQueries({ queryKey: ["bots"] })
      navigate({ to: "/bots" })
    },
    onError: handleError.bind(showErrorToast),
  })

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    const amount = Number(initialBuyAmount)
    const drop = Number(dropTriggerPct)
    const mult = Number(multiplier)
    const max = Number(maxAdds)
    const tp = Number(takeProfitPct)

    if (!accountId || !symbol.trim()) {
      showErrorToast("계좌와 거래 자산을 입력해주세요.")
      return
    }
    if (![amount, drop, mult, max, tp].every((v) => Number.isFinite(v) && v > 0)) {
      showErrorToast("금액/비율/횟수는 0보다 큰 숫자여야 합니다.")
      return
    }
    if (upbitMinOrderMessage) {
      showErrorToast(upbitMinOrderMessage)
      return
    }
    mutation.mutate()
  }

  const estimatedMaxCapital = useMemo(() => {
    const amount = Number(initialBuyAmount)
    const mult = Number(multiplier)
    const adds = Number(maxAdds)
    if (!Number.isFinite(amount) || !Number.isFinite(mult) || !Number.isFinite(adds)) {
      return 0
    }
    if (mult === 1) return amount * (adds + 1)
    return amount * ((mult ** (adds + 1) - 1) / (mult - 1))
  }, [initialBuyAmount, multiplier, maxAdds])
  const upbitMinOrderMessage = useMemo(() => {
    if (!isUpbitKrwMarket(selectedAccount?.exchange, symbol)) return null
    return getUpbitMinOrderMessage(Number(initialBuyAmount), "기본 매수 금액")
  }, [initialBuyAmount, selectedAccount?.exchange, symbol])

  return (
    <div className="flex flex-col gap-6">
      <Button
        variant="outline"
        size="sm"
        onClick={() => navigate({ to: "/bots/new" })}
      >
        <ArrowLeft className="mr-2 size-4" />
        이전
      </Button>

      <Card>
        <CardHeader>
          <CardTitle>포지션 스노우볼 봇 만들기</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={onSubmit}>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>거래소 계좌 *</Label>
                <Select value={accountId} onValueChange={setAccountId}>
                  <SelectTrigger>
                    <SelectValue placeholder="계좌 선택" />
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
                <Label>봇 이름 (선택)</Label>
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="예) 비트코인 스노우볼 봇"
                />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>거래 자산 *</Label>
                <Input
                  value={symbol}
                  onChange={(e) => setSymbol(e.target.value)}
                  placeholder="예) BTC/KRW"
                />
              </div>
              <div className="space-y-2">
                <Label>초기 매수 금액 (KRW) *</Label>
                <Input
                  value={initialBuyAmount}
                  onChange={(e) => setInitialBuyAmount(e.target.value)}
                  inputMode="numeric"
                />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-4">
              <div className="space-y-2">
                <Label>추가 매수 트리거(하락 %)</Label>
                <Input
                  value={dropTriggerPct}
                  onChange={(e) => setDropTriggerPct(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>추가 매수 배수</Label>
                <Input
                  value={multiplier}
                  onChange={(e) => setMultiplier(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>최대 추가 매수 횟수</Label>
                <Input
                  value={maxAdds}
                  onChange={(e) => setMaxAdds(e.target.value)}
                  inputMode="numeric"
                />
              </div>
              <div className="space-y-2">
                <Label>목표 수익률(전량 매도) %</Label>
                <Input
                  value={takeProfitPct}
                  onChange={(e) => setTakeProfitPct(e.target.value)}
                />
              </div>
            </div>

            <div className="rounded-md border bg-muted/30 p-3 text-sm text-muted-foreground">
              예상 최대 누적 투자금: {Math.round(estimatedMaxCapital).toLocaleString()} KRW
            </div>
            {isUpbitKrwMarket(selectedAccount?.exchange, symbol) && (
              <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                업비트 KRW 마켓에서는 초기 매수와 추가 매수 모두 최소 5,000 KRW 이상이어야 합니다.
              </div>
            )}
            {upbitMinOrderMessage && (
              <div className="text-sm text-destructive">{upbitMinOrderMessage}</div>
            )}

            <div className="flex justify-end">
              <LoadingButton
                type="submit"
                loading={mutation.isPending}
                disabled={Boolean(upbitMinOrderMessage)}
              >
                봇 생성
              </LoadingButton>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
