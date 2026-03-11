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

export const Route = createFileRoute("/_layout/bots/new/dca")({
  component: DcaBotPage,
  head: () => ({
    meta: [{ title: "현물 DCA 봇 생성 - AutoTrade" }],
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
  const [symbol, setSymbol] = useState("BTC/KRW")
  const [buyAmount, setBuyAmount] = useState("100000")
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
          name: name.trim() || "현물 DCA 봇",
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
            run_mode: runMode,
            buy_time: buyTime,
            end_date: runMode === "date" ? endDate : undefined,
          },
        },
      }),
    onSuccess: () => {
      showSuccessToast("현물 DCA 봇이 생성되었습니다")
      queryClient.invalidateQueries({ queryKey: ["bots"] })
      navigate({ to: "/bots" })
    },
    onError: handleError.bind(showErrorToast),
  })

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    const amount = Number(buyAmount)
    const count = Number(cycles)

    if (!accountId || !symbol.trim()) {
      showErrorToast("계좌와 매수 자산을 입력해주세요.")
      return
    }
    if (!Number.isFinite(amount) || amount <= 0) {
      showErrorToast("1회 매수 금액은 0보다 큰 숫자여야 합니다.")
      return
    }
    if (runMode === "count" && (!Number.isFinite(count) || count <= 0)) {
      showErrorToast("총 매수 횟수는 0보다 큰 숫자여야 합니다.")
      return
    }
    if (runMode === "date" && !endDate) {
      showErrorToast("날짜 지정 모드에서는 종료일이 필요합니다.")
      return
    }

    mutation.mutate()
  }

  const totalPlanned = useMemo(() => {
    if (runMode !== "count") return Number(buyAmount || 0)
    return Number(buyAmount || 0) * Number(cycles || 0)
  }, [buyAmount, cycles, runMode])

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
          <CardTitle>현물 DCA 봇 만들기</CardTitle>
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
                  placeholder="예) 비트코인 DCA 봇"
                />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>매수 자산 *</Label>
                <Input
                  value={symbol}
                  onChange={(e) => setSymbol(e.target.value)}
                  placeholder="예) BTC/KRW"
                />
              </div>
              <div className="space-y-2">
                <Label>1회 매수 금액 (KRW) *</Label>
                <Input
                  value={buyAmount}
                  onChange={(e) => setBuyAmount(e.target.value)}
                  inputMode="numeric"
                />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <Label>매수 주기</Label>
                <Select value={frequency} onValueChange={setFrequency}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="daily">매일</SelectItem>
                    <SelectItem value="weekly">매주</SelectItem>
                    <SelectItem value="monthly">매월</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>매수 시간</Label>
                <Input
                  type="time"
                  value={buyTime}
                  onChange={(e) => setBuyTime(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>운영 모드</Label>
                <Select value={runMode} onValueChange={setRunMode}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="count">횟수 지정</SelectItem>
                    <SelectItem value="date">날짜 지정</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {runMode === "count" ? (
              <div className="space-y-2">
                <Label>총 매수 횟수</Label>
                <Input
                  value={cycles}
                  onChange={(e) => setCycles(e.target.value)}
                  inputMode="numeric"
                />
              </div>
            ) : (
              <div className="space-y-2">
                <Label>종료일</Label>
                <Input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                />
              </div>
            )}

            <div className="space-y-2">
              <Label>목표 수익률 달성 시 종료 % (선택)</Label>
              <Input
                value={takeProfitPct}
                onChange={(e) => setTakeProfitPct(e.target.value)}
              />
            </div>

            <div className="rounded-md border bg-muted/30 p-3 text-sm text-muted-foreground">
              계획 투자금(대략): {Math.round(totalPlanned).toLocaleString()} KRW
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
