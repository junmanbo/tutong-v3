import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"

import { BotsService } from "@/client"
import { columns } from "@/components/Bots/columns"
import AddBot from "@/components/Bots/AddBot"
import { DataTable } from "@/components/Common/DataTable"
import PendingBots from "@/components/Pending/PendingBots"

function getBotsQueryOptions() {
  return {
    queryFn: () => BotsService.readBots({ skip: 0, limit: 100 }),
    queryKey: ["bots"],
  }
}

export const Route = createFileRoute("/_layout/bots")({
  component: Bots,
  head: () => ({
    meta: [{ title: "Bots - AutoTrade" }],
  }),
})

function BotsTableContent() {
  const { data: bots } = useSuspenseQuery(getBotsQueryOptions())

  return <DataTable columns={columns} data={bots.data} />
}

function BotsTable() {
  return (
    <Suspense fallback={<PendingBots />}>
      <BotsTableContent />
    </Suspense>
  )
}

function Bots() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Trading Bots</h1>
          <p className="text-muted-foreground">
            Create and manage your automated trading bots
          </p>
        </div>
        <AddBot />
      </div>
      <BotsTable />
    </div>
  )
}
