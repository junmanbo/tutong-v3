import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowLeft, RefreshCw } from "lucide-react"

import { BotsService, type BotStatusEnum } from "@/client"
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
            <ValueRow label="Quote Currency" value={bot.quote_currency ?? "-"} />
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
    </div>
  )
}

