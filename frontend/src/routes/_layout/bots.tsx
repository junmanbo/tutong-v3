import { useSuspenseQuery } from "@tanstack/react-query"
import {
  Outlet,
  createFileRoute,
  useNavigate,
  useRouterState,
} from "@tanstack/react-router"
import { BookOpen } from "lucide-react"
import { Suspense } from "react"

import { BotsService } from "@/client"
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

function getBotsQueryOptions() {
  return {
    queryFn: () => BotsService.readBots({ skip: 0, limit: 100 }),
    queryKey: ["bots"],
  }
}

export const Route = createFileRoute("/_layout/bots")({
  component: BotsRouteLayout,
  head: () => ({
    meta: [{ title: "트레이딩 봇 - AutoTrade" }],
  }),
})

function BotsTableContent() {
  const { data: bots } = useSuspenseQuery(getBotsQueryOptions())
  const navigate = useNavigate()

  return (
    <DataTable
      columns={columns}
      data={bots.data}
      onRowClick={(bot) =>
        navigate({
          to: "/bots/$botId",
          params: { botId: String(bot.id) },
        })
      }
    />
  )
}

function BotsTable() {
  return (
    <Suspense fallback={<PendingBots />}>
      <BotsTableContent />
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
      <BotsTable />
    </div>
  )
}
