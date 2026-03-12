export type Plan = {
  name: string
  price: string
  features: string[]
  isCurrent?: boolean
}

export const plans: Plan[] = [
  {
    name: "무료",
    price: "월 0원",
    features: ["봇 1개", "거래소 1개", "기본 알림"],
  },
  {
    name: "베이직",
    price: "월 9,900원",
    features: ["봇 5개", "거래소 2개", "이메일 알림", "기본 분석"],
    isCurrent: true,
  },
  {
    name: "프로",
    price: "월 29,900원",
    features: [
      "봇 무제한",
      "모든 거래소",
      "전체 알림",
      "고급 분석",
      "API 액세스",
    ],
  },
]

export const paymentHistory = [
  { date: "2026-03-01", plan: "베이직", amount: "9,900원", status: "결제 완료" },
  { date: "2026-02-01", plan: "베이직", amount: "9,900원", status: "결제 완료" },
  { date: "2026-01-01", plan: "베이직", amount: "9,900원", status: "결제 완료" },
]
