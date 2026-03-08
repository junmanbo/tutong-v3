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

export const Route = createFileRoute("/_layout/bots/new/algo-orders")({
  component: AlgoOrdersBotPage,
  head: () => ({
    meta: [{ title: "Spot Algo Orders 봇 생성 - AutoTrade" }],
  }),
})

function AlgoOrdersBotPage() {
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
  const [side, setSide] = useState("buy")
  const [amountType, setAmountType] = useState("quote")
  const [quoteAmount, setQuoteAmount] = useState("10000000")
  const [baseQty, setBaseQty] = useState("0.1")
  const [referencePrice, setReferencePrice] = useState("")
  const [algoType, setAlgoType] = useState("twap")
  const [startAt, setStartAt] = useState("")
  const [endAt, setEndAt] = useState("")
  const [sliceCount, setSliceCount] = useState("12")

  const totalQty = useMemo(() => {
    if (amountType === "base") return Number(baseQty)
    const quote = Number(quoteAmount)
    const price = Number(referencePrice)
    if (!Number.isFinite(quote) || !Number.isFinite(price) || price <= 0) return NaN
    return quote / price
  }, [amountType, baseQty, quoteAmount, referencePrice])

  const durationSeconds = useMemo(() => {
    if (!startAt || !endAt) return 3600
    return Math.max(
      60,
      Math.floor((new Date(endAt).getTime() - new Date(startAt).getTime()) / 1000),
    )
  }, [startAt, endAt])

  const mutation = useMutation({
    mutationFn: () => {
      const totalQtyString = String(totalQty)
      const investmentAmount =
        amountType === "quote"
          ? quoteAmount.trim()
          : Number.isFinite(totalQty) && Number(referencePrice) > 0
            ? String(totalQty * Number(referencePrice))
            : baseQty.trim()

      return BotsService.createBot({
        requestBody: {
          name: name.trim() || "Algo Orders Bot",
          bot_type: "algo_orders",
          account_id: accountId,
          symbol: symbol.trim().toUpperCase(),
          investment_amount: investmentAmount,
          config: {
            side,
            total_qty: totalQtyString,
            total_amount: amountType === "quote" ? quoteAmount.trim() : undefined,
            num_slices: Number(sliceCount),
            duration_seconds: durationSeconds,
            order_type: "market",
            algo_type: algoType,
            start_at: startAt || undefined,
            end_at: endAt || undefined,
          },
        },
      })
    },
    onSuccess: () => {
      showSuccessToast("Spot Algo Orders 봇이 생성되었습니다")
      queryClient.invalidateQueries({ queryKey: ["bots"] })
      navigate({ to: "/bots" })
    },
    onError: handleError.bind(showErrorToast),
  })

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    const slices = Number(sliceCount)

    if (!accountId || !symbol.trim()) {
      showErrorToast("계좌와 거래 쌍을 입력해주세요.")
      return
    }
    if (amountType === "quote" && !quoteAmount.trim()) {
      showErrorToast("금액(원화)을 입력해주세요.")
      return
    }
    if (amountType === "quote" && (!referencePrice || Number(referencePrice) <= 0)) {
      showErrorToast("금액 모드에서는 기준 가격이 필요합니다.")
      return
    }
    if (amountType === "base" && (!baseQty.trim() || Number(baseQty) <= 0)) {
      showErrorToast("수량을 입력해주세요.")
      return
    }
    if (!Number.isFinite(totalQty) || totalQty <= 0) {
      showErrorToast("계산된 총 주문 수량이 올바르지 않습니다.")
      return
    }
    if (!Number.isFinite(slices) || slices <= 0) {
      showErrorToast("분할 주문 수는 0보다 큰 숫자여야 합니다.")
      return
    }
    if (startAt && endAt && new Date(endAt) <= new Date(startAt)) {
      showErrorToast("종료 시간은 시작 시간 이후여야 합니다.")
      return
    }

    mutation.mutate()
  }

  const estimatedSliceQty = useMemo(() => {
    const slices = Number(sliceCount)
    if (!Number.isFinite(totalQty) || !Number.isFinite(slices) || slices <= 0) return 0
    return totalQty / slices
  }, [sliceCount, totalQty])

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
          <CardTitle>Spot Algo Orders 만들기 (TWAP)</CardTitle>
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
                  placeholder="예) BTC TWAP Bot"
                />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <Label>거래 쌍 *</Label>
                <Input value={symbol} onChange={(e) => setSymbol(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>주문 방향</Label>
                <Select value={side} onValueChange={setSide}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="buy">매수 (BUY)</SelectItem>
                    <SelectItem value="sell">매도 (SELL)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>알고리즘 타입</Label>
                <Select value={algoType} onValueChange={setAlgoType}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="twap">TWAP</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <Label>입력 방식</Label>
                <Select value={amountType} onValueChange={setAmountType}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="quote">금액 (KRW)</SelectItem>
                    <SelectItem value="base">수량 (Base)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {amountType === "quote" ? (
                <>
                  <div className="space-y-2">
                    <Label>총 주문 금액 (KRW)</Label>
                    <Input
                      value={quoteAmount}
                      onChange={(e) => setQuoteAmount(e.target.value)}
                      inputMode="numeric"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>기준 가격 (KRW)</Label>
                    <Input
                      value={referencePrice}
                      onChange={(e) => setReferencePrice(e.target.value)}
                      placeholder="예) 95000000"
                      inputMode="numeric"
                    />
                  </div>
                </>
              ) : (
                <div className="space-y-2 md:col-span-2">
                  <Label>총 주문 수량</Label>
                  <Input value={baseQty} onChange={(e) => setBaseQty(e.target.value)} />
                </div>
              )}
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <Label>시작 시간</Label>
                <Input
                  type="datetime-local"
                  value={startAt}
                  onChange={(e) => setStartAt(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>종료 시간</Label>
                <Input
                  type="datetime-local"
                  value={endAt}
                  onChange={(e) => setEndAt(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>분할 주문 수</Label>
                <Input
                  value={sliceCount}
                  onChange={(e) => setSliceCount(e.target.value)}
                  inputMode="numeric"
                />
              </div>
            </div>

            <div className="rounded-md border bg-muted/30 p-3 text-sm text-muted-foreground">
              계산된 총 주문 수량: {Number.isFinite(totalQty) ? totalQty.toFixed(8) : "-"} / 분할당 수량: {" "}
              {Number.isFinite(estimatedSliceQty) ? estimatedSliceQty.toFixed(8) : "-"} / 총 실행 시간: {durationSeconds}초
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
