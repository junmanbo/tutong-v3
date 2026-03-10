import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import {
  Activity,
  ArrowLeft,
  Clock3,
  ListOrdered,
  RefreshCw,
  TrendingUp,
} from "lucide-react"

import { type BotStatusEnum, BotsService } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

const BOT_TYPE_LABELS: Record<string, string> = {
  spot_grid: "Spot Grid",
  position_snowball: "Snowball",
  rebalancing: "Rebalancing",
  spot_dca: "Spot DCA",
  algo_orders: "Algo Orders",
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
    meta: [{ title: "Bot Detail - AutoTrade" }],
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

  return `${hours}h ${minutes}m`
}

type TimelineItem = {
  id: string
  title: string
  description: string
  at: string
  tone?: "default" | "success" | "warning" | "danger"
}

function BotDetailPage() {
  const { botId } = Route.useParams()
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
  const { data: botLogs, isLoading: logsLoading } = useQuery({
    queryKey: ["bot-logs", botId],
    queryFn: () => BotsService.readBotLogs({ id: botId, limit: 100, skip: 0 }),
    refetchInterval: 5000,
    refetchIntervalInBackground: true,
    enabled: !!bot,
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

  const recentOrders: TimelineItem[] = (botLogs?.data ?? [])
    .filter(
      (log) =>
        log.level !== "error" &&
        (log.event_type.includes("order") ||
          log.event_type.includes("slice") ||
          log.event_type.includes("filled")),
    )
    .slice(0, 20)
    .map((log) => ({
      id: log.id,
      title: log.event_type.split("_").join(" ").toUpperCase(),
      description: log.message,
      at: new Date(log.created_at).toLocaleString(),
      tone:
        log.level === "error"
          ? "danger"
          : log.level === "warning"
            ? "warning"
            : "success",
    }))

  const toneClassName: Record<NonNullable<TimelineItem["tone"]>, string> = {
    default: "border-border bg-background text-foreground",
    success:
      "border-emerald-200 bg-emerald-50/70 text-emerald-900 dark:border-emerald-900/70 dark:bg-emerald-950/35 dark:text-emerald-100",
    warning:
      "border-amber-200 bg-amber-50/70 text-amber-900 dark:border-amber-900/70 dark:bg-amber-950/35 dark:text-amber-100",
    danger:
      "border-red-200 bg-red-50/70 text-red-900 dark:border-red-900/70 dark:bg-red-950/35 dark:text-red-100",
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link to="/bots">
          <Button variant="outline" size="sm">
            <ArrowLeft className="mr-2 size-4" />
            봇 목록으로
          </Button>
        </Link>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          <RefreshCw
            className={cn("mr-2 size-4", isFetching && "animate-spin")}
          />
          새로고침
        </Button>
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
            <ListOrdered className="size-4 text-muted-foreground" />
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

      <div className="grid gap-4">
        <Card>
          <CardHeader>
            <CardTitle>최근 주문</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {logsLoading ? (
              <Skeleton className="h-24 w-full" />
            ) : recentOrders.length === 0 ? (
              <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                최근 실행된 주문이 없습니다.
              </div>
            ) : (
              recentOrders.map((item) => (
                <div
                  key={item.id}
                  className={cn(
                    "rounded-md border p-3",
                    toneClassName[item.tone ?? "default"],
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-medium">{item.title}</p>
                    <p className="text-xs text-muted-foreground">{item.at}</p>
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground dark:text-slate-300">
                    {item.description}
                  </p>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
