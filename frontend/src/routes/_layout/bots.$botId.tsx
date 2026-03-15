import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router"
import {
  Activity,
  ArrowLeft,
  Clock3,
  Pause,
  PencilLine,
  Play,
  RefreshCw,
  ShieldAlert,
  TrendingUp,
} from "lucide-react"

import { type BotStatusEnum, BotsService, OpenAPI } from "@/client"
import { StopBotDialog } from "@/components/Bots/StopBotDialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import useCustomToast from "@/hooks/useCustomToast"
import { cn } from "@/lib/utils"

const BOT_TYPE_LABELS: Record<string, string> = {
  spot_grid: "현물 그리드",
  position_snowball: "스노우볼",
  rebalancing: "리밸런싱",
  spot_dca: "현물 DCA",
  algo_orders: "알고 주문",
}

const STATUS_STYLES: Record<
  BotStatusEnum,
  {
    variant: "default" | "secondary" | "destructive" | "outline"
    label: string
  }
> = {
  running: { variant: "default", label: "실행 중" },
  pending: { variant: "outline", label: "대기 중" },
  stopped: { variant: "secondary", label: "중지됨" },
  error: { variant: "destructive", label: "오류" },
  completed: { variant: "outline", label: "완료" },
}

export const Route = createFileRoute("/_layout/bots/$botId")({
  component: BotDetailPage,
  head: () => ({
    meta: [{ title: "봇 상세 - AutoTrade" }],
  }),
})

function ValueRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-2">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="font-mono text-sm">{value}</span>
    </div>
  )
}

function formatSignedNumber(value: number, unit = "") {
  const prefix = value >= 0 ? "+" : ""
  return `${prefix}${value.toFixed(2)}${unit}`
}

function formatKrw(value?: string | null) {
  const amount = Number(value ?? "0")
  if (!Number.isFinite(amount)) return "-"
  return `${Math.round(amount).toLocaleString()} KRW`
}

function formatDurationFrom(isoDate: string) {
  const startedAt = new Date(isoDate).getTime()
  const now = Date.now()

  if (Number.isNaN(startedAt)) {
    return "-"
  }

  const diff = Math.max(0, now - startedAt)
  const hours = Math.floor(diff / (1000 * 60 * 60))
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))

  return `${hours}시간 ${minutes}분`
}

type BotOrderItem = {
  id: string
  symbol: string
  side: string
  placed_at: string
}

type BotOrdersResponse = {
  data: BotOrderItem[]
  count: number
}

type BotTradeItem = {
  id: string
  order_id: string
  quantity: string
  price: string
  fee: string
  fee_currency: string | null
  traded_at: string
}

type BotTradesResponse = {
  data: BotTradeItem[]
  count: number
}

type BotSnapshotItem = {
  id: string
  total_pnl: string
  total_pnl_pct: string
  portfolio_value: string
  snapshot_at: string
}

type BotSnapshotsResponse = {
  data: BotSnapshotItem[]
  count: number
}

function formatQuantity(value: string) {
  const n = Number(value)
  if (!Number.isFinite(n)) return "-"
  return n.toLocaleString("ko-KR", { maximumFractionDigits: 8 })
}

function formatUnitPrice(value: string) {
  const n = Number(value)
  if (!Number.isFinite(n)) return "-"
  return n.toLocaleString("ko-KR", { maximumFractionDigits: 8 })
}

function formatAmount(value: number, currency: string | null | undefined) {
  if (!Number.isFinite(value)) return "-"
  const digits = currency?.toUpperCase() === "KRW" ? 0 : 8
  return `${value.toLocaleString("ko-KR", { maximumFractionDigits: digits })} ${currency ?? ""}`.trim()
}

async function fetchAuthedJson<T>(path: string): Promise<T> {
  const accessToken = localStorage.getItem("access_token")
  const response = await fetch(`${OpenAPI.BASE}${path}`, {
    method: "GET",
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
  })
  if (!response.ok) {
    const raw = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null
    throw new Error(raw?.detail ?? "데이터를 불러오지 못했습니다.")
  }
  return (await response.json()) as T
}

function formatSignedPct(value: string) {
  const n = Number(value)
  if (!Number.isFinite(n)) return "-"
  return `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`
}

function BotDetailPage() {
  const { botId } = Route.useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const {
    data: bot,
    isLoading,
    isError,
    isFetching,
    refetch,
    error,
  } = useQuery({
    queryKey: ["bot", botId],
    queryFn: () => BotsService.readBot({ id: botId }),
    refetchInterval: 5000,
    refetchIntervalInBackground: true,
  })
  const { data: botOrders, isLoading: ordersLoading } = useQuery({
    queryKey: ["bot-orders", botId],
    queryFn: () =>
      fetchAuthedJson<BotOrdersResponse>(
        `/api/v1/bots/${botId}/orders?skip=0&limit=100`,
      ),
    refetchInterval: 5000,
    refetchIntervalInBackground: true,
    enabled: !!bot,
  })
  const { data: botTrades, isLoading: tradesLoading } = useQuery({
    queryKey: ["bot-trades", botId],
    queryFn: () =>
      fetchAuthedJson<BotTradesResponse>(
        `/api/v1/bots/${botId}/trades?skip=0&limit=100`,
      ),
    refetchInterval: 5000,
    refetchIntervalInBackground: true,
    enabled: !!bot,
  })
  const { data: botSnapshots, isLoading: snapshotsLoading } = useQuery({
    queryKey: ["bot-snapshots", botId],
    queryFn: () =>
      fetchAuthedJson<BotSnapshotsResponse>(
        `/api/v1/bots/${botId}/snapshots?skip=0&limit=20`,
      ),
    refetchInterval: 10000,
    refetchIntervalInBackground: true,
    enabled: !!bot,
  })

  const startMutation = useMutation({
    mutationFn: () => BotsService.startBot({ id: botId }),
    onSuccess: () => {
      showSuccessToast("봇 실행을 요청했습니다.")
      queryClient.invalidateQueries({ queryKey: ["bot", botId] })
    },
    onError: (error) => {
      showErrorToast(error instanceof Error ? error.message : "봇 실행에 실패했습니다.")
    },
  })

  if (isLoading) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-9 w-40" />
        <Skeleton className="h-28 w-full" />
        <div className="grid gap-4 lg:grid-cols-2">
          <Skeleton className="h-56 w-full" />
          <Skeleton className="h-56 w-full" />
        </div>
      </div>
    )
  }

  if (isError || !bot) {
    return (
      <div className="flex flex-col gap-4">
        <Link to="/bots">
          <Button variant="outline" size="sm">
            <ArrowLeft className="mr-2 size-4" />
            봇 목록으로
          </Button>
        </Link>
        <Card>
          <CardHeader>
            <CardTitle>봇 정보를 불러오지 못했습니다</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            {error instanceof Error ? error.message : "알 수 없는 오류"}
          </CardContent>
        </Card>
      </div>
    )
  }

  const statusMeta = STATUS_STYLES[bot.status]
  const pnlPct = Number(bot.total_pnl_pct ?? "0")
  const pnlValue = Number(bot.total_pnl ?? "0")
  const lastSyncedAt = new Date().toLocaleTimeString()

  const orderById = new Map(
    (botOrders?.data ?? []).map((order) => [order.id, order]),
  )
  const recentTrades = (botTrades?.data ?? []).slice(0, 20).map((trade) => {
    const order = orderById.get(trade.order_id)
    const side = order?.side?.toLowerCase() === "buy" ? "매수" : "매도"
    const quantity = Number(trade.quantity)
    const unitPrice = Number(trade.price)
    const tradeAmount = quantity * unitPrice
    return {
      id: trade.id,
      tradedAt: new Date(trade.traded_at).toLocaleString(),
      symbol: order?.symbol ?? bot.symbol ?? "-",
      side,
      quantity: formatQuantity(trade.quantity),
      unitPrice: formatUnitPrice(trade.price),
      tradeAmount: formatAmount(tradeAmount, bot.quote_currency),
      fee: formatAmount(
        Number(trade.fee),
        trade.fee_currency ?? bot.quote_currency,
      ),
      orderedAt: order ? new Date(order.placed_at).toLocaleString() : "-",
    }
  })
  const canStart = bot.status === "stopped" || bot.status === "error"
  const canStop = bot.status === "running" || bot.status === "pending"
  const snapshotPoints = (botSnapshots?.data ?? [])
    .slice()
    .reverse()
    .map((snapshot) => Number(snapshot.total_pnl_pct))
    .filter((value) => Number.isFinite(value))
  const maxAbsPct =
    snapshotPoints.length > 0
      ? Math.max(...snapshotPoints.map((v) => Math.abs(v)), 0.1)
      : 0.1

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link to="/bots">
          <Button variant="outline" size="sm">
            <ArrowLeft className="mr-2 size-4" />
            봇 목록으로
          </Button>
        </Link>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => startMutation.mutate()}
            disabled={!canStart || startMutation.isPending}
          >
            <Play className="mr-2 size-4" />
            실행
          </Button>
          <StopBotDialog
            bot={bot}
            trigger={
              <Button variant="outline" size="sm" disabled={!canStop}>
                <Pause className="mr-2 size-4" />
                중지
              </Button>
            }
          />
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate({ to: "/bots/new" })}
          >
            <PencilLine className="mr-2 size-4" />
            수정
          </Button>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw
              className={cn("mr-2 size-4", isFetching && "animate-spin")}
            />
            새로고침
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader className="gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <CardTitle className="text-2xl">{bot.name}</CardTitle>
            <p className="text-sm text-muted-foreground mt-1">
              5초마다 실시간 상태 업데이트
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline">
              {BOT_TYPE_LABELS[bot.bot_type] ?? bot.bot_type}
            </Badge>
            <Badge variant={statusMeta.variant}>{statusMeta.label}</Badge>
          </div>
        </CardHeader>
      </Card>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">총 수익/손실</CardTitle>
            <TrendingUp className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p
              className={cn(
                "text-2xl font-semibold font-mono",
                pnlValue > 0
                  ? "text-green-600"
                  : pnlValue < 0
                    ? "text-destructive"
                    : "text-foreground",
              )}
            >
              {formatSignedNumber(pnlValue)}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              ROI {formatSignedNumber(pnlPct, "%")}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">운영 시간</CardTitle>
            <Clock3 className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold font-mono">
              {formatDurationFrom(bot.created_at)}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              봇 생성 시점부터
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              현재 상태
            </CardTitle>
            <Activity className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <Badge variant={statusMeta.variant}>{statusMeta.label}</Badge>
            <p className="text-xs text-muted-foreground mt-2">
              5초마다 업데이트
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">리스크 한도</CardTitle>
            <ShieldAlert className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent className="space-y-1">
            <p className="text-sm">
              손절:{" "}
              <span className="font-mono">{bot.stop_loss_pct ?? "-"}</span>
            </p>
            <p className="text-sm">
              목표수익:{" "}
              <span className="font-mono">{bot.take_profit_pct ?? "-"}</span>
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>성과</CardTitle>
          </CardHeader>
          <CardContent>
            <ValueRow
              label="총 수익/손실"
              value={`${pnlValue >= 0 ? "+" : ""}${bot.total_pnl}`}
            />
            <Separator />
            <ValueRow
              label="총 수익률"
              value={`${pnlPct >= 0 ? "+" : ""}${pnlPct.toFixed(2)}%`}
            />
            <Separator />
            <ValueRow
              label="투자 금액"
              value={formatKrw(bot.investment_amount)}
            />
            <Separator />
            <ValueRow
              label="생성일"
              value={new Date(bot.created_at).toLocaleString()}
            />
            <Separator />
            <ValueRow label="마지막 동기화" value={lastSyncedAt} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>설정 정보</CardTitle>
          </CardHeader>
          <CardContent>
            <ValueRow label="봇 ID" value={bot.id} />
            <Separator />
            <ValueRow label="계좌 ID" value={bot.account_id} />
            <Separator />
            <ValueRow label="종목코드" value={bot.symbol ?? "-"} />
            <Separator />
            <ValueRow label="기준 통화" value={bot.base_currency ?? "-"} />
            <Separator />
            <ValueRow
              label="견적 통화"
              value={bot.quote_currency ?? "-"}
            />
            <Separator />
            <ValueRow label="손절 비율 %" value={bot.stop_loss_pct ?? "-"} />
            <Separator />
            <ValueRow
              label="목표수익 비율 %"
              value={bot.take_profit_pct ?? "-"}
            />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>수익률 추이</CardTitle>
        </CardHeader>
        <CardContent>
          {snapshotsLoading ? (
            <Skeleton className="h-36 w-full" />
          ) : snapshotPoints.length === 0 ? (
            <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
              아직 수익 스냅샷 데이터가 없습니다.
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex h-36 items-end gap-1 rounded-md border bg-muted/20 p-3">
                {snapshotPoints.map((point, idx) => {
                  const ratio = Math.max(Math.abs(point) / maxAbsPct, 0.08)
                  const height = `${Math.round(ratio * 100)}%`
                  return (
                    <div
                      key={`${idx}-${point}`}
                      className={cn(
                        "flex-1 rounded-sm",
                        point >= 0 ? "bg-emerald-500/70" : "bg-red-500/70",
                      )}
                      style={{ height }}
                      title={`${point >= 0 ? "+" : ""}${point.toFixed(2)}%`}
                    />
                  )
                })}
              </div>
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>
                  시작: {formatSignedPct(String(snapshotPoints[0] ?? 0))}
                </span>
                <span>
                  최근:{" "}
                  {formatSignedPct(
                    String(snapshotPoints[snapshotPoints.length - 1] ?? 0),
                  )}
                </span>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4">
        <Card>
          <CardHeader>
            <CardTitle>최근 주문</CardTitle>
          </CardHeader>
          <CardContent>
            {ordersLoading || tradesLoading ? (
              <Skeleton className="h-24 w-full" />
            ) : recentTrades.length === 0 ? (
              <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                최근 실행된 주문이 없습니다.
              </div>
            ) : (
              <div className="overflow-x-auto rounded-md border">
                <table className="w-full min-w-[980px] text-sm">
                  <thead className="bg-muted/40 text-muted-foreground">
                    <tr>
                      <th className="px-3 py-2 text-left font-medium">체결시간</th>
                      <th className="px-3 py-2 text-left font-medium">종목명</th>
                      <th className="px-3 py-2 text-left font-medium">종류</th>
                      <th className="px-3 py-2 text-right font-medium">거래수량</th>
                      <th className="px-3 py-2 text-right font-medium">거래단가</th>
                      <th className="px-3 py-2 text-right font-medium">거래금액</th>
                      <th className="px-3 py-2 text-right font-medium">수수료</th>
                      <th className="px-3 py-2 text-left font-medium">주문시간</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentTrades.map((trade) => (
                      <tr key={trade.id} className="border-t">
                        <td className="px-3 py-2">{trade.tradedAt}</td>
                        <td className="px-3 py-2">{trade.symbol}</td>
                        <td className="px-3 py-2">
                          <Badge
                            variant={trade.side === "매수" ? "default" : "secondary"}
                          >
                            {trade.side}
                          </Badge>
                        </td>
                        <td className="px-3 py-2 text-right font-mono">
                          {trade.quantity}
                        </td>
                        <td className="px-3 py-2 text-right font-mono">
                          {trade.unitPrice}
                        </td>
                        <td className="px-3 py-2 text-right font-mono">
                          {trade.tradeAmount}
                        </td>
                        <td className="px-3 py-2 text-right font-mono">{trade.fee}</td>
                        <td className="px-3 py-2">{trade.orderedAt}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
