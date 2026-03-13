import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowLeft, CircleCheckBig } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

type BotGuide = {
  title: string
  summary: string
  howItWorks: string[]
  inputs: Array<{ name: string; role: string }>
  scenario: string[]
}

const BOT_GUIDES: Record<string, BotGuide> = {
  dca: {
    title: "현물 DCA",
    summary:
      "정해진 주기마다 같은 금액을 나눠 매수해 평균 매입단가를 관리하는 전략입니다.",
    howItWorks: [
      "봇이 interval_seconds(주기)마다 현재가를 조회합니다.",
      "amount_per_order(1회 매수금액) 기준으로 주문 수량을 계산합니다.",
      "total_orders(총 횟수)에 도달하면 자동으로 종료됩니다.",
      "목표수익/손절이 설정되면 조건 충족 시 자동 종료됩니다.",
    ],
    inputs: [
      { name: "종목(symbol)", role: "매수할 코인/자산 (예: SOL/KRW)" },
      { name: "1회 매수금액(amount_per_order)", role: "매 주기마다 투입할 KRW 금액" },
      { name: "매수 주기(interval_seconds)", role: "주문 실행 간격 (초)" },
      { name: "총 매수 횟수(total_orders)", role: "전체 반복 횟수" },
      { name: "주문 타입(order_type)", role: "시장가/지정가 등 주문 방식" },
    ],
    scenario: [
      "예: SOL/KRW, 1회 10,000원, 1시간 주기, 총 10회",
      "1시간마다 10,000원씩 자동 매수해 총 100,000원 분할 매수",
      "중간에 급락해도 동일 금액 매수로 평균단가를 완화",
      "10회 완료 또는 리스크 조건 충족 시 종료",
    ],
  },
  "spot-grid": {
    title: "현물 그리드",
    summary:
      "가격 구간을 격자(그리드)로 나눠 하단 매수·상단 매도를 반복하는 횡보장 전략입니다.",
    howItWorks: [
      "upper/lower와 grid_count로 가격 레벨을 생성합니다.",
      "현재가 아래 레벨에 매수 주문을 배치합니다.",
      "매수 체결 시 위 레벨 매도 주문을 배치해 차익을 노립니다.",
      "시세가 레벨 사이를 왕복할수록 반복 체결됩니다.",
    ],
    inputs: [
      { name: "가격 상단(upper)", role: "전략 상한 가격" },
      { name: "가격 하단(lower)", role: "전략 하한 가격" },
      { name: "그리드 수(grid_count)", role: "가격 구간 분할 개수" },
      { name: "간격 타입(arithmetic/geometric)", role: "등차/등비 간격 방식" },
      { name: "그리드당 금액(amount_per_grid)", role: "각 레벨 주문 금액" },
    ],
    scenario: [
      "예: BTC/KRW, 하단 90,000,000 / 상단 120,000,000, 20그리드",
      "95,000,000에서 매수 체결되면 96,500,000 인근 매도 대기",
      "가격이 다시 오르면 매도 체결, 수익 실현",
      "가격이 범위 내에서 횡보할수록 다회전 체결",
    ],
  },
  snowball: {
    title: "포지션 스노우볼",
    summary:
      "하락 시 분할 매수를 누적해 평균단가를 낮추고, 반등 시 목표수익에서 정리하는 전략입니다.",
    howItWorks: [
      "초기 진입 후 drop_pct 하락마다 추가 매수를 검토합니다.",
      "amount_per_buy와 multiplier에 따라 추가 매수 규모를 조정합니다.",
      "max_buys 범위 내에서만 레이어를 늘립니다.",
      "평균단가 대비 목표수익률 도달 시 정리합니다.",
    ],
    inputs: [
      { name: "하락 트리거(drop_pct)", role: "추가 매수를 트리거할 하락률" },
      { name: "기본 매수금액(amount_per_buy)", role: "1차/기본 매수 금액" },
      { name: "최대 매수 횟수(max_buys)", role: "레이어 수 상한" },
      { name: "배수(multiplier)", role: "추가 매수 시 금액 증가 배수" },
      { name: "목표수익률(take_profit_pct)", role: "정리 기준 수익률" },
    ],
    scenario: [
      "예: 1차 50,000원, -5%마다 추가, 최대 4회, 배수 1.5",
      "하락 구간에서 50,000 → 75,000 → 112,500 식으로 누적",
      "평균단가가 내려간 상태에서 반등 시 목표수익 도달 가능성 증가",
      "목표수익 도달 시 포지션 정리",
    ],
  },
  rebalancing: {
    title: "리밸런싱",
    summary:
      "여러 자산의 목표 비중을 유지하도록 주기적 또는 편차 기준으로 자동 재조정하는 전략입니다.",
    howItWorks: [
      "assets와 target_weight로 목표 포트폴리오를 정의합니다.",
      "현재 비중과 목표 비중의 차이를 계산합니다.",
      "mode가 time이면 interval_seconds마다, deviation이면 threshold_pct 초과 시 실행합니다.",
      "부족 자산 매수 / 과다 자산 매도로 비중을 다시 맞춥니다.",
    ],
    inputs: [
      { name: "자산 목록(assets)", role: "운용할 종목 집합 (최소 2개)" },
      { name: "목표 비중(target weights)", role: "각 자산 목표 %, 합계 100%" },
      { name: "실행 방식(mode)", role: "시간 기반(time) 또는 편차 기반(deviation)" },
      { name: "주기(interval_seconds)", role: "time 모드 실행 간격" },
      { name: "편차 임계값(threshold_pct)", role: "deviation 모드 트리거 기준" },
    ],
    scenario: [
      "예: BTC 50%, ETH 30%, KRW 20%",
      "상승으로 BTC 비중이 62%가 되면 BTC 일부 매도",
      "ETH/KRW를 매수해 목표 비중으로 복귀",
      "장기적으로 과열 자산 비중을 줄이고 균형 유지",
    ],
  },
  "algo-orders": {
    title: "알고 주문(TWAP)",
    summary:
      "대량 주문을 일정 시간 동안 잘게 나눠 체결해 시장 충격과 슬리피지를 낮추는 전략입니다.",
    howItWorks: [
      "total_qty를 num_slices로 분할해 슬라이스 수량을 계산합니다.",
      "duration_seconds를 기준으로 슬라이스 간격을 정합니다.",
      "각 간격마다 한 조각씩 주문을 실행합니다.",
      "모든 슬라이스가 완료되면 자동 종료됩니다.",
    ],
    inputs: [
      { name: "주문 방향(side)", role: "매수 또는 매도" },
      { name: "총 수량(total_qty)", role: "전체 집행 수량" },
      { name: "분할 횟수(num_slices)", role: "몇 조각으로 나눌지" },
      { name: "총 실행시간(duration_seconds)", role: "전체 집행 기간" },
      { name: "주문 타입(order_type)", role: "시장가/지정가 등 주문 방식" },
    ],
    scenario: [
      "예: 2 SOL를 1시간 동안 12회 분할 매수",
      "5분마다 약 0.166 SOL씩 순차 매수",
      "한 번에 큰 주문을 넣는 것보다 평균 체결가 안정화 기대",
      "12회 완료 시 자동 종료",
    ],
  },
}

export const Route = createFileRoute("/_layout/bots/guide/$botType")({
  component: BotGuideDetailPage,
  head: () => ({
    meta: [{ title: "봇 유형 상세 안내 - AutoTrade" }],
  }),
})

function BotGuideDetailPage() {
  const { botType } = Route.useParams()
  const guide = BOT_GUIDES[botType]

  if (!guide) {
    return (
      <div className="flex flex-col gap-4">
        <Link to="/bots">
          <Button variant="outline" size="sm">
            <ArrowLeft className="mr-2 size-4" />
            봇 목록으로
          </Button>
        </Link>
        <Card>
          <CardHeader>
            <CardTitle>지원하지 않는 봇 유형입니다</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            봇 유형 안내에서 다시 선택해주세요.
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-3">
        <Link to="/bots">
          <Button variant="outline" size="sm">
            <ArrowLeft className="mr-2 size-4" />
            봇 목록으로
          </Button>
        </Link>
      </div>

      <div>
        <h1 className="text-2xl font-bold tracking-tight">{guide.title} 상세 안내</h1>
        <p className="mt-2 text-muted-foreground">{guide.summary}</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>기본 동작 방식</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {guide.howItWorks.map((item) => (
            <p key={item} className="flex items-start gap-2 text-sm">
              <CircleCheckBig className="mt-0.5 size-4 text-primary" />
              <span>{item}</span>
            </p>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>입력값과 역할</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {guide.inputs.map((item) => (
            <div key={item.name} className="rounded-md border p-3">
              <p className="text-sm font-semibold">{item.name}</p>
              <p className="mt-1 text-sm text-muted-foreground">{item.role}</p>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>예시 매매 시나리오</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {guide.scenario.map((item) => (
            <p key={item} className="text-sm text-muted-foreground">
              {item}
            </p>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
