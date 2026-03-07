import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { Bot, Plus, TrendingUp, Wallet } from "lucide-react"

import { AccountsService, BotsService } from "@/client"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
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

  const accountIds = (accounts?.data ?? []).map((account) => account.id)
  const { data: accountBalances, isLoading: balancesLoading } = useQuery({
    queryKey: ["account-balances", accountIds],
    enabled: accountIds.length > 0,
    queryFn: () =>
      Promise.all(
        accountIds.map((id) =>
          AccountsService.getAccountBalance({
            id,
          }),
        ),
      ),
  })

  const runningBots =
    bots?.data.filter((b) => b.status === "running").length ?? 0
  const pendingBots =
    bots?.data.filter((b) => b.status === "pending").length ?? 0
  const totalBots = bots?.count ?? 0
  const totalAccounts = accounts?.count ?? 0
  const totalPnl = (bots?.data ?? []).reduce(
    (sum, b) => sum + Number(b.total_pnl ?? "0"),
    0,
  )

  const assetTotals = new Map<string, number>()
  ;(accountBalances ?? []).forEach((balances) => {
    balances.forEach((item) => {
      const qty = Number(item.free ?? "0") + Number(item.locked ?? "0")
      if (!Number.isFinite(qty) || qty <= 0) {
        return
      }
      const current = assetTotals.get(item.asset) ?? 0
      assetTotals.set(item.asset, current + qty)
    })
  })

  const totalAssetQty = Array.from(assetTotals.values()).reduce(
    (sum, qty) => sum + qty,
    0,
  )
  const assetColors = [
    "bg-blue-500",
    "bg-emerald-500",
    "bg-amber-500",
    "bg-rose-500",
    "bg-indigo-500",
  ]
  const portfolioAssets = Array.from(assetTotals.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([name, qty], idx) => ({
      name,
      qty,
      weight: totalAssetQty > 0 ? (qty / totalAssetQty) * 100 : 0,
      color: assetColors[idx % assetColors.length],
    }))

  const trend = (bots?.data ?? [])
    .slice()
    .sort(
      (a, b) =>
        new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
    )
    .slice(-7)
    .map((bot) => ({
      label: new Date(bot.created_at).toLocaleDateString(undefined, {
        month: "2-digit",
        day: "2-digit",
      }),
      value: Number(bot.total_pnl ?? "0"),
      name: bot.name,
    }))
  const maxTrendAbs = Math.max(
    ...trend.map((point) => Math.abs(point.value)),
    1,
  )

  const activeBots = (bots?.data ?? []).filter(
    (bot) => bot.status === "running" || bot.status === "pending",
  )

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight truncate max-w-sm">
          Hi, {currentUser?.full_name || currentUser?.email} 👋
        </h1>
        <p className="text-muted-foreground">
          AutoTrade 플랫폼에 오신 것을 환영합니다
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              연결 계좌
            </CardTitle>
            <Wallet className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {accountsLoading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="text-2xl font-bold">{totalAccounts}</div>
            )}
            <p className="text-xs text-muted-foreground mt-1">
              연결된 거래소 수
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">실행 중인 봇</CardTitle>
            <Bot className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {botsLoading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="text-2xl font-bold">{runningBots}</div>
            )}
            <p className="text-xs text-muted-foreground mt-1">
              {pendingBots > 0 ? `${pendingBots}개 시작 대기 중` : "라이브 봇"}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">전체 봇</CardTitle>
            <Bot className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {botsLoading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="text-2xl font-bold">{totalBots}</div>
            )}
            <p className="text-xs text-muted-foreground mt-1">
              실행 + 중지 + 완료 포함
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">수익/손실</CardTitle>
            <TrendingUp className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {botsLoading ? (
              <Skeleton className="h-8 w-24" />
            ) : (
              <div className="text-2xl font-bold">
                {totalPnl >= 0 ? "+" : ""}
                {totalPnl.toFixed(2)}
              </div>
            )}
            <p className="text-xs text-muted-foreground mt-1">
              전체 봇 누적 성과
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>포트폴리오 배분</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {balancesLoading || accountsLoading ? (
              <Skeleton className="h-32 w-full" />
            ) : portfolioAssets.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                잔고 데이터가 없습니다.
              </p>
            ) : (
              portfolioAssets.map((asset) => (
                <div key={asset.name} className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <span>{asset.name}</span>
                    <span className="font-medium">
                      {asset.weight.toFixed(2)}% ({asset.qty.toFixed(6)})
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-muted">
                    <div
                      className={`h-2 rounded-full ${asset.color}`}
                      style={{ width: `${asset.weight}%` }}
                    />
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>수익/손실 추이 (최근 7개 봇)</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {botsLoading ? (
              <Skeleton className="h-32 w-full" />
            ) : trend.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                봇 수익/손실 데이터가 없습니다.
              </p>
            ) : (
              trend.map((point) => {
                const width = (Math.abs(point.value) / maxTrendAbs) * 100
                return (
                  <div
                    key={`${point.label}-${point.name}`}
                    className="space-y-1"
                  >
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>
                        {point.label} · {point.name}
                      </span>
                      <span>
                        {point.value >= 0 ? "+" : ""}
                        {point.value.toFixed(2)}
                      </span>
                    </div>
                    <div className="h-2 rounded-full bg-muted">
                      <div
                        className={`h-2 rounded-full ${
                          point.value >= 0 ? "bg-green-600" : "bg-destructive"
                        }`}
                        style={{ width: `${Math.max(4, width)}%` }}
                      />
                    </div>
                  </div>
                )
              })
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>실행 중인 봇</CardTitle>
          <Link to="/bots/new">
            <Button size="sm">
              <Plus className="mr-2 size-4" />
              봇 추가
            </Button>
          </Link>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>이름</TableHead>
                <TableHead>유형</TableHead>
                <TableHead>수익률</TableHead>
                <TableHead>상태</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {activeBots.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={4}
                    className="text-center text-muted-foreground"
                  >
                    현재 실행 중인 봇이 없습니다.
                  </TableCell>
                </TableRow>
              ) : (
                activeBots.map((bot) => (
                  <TableRow key={bot.id}>
                    <TableCell>{bot.name}</TableCell>
                    <TableCell>{bot.bot_type}</TableCell>
                    <TableCell>
                      {Number(bot.total_pnl_pct).toFixed(2)}%
                    </TableCell>
                    <TableCell className="capitalize">{bot.status}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
