export const UPBIT_MIN_ORDER_KRW = 5000

export const isKrwSymbol = (symbol: string) =>
  symbol.trim().toUpperCase().endsWith("/KRW")

export const isUpbitExchange = (exchange?: string | null) =>
  exchange?.toLowerCase() === "upbit"

export const isUpbitKrwMarket = (
  exchange: string | null | undefined,
  symbol: string,
) => isUpbitExchange(exchange) && isKrwSymbol(symbol)

export const getUpbitMinOrderMessage = (
  orderValueKrw: number,
  label: string,
) => {
  if (!Number.isFinite(orderValueKrw) || orderValueKrw <= 0) return null
  if (orderValueKrw >= UPBIT_MIN_ORDER_KRW) return null
  return `업비트 KRW 마켓은 ${label}이 최소 ${UPBIT_MIN_ORDER_KRW.toLocaleString()} KRW 이상이어야 합니다. 현재 ${Math.round(orderValueKrw).toLocaleString()} KRW`
}
