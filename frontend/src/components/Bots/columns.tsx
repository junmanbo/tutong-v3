import type { ColumnDef } from "@tanstack/react-table"
import { Link } from "@tanstack/react-router"

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
  running: { variant: "default", label: "Running" },
  pending: { variant: "outline", label: "Pending" },
  stopped: { variant: "secondary", label: "Stopped" },
  error: { variant: "destructive", label: "Error" },
  completed: { variant: "outline", label: "Completed" },
}

export const columns: ColumnDef<BotPublic>[] = [
  {
    accessorKey: "name",
    header: "Name",
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
    header: "Type",
    cell: ({ row }) => (
      <Badge variant="outline">
        {BOT_TYPE_LABELS[row.original.bot_type] ?? row.original.bot_type}
      </Badge>
    ),
  },
  {
    accessorKey: "symbol",
    header: "Symbol",
    cell: ({ row }) => (
      <span className="text-muted-foreground">
        {row.original.symbol ?? "-"}
      </span>
    ),
  },
  {
    accessorKey: "investment_amount",
    header: "Investment",
    cell: ({ row }) => (
      <span className="font-mono text-sm">
        {row.original.investment_amount
          ? `${row.original.investment_amount} USDT`
          : "-"}
      </span>
    ),
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => {
      const s = STATUS_STYLES[row.original.status]
      return <Badge variant={s.variant}>{s.label}</Badge>
    },
  },
  {
    accessorKey: "total_pnl_pct",
    header: "P&L",
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
