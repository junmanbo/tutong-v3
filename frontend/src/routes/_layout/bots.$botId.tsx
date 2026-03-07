import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import {
  Activity,
  ArrowLeft,
  Clock3,
  ListOrdered,
  RefreshCw,
  ScrollText,
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
  running: { variant: "default", label: "Running" },
  pending: { variant: "outline", label: "Pending" },
  stopped: { variant: "secondary", label: "Stopped" },
  error: { variant: "destructive", label: "Error" },
  completed: { variant: "outline", label: "Completed" },
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
            Back to Bots
          </Button>
        </Link>
        <Card>
          <CardHeader>
            <CardTitle>Failed to load bot</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            {error instanceof Error ? error.message : "Unknown error"}
          </CardContent>
        </Card>
      </div>
    )
  }

  const statusMeta = STATUS_STYLES[bot.status]
  const pnlPct = Number(bot.total_pnl_pct ?? "0")
  const pnlValue = Number(bot.total_pnl ?? "0")
  const lastSyncedAt = new Date().toLocaleTimeString()

  const systemTimeline: TimelineItem[] = [
    {
      id: "created",
      title: "Bot created",
      description: "Initial configuration saved and ready for operation.",
      at: new Date(bot.created_at).toLocaleString(),
      tone: "default",
    },
    {
      id: "status",
      title: `Status: ${statusMeta.label}`,
      description:
        bot.status === "running"
          ? "Bot is actively processing strategy cycles."
          : bot.status === "pending"
            ? "Bot start requested and waiting for worker pickup."
            : bot.status === "error"
              ? "Bot requires manual check before restarting."
              : "Bot is currently not processing new cycles.",
      at: `Last synced ${lastSyncedAt}`,
      tone:
        bot.status === "running"
          ? "success"
          : bot.status === "pending"
            ? "warning"
            : bot.status === "error"
              ? "danger"
              : "default",
    },
  ]

  const recentOrders: TimelineItem[] = (botLogs?.data ?? [])
    .filter(
      (log) =>
        log.event_type.includes("order") ||
        log.event_type.includes("slice") ||
        log.event_type.includes("filled"),
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

  const recentLogs: TimelineItem[] = (botLogs?.data ?? [])
    .filter((log) => !recentOrders.some((orderLog) => orderLog.id === log.id))
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
            : "default",
    }))

  const toneClassName: Record<NonNullable<TimelineItem["tone"]>, string> = {
    default: "border-border bg-background",
    success: "border-emerald-200 bg-emerald-50/60 dark:border-emerald-900",
    warning: "border-amber-200 bg-amber-50/60 dark:border-amber-900",
    danger: "border-red-200 bg-red-50/60 dark:border-red-900",
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link to="/bots">
          <Button variant="outline" size="sm">
            <ArrowLeft className="mr-2 size-4" />
            Back to Bots
          </Button>
        </Link>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          <RefreshCw
            className={cn("mr-2 size-4", isFetching && "animate-spin")}
          />
          Refresh
        </Button>
      </div>

      <Card>
        <CardHeader className="gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <CardTitle className="text-2xl">{bot.name}</CardTitle>
            <p className="text-sm text-muted-foreground mt-1">
              Live status updates every 5 seconds
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
            <CardTitle className="text-sm font-medium">Total P&L</CardTitle>
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
            <CardTitle className="text-sm font-medium">Run Time</CardTitle>
            <Clock3 className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold font-mono">
              {formatDurationFrom(bot.created_at)}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Since bot creation
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Current Status
            </CardTitle>
            <Activity className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <Badge variant={statusMeta.variant}>{statusMeta.label}</Badge>
            <p className="text-xs text-muted-foreground mt-2">
              Updated every 5 seconds
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Risk Limits</CardTitle>
            <ListOrdered className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent className="space-y-1">
            <p className="text-sm">
              Stop Loss:{" "}
              <span className="font-mono">{bot.stop_loss_pct ?? "-"}</span>
            </p>
            <p className="text-sm">
              Take Profit:{" "}
              <span className="font-mono">{bot.take_profit_pct ?? "-"}</span>
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Performance</CardTitle>
          </CardHeader>
          <CardContent>
            <ValueRow
              label="Total P&L"
              value={`${pnlValue >= 0 ? "+" : ""}${bot.total_pnl}`}
            />
            <Separator />
            <ValueRow
              label="Total P&L %"
              value={`${pnlPct >= 0 ? "+" : ""}${pnlPct.toFixed(2)}%`}
            />
            <Separator />
            <ValueRow
              label="Investment Amount"
              value={`${bot.investment_amount ?? "-"} USDT`}
            />
            <Separator />
            <ValueRow
              label="Created At"
              value={new Date(bot.created_at).toLocaleString()}
            />
            <Separator />
            <ValueRow label="Last Synced" value={lastSyncedAt} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Configuration</CardTitle>
          </CardHeader>
          <CardContent>
            <ValueRow label="Bot ID" value={bot.id} />
            <Separator />
            <ValueRow label="Account ID" value={bot.account_id} />
            <Separator />
            <ValueRow label="Symbol" value={bot.symbol ?? "-"} />
            <Separator />
            <ValueRow label="Base Currency" value={bot.base_currency ?? "-"} />
            <Separator />
            <ValueRow
              label="Quote Currency"
              value={bot.quote_currency ?? "-"}
            />
            <Separator />
            <ValueRow label="Stop Loss %" value={bot.stop_loss_pct ?? "-"} />
            <Separator />
            <ValueRow
              label="Take Profit %"
              value={bot.take_profit_pct ?? "-"}
            />
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Recent Orders</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {logsLoading ? (
              <Skeleton className="h-24 w-full" />
            ) : recentOrders.length === 0 ? (
              <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                No recent order executions yet.
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
                  <p className="mt-1 text-sm text-muted-foreground">
                    {item.description}
                  </p>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Log Timeline</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {logsLoading ? (
              <Skeleton className="h-24 w-full" />
            ) : (
              [...systemTimeline, ...recentLogs].map((item) => (
                <div
                  key={item.id}
                  className={cn(
                    "rounded-md border p-3",
                    toneClassName[item.tone ?? "default"],
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <ScrollText className="size-4 text-muted-foreground" />
                      <p className="text-sm font-medium">{item.title}</p>
                    </div>
                    <p className="text-xs text-muted-foreground">{item.at}</p>
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">
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
