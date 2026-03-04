import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Bot, Wallet } from "lucide-react"

import { AccountsService, BotsService } from "@/client"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import useAuth from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  head: () => ({
    meta: [{ title: "Dashboard - AutoTrade" }],
  }),
})

function Dashboard() {
  const { user: currentUser } = useAuth()

  const { data: accounts, isLoading: accountsLoading } = useQuery({
    queryKey: ["accounts"],
    queryFn: () => AccountsService.readAccounts({ skip: 0, limit: 100 }),
  })

  const { data: bots, isLoading: botsLoading } = useQuery({
    queryKey: ["bots"],
    queryFn: () => BotsService.readBots({ skip: 0, limit: 100 }),
  })

  const runningBots =
    bots?.data.filter((b) => b.status === "running").length ?? 0

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight truncate max-w-sm">
          Hi, {currentUser?.full_name || currentUser?.email} 👋
        </h1>
        <p className="text-muted-foreground">
          Welcome back to AutoTrade Platform
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Exchange Accounts
            </CardTitle>
            <Wallet className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {accountsLoading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="text-2xl font-bold">{accounts?.count ?? 0}</div>
            )}
            <p className="text-xs text-muted-foreground mt-1">
              Connected exchanges
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Trading Bots</CardTitle>
            <Bot className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {botsLoading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="text-2xl font-bold">{bots?.count ?? 0}</div>
            )}
            <p className="text-xs text-muted-foreground mt-1">
              {runningBots > 0
                ? `${runningBots} currently running`
                : "No bots running"}
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
