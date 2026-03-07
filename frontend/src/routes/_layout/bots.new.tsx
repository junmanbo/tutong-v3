import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowLeft, ChartColumnIncreasing, Gauge, Scale, Snowflake, Target } from "lucide-react"

import AddBot from "@/components/Bots/AddBot"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

const botTypes = [
  {
    title: "Spot Grid",
    icon: ChartColumnIncreasing,
    description: "설정한 가격 범위에서 자동 반복 매매",
    fit: "적합: 횡보장",
    to: "/bots/new/spot-grid",
  },
  {
    title: "Position Snowball",
    icon: Snowflake,
    description: "가격 하락 시 분할 매수로 단가를 조정",
    fit: "적합: 하락 후 반등",
    to: "/bots/new/snowball",
  },
  {
    title: "Rebalancing",
    icon: Scale,
    description: "포트폴리오 목표 비중을 자동 유지",
    fit: "적합: 장기 보유",
    to: "/bots/new/rebalancing",
  },
  {
    title: "Spot DCA",
    icon: Gauge,
    description: "정기적으로 일정 금액을 자동 매수",
    fit: "적합: 장기 투자",
    to: "/bots/new/dca",
  },
  {
    title: "Spot Algo Orders",
    icon: Target,
    description: "대량 주문을 분할 실행해 슬리피지 최소화",
    fit: "적합: 대규모 매매",
    to: "/bots/new/algo-orders",
  },
]

export const Route = createFileRoute("/_layout/bots/new")({
  component: BotsNewPage,
  head: () => ({
    meta: [{ title: "Create Bot - AutoTrade" }],
  }),
})

function BotsNewPage() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <Link to="/bots">
          <Button variant="outline" size="sm">
            <ArrowLeft className="mr-2 size-4" />
            Back to Bots
          </Button>
        </Link>
        <AddBot />
      </div>

      <div>
        <h1 className="text-2xl font-bold tracking-tight">어떤 봇을 만들까요?</h1>
        <p className="text-muted-foreground">
          전략 유형을 확인한 뒤 우측 상단 버튼으로 새 봇을 생성하세요.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {botTypes.map((bot) => (
          <Card key={bot.title}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <bot.icon className="size-5 text-primary" />
                {bot.title}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <p className="text-sm text-muted-foreground">{bot.description}</p>
              <p className="text-sm font-medium">{bot.fit}</p>
              <Link to={bot.to} className="inline-block pt-2">
                <Button size="sm" variant="outline">
                  선택하기
                </Button>
              </Link>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
