import type { ColumnDef } from "@tanstack/react-table"

import type { ExchangeAccountPublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { AccountActionsMenu } from "./AccountActionsMenu"

const EXCHANGE_LABELS: Record<string, string> = {
  binance: "Binance",
  upbit: "Upbit",
  kis: "KIS",
  kiwoom: "Kiwoom",
}

export const columns: ColumnDef<ExchangeAccountPublic>[] = [
  {
    accessorKey: "exchange",
    header: "Exchange",
    cell: ({ row }) => (
      <Badge variant="outline">
        {EXCHANGE_LABELS[row.original.exchange] ?? row.original.exchange}
      </Badge>
    ),
  },
  {
    accessorKey: "label",
    header: "Label",
    cell: ({ row }) => (
      <span className="font-medium">{row.original.label}</span>
    ),
  },
  {
    accessorKey: "is_active",
    header: "Status",
    cell: ({ row }) => (
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "size-2 rounded-full",
            row.original.is_active ? "bg-green-500" : "bg-gray-400",
          )}
        />
        <span className={row.original.is_active ? "" : "text-muted-foreground"}>
          {row.original.is_active ? "Active" : "Inactive"}
        </span>
      </div>
    ),
  },
  {
    accessorKey: "is_valid",
    header: "Valid",
    cell: ({ row }) => (
      <span
        className={cn(
          "text-sm font-medium",
          row.original.is_valid ? "text-green-600" : "text-muted-foreground",
        )}
      >
        {row.original.is_valid ? "✓" : "✗"}
      </span>
    ),
  },
  {
    accessorKey: "created_at",
    header: "Created",
    cell: ({ row }) => (
      <span className="text-muted-foreground text-sm">
        {new Date(row.original.created_at).toLocaleDateString()}
      </span>
    ),
  },
  {
    id: "actions",
    header: () => <span className="sr-only">Actions</span>,
    cell: ({ row }) => (
      <div className="flex justify-end">
        <AccountActionsMenu account={row.original} />
      </div>
    ),
  },
]
