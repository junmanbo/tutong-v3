export type Plan = {
  name: string
  price: string
  features: string[]
  isCurrent?: boolean
}

export const plans: Plan[] = [
  {
    name: "Free",
    price: "0 KRW / mo",
    features: ["봇 1개", "거래소 1개", "기본 알림"],
  },
  {
    name: "Basic",
    price: "9,900 KRW / mo",
    features: ["봇 5개", "거래소 2개", "이메일 알림", "기본 분석"],
    isCurrent: true,
  },
  {
    name: "Pro",
    price: "29,900 KRW / mo",
    features: ["봇 무제한", "모든 거래소", "전체 알림", "고급 분석"],
  },
]

export const paymentHistory = [
  { date: "2026-03-01", plan: "Basic", amount: "9,900 KRW", status: "Paid" },
  { date: "2026-02-01", plan: "Basic", amount: "9,900 KRW", status: "Paid" },
  { date: "2026-01-01", plan: "Basic", amount: "9,900 KRW", status: "Paid" },
]
