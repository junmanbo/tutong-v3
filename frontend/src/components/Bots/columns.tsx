import { Link } from "@tanstack/react-router"
import type { ColumnDef } from "@tanstack/react-table"

import type { BotPublic, BotStatusEnum } from "@/client"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { BotActionsMenu } from "./BotActionsMenu"

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

const formatKrw = (value?: string | null): string => {
  const amount = Number(value ?? "0")
  if (!Number.isFinite(amount)) return "-"
  return `${Math.round(amount).toLocaleString()} KRW`
}

export const columns: ColumnDef<BotPublic>[] = [
  {
    accessorKey: "name",
    header: "이름",
    cell: ({ row }) => (
      <Link
        to="/bots/$botId"
        params={{ botId: row.original.id }}
        className="font-medium hover:underline"
      >
        {row.original.name}
      </Link>
    ),
  },
  {
    accessorKey: "bot_type",
    header: "유형",
    cell: ({ row }) => (
      <Badge variant="outline">
        {BOT_TYPE_LABELS[row.original.bot_type] ?? row.original.bot_type}
      </Badge>
    ),
  },
  {
    accessorKey: "symbol",
    header: "종목",
    cell: ({ row }) => (
      <span className="text-muted-foreground">
        {row.original.symbol ?? "-"}
      </span>
    ),
  },
  {
    accessorKey: "investment_amount",
    header: "투자금액",
    cell: ({ row }) => (
      <span className="font-mono text-sm">
        {row.original.investment_amount ? formatKrw(row.original.investment_amount) : "-"}
      </span>
    ),
  },
  {
    accessorKey: "status",
    header: "상태",
    cell: ({ row }) => {
      const s = STATUS_STYLES[row.original.status]
      return <Badge variant={s.variant}>{s.label}</Badge>
    },
  },
  {
    accessorKey: "total_pnl_pct",
    header: "수익률",
    cell: ({ row }) => {
      const pct = parseFloat(row.original.total_pnl_pct ?? "0")
      return (
        <span
          className={cn(
            "font-mono text-sm font-medium",
            pct > 0
              ? "text-green-600"
              : pct < 0
                ? "text-destructive"
                : "text-muted-foreground",
          )}
        >
          {pct >= 0 ? "+" : ""}
          {pct.toFixed(2)}%
        </span>
      )
    },
  },
  {
    id: "actions",
    header: () => <span className="sr-only">Actions</span>,
    cell: ({ row }) => (
      <div className="flex justify-end">
        <BotActionsMenu bot={row.original} />
      </div>
    ),
  },
]
