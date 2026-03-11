import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { ArrowLeft, Plus, Trash2 } from "lucide-react"
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

type AssetRow = { symbol: string; weight: string }

export const Route = createFileRoute("/_layout/bots/new/rebalancing")({
  component: RebalancingBotPage,
  head: () => ({
    meta: [{ title: "리밸런싱 봇 생성 - AutoTrade" }],
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
  const [quoteCurrency, setQuoteCurrency] = useState("KRW")
  const [assets, setAssets] = useState<AssetRow[]>([
    { symbol: "BTC", weight: "40" },
    { symbol: "ETH", weight: "30" },
    { symbol: "KRW", weight: "30" },
  ])
  const [rebalanceMode, setRebalanceMode] = useState("time")
  const [rebalanceInterval, setRebalanceInterval] = useState("1w")
  const [deviationPct, setDeviationPct] = useState("5")
  const [investmentAmount, setInvestmentAmount] = useState("5000000")

  const mutation = useMutation({
    mutationFn: () => {
      const cleanedAssets = assets
        .map((row) => ({
          symbol: row.symbol.trim().toUpperCase(),
          weight: row.weight.trim(),
        }))
        .filter((row) => row.symbol && row.weight)

      const assetsMap = Object.fromEntries(
        cleanedAssets.map((row) => [row.symbol, row.weight]),
      )

      const baseAsset =
        cleanedAssets.find((row) => row.symbol !== quoteCurrency.trim().toUpperCase())?.symbol ||
        cleanedAssets[0]?.symbol ||
        quoteCurrency.trim().toUpperCase()

      return BotsService.createBot({
        requestBody: {
          name: name.trim() || "리밸런싱 봇",
          bot_type: "rebalancing",
          account_id: accountId,
          base_currency: baseAsset,
          quote_currency: quoteCurrency.trim().toUpperCase(),
          investment_amount: investmentAmount.trim(),
          config: {
            assets: assetsMap,
            mode: rebalanceMode,
            quote: quoteCurrency.trim().toUpperCase(),
            threshold_pct: rebalanceMode === "deviation" ? deviationPct.trim() : "0",
            interval_seconds:
              rebalanceInterval === "1d"
                ? 86400
                : rebalanceInterval === "1w"
                  ? 604800
                  : 2592000,
          },
        },
      })
    },
    onSuccess: () => {
      showSuccessToast("리밸런싱 봇이 생성되었습니다")
      queryClient.invalidateQueries({ queryKey: ["bots"] })
      navigate({ to: "/bots" })
    },
    onError: handleError.bind(showErrorToast),
  })

  const onChangeAsset = (index: number, key: keyof AssetRow, value: string) => {
    setAssets((prev) =>
      prev.map((row, idx) => (idx === index ? { ...row, [key]: value } : row)),
    )
  }

  const onAddAsset = () => {
    setAssets((prev) => [...prev, { symbol: "", weight: "" }])
  }

  const onRemoveAsset = (index: number) => {
    setAssets((prev) => prev.filter((_, idx) => idx !== index))
  }

  const totalWeight = useMemo(
    () =>
      assets.reduce((sum, row) => {
        const w = Number(row.weight)
        return Number.isFinite(w) ? sum + w : sum
      }, 0),
    [assets],
  )

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    const quote = quoteCurrency.trim().toUpperCase()
    const amount = Number(investmentAmount)
    const threshold = Number(deviationPct)

    const cleanedAssets = assets
      .map((row) => ({
        symbol: row.symbol.trim().toUpperCase(),
        weight: Number(row.weight),
      }))
      .filter((row) => row.symbol)

    if (!accountId || !quote) {
      showErrorToast("계좌와 기준 통화를 입력해주세요.")
      return
    }
    if (!Number.isFinite(amount) || amount <= 0) {
      showErrorToast("총 투자금은 0보다 큰 숫자여야 합니다.")
      return
    }
    if (cleanedAssets.length < 2) {
      showErrorToast("최소 2개 자산 비중을 입력해주세요.")
      return
    }
    if (cleanedAssets.some((row) => !Number.isFinite(row.weight) || row.weight <= 0)) {
      showErrorToast("자산 비중은 0보다 큰 숫자여야 합니다.")
      return
    }
    const hasQuote = cleanedAssets.some((row) => row.symbol === quote)
    if (!hasQuote) {
      showErrorToast("기준 통화 자산을 포트폴리오 구성에 포함해주세요.")
      return
    }
    const sum = cleanedAssets.reduce((acc, row) => acc + row.weight, 0)
    if (Math.abs(sum - 100) > 0.001) {
      showErrorToast("자산 비중 합계는 100이어야 합니다.")
      return
    }
    if (rebalanceMode === "deviation" && (!Number.isFinite(threshold) || threshold <= 0)) {
      showErrorToast("편차 기반 모드에서는 임계값(%)을 입력해주세요.")
      return
    }

    mutation.mutate()
  }

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
          <CardTitle>리밸런싱 봇 만들기</CardTitle>
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
                  placeholder="예) 포트폴리오 리밸런싱 봇"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label>기준 통화</Label>
              <Input
                value={quoteCurrency}
                onChange={(e) => setQuoteCurrency(e.target.value)}
                placeholder="예) KRW"
              />
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label>포트폴리오 구성</Label>
                <Button type="button" variant="outline" size="sm" onClick={onAddAsset}>
                  <Plus className="mr-2 size-4" />
                  자산 추가
                </Button>
              </div>
              <div className="space-y-2">
                {assets.map((row, index) => (
                  <div key={`${index}-${row.symbol}`} className="grid gap-2 md:grid-cols-[1fr_1fr_auto]">
                    <Input
                      value={row.symbol}
                      onChange={(e) => onChangeAsset(index, "symbol", e.target.value)}
                      placeholder="자산 심볼 (예: BTC)"
                    />
                    <Input
                      value={row.weight}
                      onChange={(e) => onChangeAsset(index, "weight", e.target.value)}
                      placeholder="목표 비중 %"
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      onClick={() => onRemoveAsset(index)}
                      disabled={assets.length <= 2}
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </div>
                ))}
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <Label>리밸런싱 방식</Label>
                <Select value={rebalanceMode} onValueChange={setRebalanceMode}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="time">시간 기반</SelectItem>
                    <SelectItem value="deviation">편차 기반</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {rebalanceMode === "time" ? (
                <div className="space-y-2">
                  <Label>리밸런싱 주기</Label>
                  <Select value={rebalanceInterval} onValueChange={setRebalanceInterval}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1d">매일</SelectItem>
                      <SelectItem value="1w">매주</SelectItem>
                      <SelectItem value="1m">매월</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              ) : (
                <div className="space-y-2">
                  <Label>편차 임계값 %</Label>
                  <Input
                    value={deviationPct}
                    onChange={(e) => setDeviationPct(e.target.value)}
                    placeholder="예) 5"
                  />
                </div>
              )}
              <div className="space-y-2">
                <Label>총 투자금 (KRW) *</Label>
                <Input
                  value={investmentAmount}
                  onChange={(e) => setInvestmentAmount(e.target.value)}
                  inputMode="numeric"
                />
              </div>
            </div>

            <div className="rounded-md border bg-muted/30 p-3 text-sm text-muted-foreground">
              자산 비중 합계: {totalWeight}% {Math.abs(totalWeight - 100) < 0.001 ? "✓" : "(100%로 맞춰주세요)"}
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
