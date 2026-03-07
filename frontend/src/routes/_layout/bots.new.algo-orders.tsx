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

export const Route = createFileRoute("/_layout/bots/new/algo-orders")({
  component: AlgoOrdersBotPage,
  head: () => ({
    meta: [{ title: "Create Algo Orders Bot - AutoTrade" }],
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
  const [quoteAmount, setQuoteAmount] = useState("10000")
  const [baseQty, setBaseQty] = useState("0.1")
  const [algoType, setAlgoType] = useState("twap")
  const [startAt, setStartAt] = useState("")
  const [endAt, setEndAt] = useState("")
  const [sliceCount, setSliceCount] = useState("12")

  const mutation = useMutation({
    mutationFn: () =>
      BotsService.createBot({
        requestBody: {
          name: name.trim() || "Algo Orders Bot",
          bot_type: "algo_orders",
          account_id: accountId,
          symbol: symbol.trim().toUpperCase(),
          investment_amount:
            amountType === "quote" ? quoteAmount.trim() : baseQty.trim(),
          config: {
            side,
            total_qty: amountType === "base" ? baseQty.trim() : undefined,
            total_amount:
              amountType === "quote" ? quoteAmount.trim() : undefined,
            num_slices: Number(sliceCount),
            duration_seconds:
              startAt && endAt
                ? Math.max(
                    60,
                    Math.floor(
                      (new Date(endAt).getTime() -
                        new Date(startAt).getTime()) /
                        1000,
                    ),
                  )
                : 3600,
            order_type: "market",
          },
        },
      }),
    onSuccess: () => {
      showSuccessToast("Algo Orders bot created")
      queryClient.invalidateQueries({ queryKey: ["bots"] })
      navigate({ to: "/bots" })
    },
    onError: handleError.bind(showErrorToast),
  })

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!accountId || !symbol.trim()) {
      showErrorToast("Account and symbol are required.")
      return
    }
    if (amountType === "quote" && !quoteAmount.trim()) {
      showErrorToast("Quote amount is required.")
      return
    }
    if (amountType === "base" && !baseQty.trim()) {
      showErrorToast("Base quantity is required.")
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
        Back
      </Button>

      <Card>
        <CardHeader>
          <CardTitle>Spot Algo Orders (TWAP) 만들기</CardTitle>
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
                  placeholder="BTC TWAP Bot"
                />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-4">
              <div className="space-y-2">
                <Label>Trading Pair *</Label>
                <Input
                  value={symbol}
                  onChange={(e) => setSymbol(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>Order Side</Label>
                <Select value={side} onValueChange={setSide}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="buy">BUY</SelectItem>
                    <SelectItem value="sell">SELL</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Algo Type</Label>
                <Select value={algoType} onValueChange={setAlgoType}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="twap">TWAP</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Slices</Label>
                <Input
                  value={sliceCount}
                  onChange={(e) => setSliceCount(e.target.value)}
                />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <Label>Amount Type</Label>
                <Select value={amountType} onValueChange={setAmountType}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="quote">Quote Amount</SelectItem>
                    <SelectItem value="base">Base Quantity</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {amountType === "quote" ? (
                <div className="space-y-2">
                  <Label>Quote Amount (KRW)</Label>
                  <Input
                    value={quoteAmount}
                    onChange={(e) => setQuoteAmount(e.target.value)}
                  />
                </div>
              ) : (
                <div className="space-y-2">
                  <Label>Base Quantity</Label>
                  <Input
                    value={baseQty}
                    onChange={(e) => setBaseQty(e.target.value)}
                  />
                </div>
              )}
              <div className="space-y-2">
                <Label>Estimated Slice Size</Label>
                <Input
                  value={(
                    Number(amountType === "quote" ? quoteAmount : baseQty) /
                    Math.max(1, Number(sliceCount))
                  ).toString()}
                  readOnly
                />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Start Time</Label>
                <Input
                  type="datetime-local"
                  value={startAt}
                  onChange={(e) => setStartAt(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>End Time</Label>
                <Input
                  type="datetime-local"
                  value={endAt}
                  onChange={(e) => setEndAt(e.target.value)}
                />
              </div>
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
