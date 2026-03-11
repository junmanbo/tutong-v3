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
    meta: [{ title: "현물 그리드 봇 생성 - AutoTrade" }],
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
  const [symbol, setSymbol] = useState("BTC/KRW")
  const [upperPrice, setUpperPrice] = useState("120000000")
  const [lowerPrice, setLowerPrice] = useState("90000000")
  const [gridCount, setGridCount] = useState("20")
  const [gridType, setGridType] = useState("arithmetic")
  const [investmentAmount, setInvestmentAmount] = useState("1000000")
  const [stopLossPct, setStopLossPct] = useState("")
  const [takeProfitPct, setTakeProfitPct] = useState("")

  const mutation = useMutation({
    mutationFn: () =>
      BotsService.createBot({
        requestBody: {
          name: name.trim() || "현물 그리드 봇",
          bot_type: "spot_grid",
          account_id: accountId,
          symbol: symbol.trim().toUpperCase(),
          investment_amount: investmentAmount.trim(),
          stop_loss_pct: stopLossPct.trim() || undefined,
          take_profit_pct: takeProfitPct.trim() || undefined,
          config: {
            upper: upperPrice.trim(),
            lower: lowerPrice.trim(),
            grid_count: Number(gridCount),
            arithmetic: gridType === "arithmetic",
            amount_per_grid: (
              Number(investmentAmount) / Math.max(1, Number(gridCount))
            ).toFixed(8),
          },
        },
      }),
    onSuccess: () => {
      showSuccessToast("현물 그리드 봇이 생성되었습니다")
      queryClient.invalidateQueries({ queryKey: ["bots"] })
      navigate({ to: "/bots" })
    },
    onError: handleError.bind(showErrorToast),
  })

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    const upper = Number(upperPrice)
    const lower = Number(lowerPrice)
    const grids = Number(gridCount)
    const amount = Number(investmentAmount)

    if (!accountId || !symbol.trim()) {
      showErrorToast("계좌와 거래 쌍을 입력해주세요.")
      return
    }
    if (![upper, lower, grids, amount].every((v) => Number.isFinite(v) && v > 0)) {
      showErrorToast("가격/그리드 수/투자금은 0보다 큰 숫자여야 합니다.")
      return
    }
    if (upper <= lower) {
      showErrorToast("상한가는 하한가보다 커야 합니다.")
      return
    }
    mutation.mutate()
  }

  const spread = useMemo(
    () => Math.max(0, Number(upperPrice) - Number(lowerPrice)),
    [upperPrice, lowerPrice],
  )
  const perGrid = useMemo(() => {
    const count = Number(gridCount)
    if (count <= 0) return 0
    return Number(investmentAmount) / count
  }, [gridCount, investmentAmount])

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <Button
          variant="outline"
          size="sm"
          onClick={() => navigate({ to: "/bots/new" })}
        >
          <ArrowLeft className="mr-2 size-4" />
          이전
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>현물 그리드 봇 만들기</CardTitle>
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
                  placeholder="예) 비트코인 그리드 봇"
                />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>거래 쌍 *</Label>
                <Input
                  value={symbol}
                  onChange={(e) => setSymbol(e.target.value)}
                  placeholder="예) BTC/KRW"
                />
              </div>
              <div className="space-y-2">
                <Label>총 투자 금액 (KRW) *</Label>
                <Input
                  value={investmentAmount}
                  onChange={(e) => setInvestmentAmount(e.target.value)}
                  inputMode="numeric"
                />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>상한가 (KRW)</Label>
                <Input
                  value={upperPrice}
                  onChange={(e) => setUpperPrice(e.target.value)}
                  inputMode="numeric"
                />
              </div>
              <div className="space-y-2">
                <Label>하한가 (KRW)</Label>
                <Input
                  value={lowerPrice}
                  onChange={(e) => setLowerPrice(e.target.value)}
                  inputMode="numeric"
                />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>그리드 수</Label>
                <Input
                  value={gridCount}
                  onChange={(e) => setGridCount(e.target.value)}
                  inputMode="numeric"
                />
              </div>
              <div className="space-y-2">
                <Label>그리드 타입</Label>
                <Select value={gridType} onValueChange={setGridType}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="arithmetic">등간격</SelectItem>
                    <SelectItem value="geometric">등비</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>손절 비율 % (선택)</Label>
                <Input
                  value={stopLossPct}
                  onChange={(e) => setStopLossPct(e.target.value)}
                  placeholder="예) 5"
                />
              </div>
              <div className="space-y-2">
                <Label>목표 수익 자동 종료 % (선택)</Label>
                <Input
                  value={takeProfitPct}
                  onChange={(e) => setTakeProfitPct(e.target.value)}
                  placeholder="예) 10"
                />
              </div>
            </div>

            <div className="rounded-md border bg-muted/30 p-3 text-sm text-muted-foreground">
              예상 정보: 가격 범위 {spread.toLocaleString()} KRW / 그리드당 투자금 {" "}
              {Math.round(perGrid).toLocaleString()} KRW
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
