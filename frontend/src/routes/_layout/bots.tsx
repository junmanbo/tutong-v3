import { useSuspenseQuery } from "@tanstack/react-query"
import {
  Outlet,
  createFileRoute,
  useNavigate,
  useRouterState,
} from "@tanstack/react-router"
import { BookOpen } from "lucide-react"
import { Suspense, useMemo, useState } from "react"

import { AccountsService, BotsService } from "@/client"
import AddBot from "@/components/Bots/AddBot"
import { columns } from "@/components/Bots/columns"
import { DataTable } from "@/components/Common/DataTable"
import PendingBots from "@/components/Pending/PendingBots"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"

function getBotsQueryOptions() {
  return {
    queryFn: () => BotsService.readBots({ skip: 0, limit: 100 }),
    queryKey: ["bots"],
  }
}

function getAccountsQueryOptions() {
  return {
    queryFn: () => AccountsService.readAccounts({ skip: 0, limit: 200 }),
    queryKey: ["accounts"],
  }
}

export const Route = createFileRoute("/_layout/bots")({
  component: BotsRouteLayout,
  head: () => ({
    meta: [{ title: "트레이딩 봇 - AutoTrade" }],
  }),
})

function BotsTableContent({
  statusFilter,
  exchangeFilter,
}: {
  statusFilter: "all" | "running" | "stopped" | "completed" | "error"
  exchangeFilter: "all" | "binance" | "upbit" | "kis" | "kiwoom"
}) {
  const { data: bots } = useSuspenseQuery(getBotsQueryOptions())
  const { data: accounts } = useSuspenseQuery(getAccountsQueryOptions())
  const navigate = useNavigate()
  const accountExchangeMap = useMemo(
    () => new Map(accounts.data.map((account) => [account.id, account.exchange])),
    [accounts.data],
  )
  const filteredBots = useMemo(
    () =>
      bots.data.filter((bot) => {
        const statusMatched =
          statusFilter === "all" ? true : bot.status === statusFilter
        const exchange = accountExchangeMap.get(bot.account_id)
        const exchangeMatched =
          exchangeFilter === "all" ? true : exchange === exchangeFilter
        return statusMatched && exchangeMatched
      }),
    [bots.data, statusFilter, exchangeFilter, accountExchangeMap],
  )

  return (
    <DataTable
      columns={columns}
      data={filteredBots}
      onRowClick={(bot) =>
        navigate({
          to: "/bots/$botId",
          params: { botId: String(bot.id) },
        })
      }
    />
  )
}

function BotsTable({
  statusFilter,
  exchangeFilter,
}: {
  statusFilter: "all" | "running" | "stopped" | "completed" | "error"
  exchangeFilter: "all" | "binance" | "upbit" | "kis" | "kiwoom"
}) {
  return (
    <Suspense fallback={<PendingBots />}>
      <BotsTableContent
        statusFilter={statusFilter}
        exchangeFilter={exchangeFilter}
      />
    </Suspense>
  )
}

function BotsRouteLayout() {
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })
  const isBotsListPage = pathname === "/bots"

  if (!isBotsListPage) {
    return <Outlet />
  }

  return <BotsListPage />
}

function BotsListPage() {
  const [statusFilter, setStatusFilter] = useState<
    "all" | "running" | "stopped" | "completed" | "error"
  >("all")
  const [exchangeFilter, setExchangeFilter] = useState<
    "all" | "binance" | "upbit" | "kis" | "kiwoom"
  >("all")
  const botTypeGuide = [
    {
      title: "현물 DCA",
      description: "정해진 주기마다 KRW 기준으로 분할 매수합니다.",
    },
    {
      title: "현물 그리드",
      description: "설정한 가격 범위에서 자동으로 매수/매도를 반복합니다.",
    },
    {
      title: "포지션 스노우볼",
      description: "하락 구간에 분할 매수 후 반등 시 청산합니다.",
    },
    {
      title: "리밸런싱",
      description: "포트폴리오 목표 비중을 KRW 기준으로 자동 재조정합니다.",
    },
    {
      title: "알고 주문",
      description: "대량 주문을 여러 조각으로 나눠 체결 슬리피지를 줄입니다.",
    },
  ]

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">트레이딩 봇</h1>
          <p className="text-muted-foreground">
            자동매매 봇을 생성하고 관리합니다
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Dialog>
            <DialogTrigger asChild>
              <Button variant="outline">
                <BookOpen className="mr-2 size-4" />
                봇 유형 안내
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-lg">
              <DialogHeader>
                <DialogTitle>봇 유형 안내</DialogTitle>
                <DialogDescription>
                  전략별 특징을 확인할 수 있습니다.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-3">
                {botTypeGuide.map((item) => (
                  <div key={item.title} className="rounded-md border p-3">
                    <p className="text-sm font-semibold">{item.title}</p>
                    <p className="mt-1 text-sm text-muted-foreground">{item.description}</p>
                  </div>
                ))}
              </div>
            </DialogContent>
          </Dialog>
          <AddBot />
        </div>
      </div>
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <Tabs
          value={statusFilter}
          onValueChange={(value) =>
            setStatusFilter(
              value as "all" | "running" | "stopped" | "completed" | "error",
            )
          }
        >
          <TabsList>
            <TabsTrigger value="all">전체</TabsTrigger>
            <TabsTrigger value="running">실행 중</TabsTrigger>
            <TabsTrigger value="stopped">중지</TabsTrigger>
            <TabsTrigger value="completed">완료</TabsTrigger>
            <TabsTrigger value="error">오류</TabsTrigger>
          </TabsList>
        </Tabs>
        <Select
          value={exchangeFilter}
          onValueChange={(value) =>
            setExchangeFilter(
              value as "all" | "binance" | "upbit" | "kis" | "kiwoom",
            )
          }
        >
          <SelectTrigger className="w-full lg:w-[220px]">
            <SelectValue placeholder="거래소 필터" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">전체 거래소</SelectItem>
            <SelectItem value="binance">바이낸스</SelectItem>
            <SelectItem value="upbit">업비트</SelectItem>
            <SelectItem value="kis">한국투자증권</SelectItem>
            <SelectItem value="kiwoom">키움증권</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <BotsTable statusFilter={statusFilter} exchangeFilter={exchangeFilter} />
    </div>
  )
}
