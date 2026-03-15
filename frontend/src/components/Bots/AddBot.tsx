import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Plus, Trash2 } from "lucide-react"
import { useMemo, useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import {
  AccountsService,
  type BotCreate,
  BotsService,
  type BotTypeEnum,
} from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  getUpbitMinOrderMessage,
  isUpbitKrwMarket,
} from "@/lib/upbit-order-rules"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const requiredNumberField = (message: string) =>
  z
    .string()
    .min(1, { message })
    .refine((val) => !Number.isNaN(Number(val)) && Number(val) > 0, {
      message: "0보다 큰 숫자를 입력해주세요",
    })

const optionalNumberField = z
  .string()
  .optional()
  .refine(
    (val) => val === undefined || val === "" || !Number.isNaN(Number(val)),
    {
      message: "유효한 숫자를 입력해주세요",
    },
  )

const DEFAULT_REBALANCING_ASSETS = "BTC:50, KRW:50"

const parseRebalancingAssetsInput = (value?: string) => {
  if (!value) return []
  return value
    .split(/[\n,]+/)
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => {
      const [symbolRaw, weightRaw] = item.split(":")
      return {
        symbol: (symbolRaw ?? "").trim().toUpperCase(),
        weight: (weightRaw ?? "").trim(),
      }
    })
    .filter((item) => item.symbol && item.weight)
}

const buildRebalancingAssetsInput = (
  rows: Array<{ symbol: string; weight: string }>,
) =>
  rows
    .map((row) => `${row.symbol.trim().toUpperCase()}:${row.weight.trim()}`)
    .filter((row) => row !== ":")
    .join(", ")

const formSchema = z
  .object({
    name: z
      .string()
      .min(1, { message: "봇 이름을 입력해주세요" })
      .max(100, { message: "봇 이름은 최대 100자까지 입력 가능합니다" }),
    bot_type: z.enum([
      "spot_grid",
      "position_snowball",
      "rebalancing",
      "spot_dca",
      "algo_orders",
    ]),
    symbol: z.string().optional(),
    base_currency: z.string().optional(),
    quote_currency: z.string().optional(),
    investment_amount: requiredNumberField("투자 금액을 입력해주세요"),
    grid_upper_price: z.string().optional(),
    grid_lower_price: z.string().optional(),
    grid_count: z.string().optional(),
    grid_type: z.enum(["arithmetic", "geometric"]).optional(),
    snow_drop_pct: z.string().optional(),
    snow_multiplier: z.string().optional(),
    snow_max_buys: z.string().optional(),
    rebal_assets_input: z.string().optional(),
    rebal_mode: z.enum(["time", "deviation"]).optional(),
    rebal_interval: z.enum(["1d", "1w", "1m"]).optional(),
    rebal_threshold_pct: z.string().optional(),
    dca_frequency: z.enum(["daily", "weekly", "monthly"]).optional(),
    dca_total_orders: z.string().optional(),
    algo_side: z.enum(["buy", "sell"]).optional(),
    algo_total_qty: z.string().optional(),
    algo_num_slices: z.string().optional(),
    algo_duration_seconds: z.string().optional(),
    stop_loss_pct: optionalNumberField,
    take_profit_pct: optionalNumberField,
    account_id: z.string().min(1, { message: "계좌를 선택해주세요" }),
  })
  .superRefine((data, ctx) => {
    const requirePositive = (value: string | undefined, path: (string | number)[], label: string) => {
      if (!value?.trim()) {
        ctx.addIssue({ code: "custom", path, message: `${label}을(를) 입력해주세요` })
        return
      }
      if (Number.isNaN(Number(value)) || Number(value) <= 0) {
        ctx.addIssue({ code: "custom", path, message: `${label}은(는) 0보다 커야 합니다` })
      }
    }

    if (data.bot_type === "rebalancing") {
      if (!data.quote_currency?.trim()) {
        ctx.addIssue({
          code: "custom",
          path: ["quote_currency"],
          message: "리밸런싱에는 견적 통화가 필요합니다",
        })
      }
      const quote = data.quote_currency?.trim().toUpperCase()
      const assets = parseRebalancingAssetsInput(data.rebal_assets_input)
      if (assets.length < 2) {
        ctx.addIssue({
          code: "custom",
          path: ["rebal_assets_input"],
          message: "리밸런싱은 최소 2개 자산 비중이 필요합니다",
        })
      }
      const hasInvalidWeight = assets.some(
        (item) => Number.isNaN(Number(item.weight)) || Number(item.weight) <= 0,
      )
      if (hasInvalidWeight) {
        ctx.addIssue({
          code: "custom",
          path: ["rebal_assets_input"],
          message: "자산 비중은 0보다 큰 숫자로 입력해주세요",
        })
      }
      const totalWeight = assets.reduce((sum, item) => sum + Number(item.weight), 0)
      if (assets.length > 0 && Math.abs(totalWeight - 100) > 0.001) {
        ctx.addIssue({
          code: "custom",
          path: ["rebal_assets_input"],
          message: "자산 비중 합계는 100이어야 합니다",
        })
      }
      if (quote && !assets.some((item) => item.symbol === quote)) {
        ctx.addIssue({
          code: "custom",
          path: ["rebal_assets_input"],
          message: "견적 통화 자산을 포트폴리오에 포함해주세요",
        })
      }
      if (data.rebal_mode === "deviation") {
        requirePositive(
          data.rebal_threshold_pct,
          ["rebal_threshold_pct"],
          "편차 임계값(%)",
        )
      }
      return
    }

    if (!data.symbol?.trim()) {
      ctx.addIssue({
        code: "custom",
        path: ["symbol"],
        message: "이 전략에는 종목코드(심볼)가 필요합니다",
      })
    }

    if (data.bot_type === "spot_grid") {
      requirePositive(data.grid_upper_price, ["grid_upper_price"], "상한가")
      requirePositive(data.grid_lower_price, ["grid_lower_price"], "하한가")
      requirePositive(data.grid_count, ["grid_count"], "그리드 수")
      if (
        data.grid_upper_price?.trim() &&
        data.grid_lower_price?.trim() &&
        Number(data.grid_upper_price) <= Number(data.grid_lower_price)
      ) {
        ctx.addIssue({
          code: "custom",
          path: ["grid_upper_price"],
          message: "상한가는 하한가보다 커야 합니다",
        })
      }
    }

    if (data.bot_type === "position_snowball") {
      requirePositive(data.snow_drop_pct, ["snow_drop_pct"], "추가 매수 하락률(%)")
      requirePositive(data.snow_multiplier, ["snow_multiplier"], "추가 매수 배수")
      requirePositive(data.snow_max_buys, ["snow_max_buys"], "최대 추가 매수 횟수")
    }

    if (data.bot_type === "spot_dca") {
      requirePositive(data.dca_total_orders, ["dca_total_orders"], "총 매수 횟수")
    }

    if (data.bot_type === "algo_orders") {
      requirePositive(data.algo_total_qty, ["algo_total_qty"], "총 주문 수량")
      requirePositive(data.algo_num_slices, ["algo_num_slices"], "분할 주문 수")
      requirePositive(
        data.algo_duration_seconds,
        ["algo_duration_seconds"],
        "총 실행 시간(초)",
      )
    }
  })

type FormData = z.infer<typeof formSchema>

const BOT_TYPE_OPTIONS = [
  { value: "spot_dca", label: "현물 DCA" },
  { value: "spot_grid", label: "현물 그리드" },
  { value: "position_snowball", label: "포지션 스노우볼" },
  { value: "rebalancing", label: "리밸런싱" },
  { value: "algo_orders", label: "알고 주문 (TWAP)" },
]

const BOT_TYPE_DESCRIPTIONS: Record<BotTypeEnum, string> = {
  spot_grid:
    "설정된 범위에서 매수/매도 주문을 반복 실행합니다. 종목코드와 투자금이 필요합니다.",
  position_snowball:
    "하락 시 분할 매수 후 회복 시 이익 실현합니다. 종목코드와 투자금이 필요합니다.",
  rebalancing:
    "목표 자산 비중을 유지합니다. 여러 자산과 비중(합계 100)을 입력하세요.",
  spot_dca:
    "일정 금액을 주기적으로 매수하여 타이밍 리스크를 줄입니다. 종목코드와 투자금이 필요합니다.",
  algo_orders:
    "대량 주문을 시간에 걸쳐 분할 실행합니다(TWAP). 종목코드와 투자금이 필요합니다.",
}

const AddBot = () => {
  const [isOpen, setIsOpen] = useState(false)
  const [rebalancingAssets, setRebalancingAssets] = useState<
    Array<{ symbol: string; weight: string }>
  >(() => {
    const parsed = parseRebalancingAssetsInput(DEFAULT_REBALANCING_ASSETS)
    if (parsed.length >= 2) return parsed
    return [
      { symbol: "BTC", weight: "50" },
      { symbol: "KRW", weight: "50" },
    ]
  })
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const { data: accounts } = useQuery({
    queryKey: ["accounts"],
    queryFn: () => AccountsService.readAccounts({ skip: 0, limit: 100 }),
    enabled: isOpen,
  })

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    defaultValues: {
      name: "",
      bot_type: undefined,
      symbol: "",
      base_currency: "",
      quote_currency: "",
      investment_amount: "",
      grid_upper_price: "",
      grid_lower_price: "",
      grid_count: "20",
      grid_type: "arithmetic",
      snow_drop_pct: "5",
      snow_multiplier: "2.0",
      snow_max_buys: "5",
      rebal_assets_input: DEFAULT_REBALANCING_ASSETS,
      rebal_mode: "time",
      rebal_interval: "1w",
      rebal_threshold_pct: "5",
      dca_frequency: "daily",
      dca_total_orders: "30",
      algo_side: "buy",
      algo_total_qty: "0.1",
      algo_num_slices: "12",
      algo_duration_seconds: "3600",
      stop_loss_pct: "",
      take_profit_pct: "",
      account_id: "",
    },
  })
  const botType = form.watch("bot_type")
  const watchedAccountId = form.watch("account_id")
  const watchedSymbol = form.watch("symbol") ?? ""
  const watchedInvestmentAmount = form.watch("investment_amount") ?? ""
  const watchedGridCount = form.watch("grid_count") ?? "20"
  const selectedAccount = useMemo(
    () => accounts?.data.find((acc) => acc.id === watchedAccountId),
    [accounts, watchedAccountId],
  )
  const upbitMinOrderMessage = useMemo(() => {
    if (!botType || !isUpbitKrwMarket(selectedAccount?.exchange, watchedSymbol)) {
      return null
    }

    const investmentAmount = Number(watchedInvestmentAmount)
    if (botType === "spot_grid") {
      const gridCount = Number(watchedGridCount)
      const perGrid =
        investmentAmount / Math.max(1, Number.isFinite(gridCount) ? gridCount : 1)
      return getUpbitMinOrderMessage(perGrid, "그리드당 투자금")
    }
    if (botType === "spot_dca") {
      return getUpbitMinOrderMessage(investmentAmount, "1회 매수 금액")
    }
    if (botType === "position_snowball") {
      return getUpbitMinOrderMessage(investmentAmount, "기본 매수 금액")
    }

    return null
  }, [
    botType,
    selectedAccount?.exchange,
    watchedGridCount,
    watchedInvestmentAmount,
    watchedSymbol,
  ])

  const mutation = useMutation({
    mutationFn: (data: BotCreate) =>
      BotsService.createBot({ requestBody: data }),
    onSuccess: () => {
      showSuccessToast("봇이 생성되었습니다")
      form.reset()
      setRebalancingAssets(
        parseRebalancingAssetsInput(DEFAULT_REBALANCING_ASSETS),
      )
      setIsOpen(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["bots"] })
    },
  })

  const toOptionalNumberString = (value?: string) =>
    value?.trim() ? value.trim() : undefined

  const toOptionalString = (value?: string) =>
    value?.trim() ? value.trim() : undefined

  const onSubmit = (data: FormData) => {
    if (upbitMinOrderMessage) {
      showErrorToast(upbitMinOrderMessage)
      return
    }

    let baseCurrency = toOptionalString(data.base_currency)?.toUpperCase()
    const quoteCurrency = toOptionalString(data.quote_currency)?.toUpperCase()
    const symbol =
      data.bot_type === "rebalancing"
        ? undefined
        : toOptionalString(data.symbol)?.toUpperCase()

    const config: Record<string, unknown> = {}
    if (data.bot_type === "spot_grid") {
      const gridCount = Number(data.grid_count ?? "20")
      const amountPerGrid = Number(data.investment_amount) / Math.max(1, gridCount)
      config.upper = data.grid_upper_price?.trim()
      config.lower = data.grid_lower_price?.trim()
      config.grid_count = gridCount
      config.arithmetic = (data.grid_type ?? "arithmetic") === "arithmetic"
      config.amount_per_grid = amountPerGrid.toFixed(8)
    }
    if (data.bot_type === "position_snowball") {
      config.drop_pct = data.snow_drop_pct?.trim()
      config.amount_per_buy = data.investment_amount.trim()
      config.take_profit_pct = data.take_profit_pct?.trim() || "5"
      config.max_buys = Number(data.snow_max_buys ?? "5")
      config.multiplier = data.snow_multiplier?.trim() || "2.0"
    }
    if (data.bot_type === "rebalancing") {
      const assets = parseRebalancingAssetsInput(data.rebal_assets_input)
      const assetsMap = Object.fromEntries(
        assets.map((item) => [item.symbol, item.weight]),
      )
      const quote = (quoteCurrency ?? "").toUpperCase()
      config.assets = assetsMap
      config.mode = data.rebal_mode ?? "deviation"
      config.quote = quote
      config.threshold_pct =
        data.rebal_mode === "deviation"
          ? data.rebal_threshold_pct?.trim() || "5"
          : "0"
      config.interval_seconds =
        data.rebal_interval === "1d"
          ? 86400
          : data.rebal_interval === "1m"
            ? 2592000
            : 604800
      const baseAsset =
        assets.find((item) => item.symbol !== quote)?.symbol ??
        assets[0]?.symbol ??
        quote
      baseCurrency = baseAsset
    }
    if (data.bot_type === "spot_dca") {
      config.amount_per_order = data.investment_amount.trim()
      config.interval_seconds =
        data.dca_frequency === "weekly"
          ? 604800
          : data.dca_frequency === "monthly"
            ? 2592000
            : 86400
      config.order_type = "market"
      config.total_orders = Number(data.dca_total_orders ?? "30")
    }
    if (data.bot_type === "algo_orders") {
      config.side = data.algo_side ?? "buy"
      config.total_qty = data.algo_total_qty?.trim() || "0.1"
      config.num_slices = Number(data.algo_num_slices ?? "12")
      config.duration_seconds = Number(data.algo_duration_seconds ?? "3600")
      config.order_type = "market"
    }

    mutation.mutate({
      name: data.name.trim(),
      bot_type: data.bot_type,
      account_id: data.account_id,
      symbol,
      base_currency: baseCurrency,
      quote_currency: quoteCurrency,
      investment_amount: data.investment_amount.trim(),
      stop_loss_pct: toOptionalNumberString(data.stop_loss_pct),
      take_profit_pct: toOptionalNumberString(data.take_profit_pct),
      config,
    })
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="mr-2" />
          봇 생성
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-md">
        <DialogHeader>
          <DialogTitle>트레이딩 봇 생성</DialogTitle>
          <DialogDescription>
            새 트레이딩 봇을 설정합니다. 생성 후 시작할 수 있습니다.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)}>
            <div className="grid gap-4 py-4">
              <FormField
                control={form.control}
                name="account_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      거래소 계좌{" "}
                      <span className="text-destructive">*</span>
                    </FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      value={field.value ?? ""}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="계좌 선택" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {accounts?.data.map((acc) => (
                          <SelectItem key={acc.id} value={acc.id}>
                            {acc.label} ({acc.exchange})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="bot_type"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      봇 유형 <span className="text-destructive">*</span>
                    </FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      value={field.value ?? ""}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="전략 선택" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {BOT_TYPE_OPTIONS.map((opt) => (
                          <SelectItem key={opt.value} value={opt.value}>
                            {opt.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      봇 이름 <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input placeholder="예) BTC DCA 봇" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {botType && (
                <div className="rounded-md border bg-muted/40 p-3 text-sm text-muted-foreground">
                  {BOT_TYPE_DESCRIPTIONS[botType]}
                </div>
              )}
              {botType && isUpbitKrwMarket(selectedAccount?.exchange, watchedSymbol) && (
                <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                  업비트 KRW 마켓 주문은 모두 최소 5,000 KRW 이상이어야 합니다.
                </div>
              )}
              {upbitMinOrderMessage && (
                <div className="text-sm text-destructive">{upbitMinOrderMessage}</div>
              )}

              {botType === "rebalancing" ? (
                <div className="grid grid-cols-1 gap-4">
                  <FormField
                    control={form.control}
                    name="quote_currency"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>
                          견적 통화{" "}
                          <span className="text-destructive">*</span>
                        </FormLabel>
                        <FormControl>
                          <Input placeholder="예) KRW" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              ) : (
                <FormField
                  control={form.control}
                  name="symbol"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>
                        종목코드(심볼) <span className="text-destructive">*</span>
                      </FormLabel>
                      <FormControl>
                        <Input placeholder="예) BTC/KRW" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}

              <FormField
                control={form.control}
                name="investment_amount"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      {botType === "algo_orders" ? "총 주문 금액 (KRW)" : "투자 금액 (KRW)"}{" "}
                      <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input
                        placeholder="예) 100"
                        type="text"
                        inputMode="decimal"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {botType === "spot_grid" && (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="grid_upper_price"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>상한가 (KRW)</FormLabel>
                        <FormControl>
                          <Input placeholder="예) 120000000" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="grid_lower_price"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>하한가 (KRW)</FormLabel>
                        <FormControl>
                          <Input placeholder="예) 90000000" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="grid_count"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>그리드 수</FormLabel>
                        <FormControl>
                          <Input placeholder="예) 20" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="grid_type"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>그리드 타입</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value ?? "arithmetic"}>
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue placeholder="그리드 타입 선택" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="arithmetic">등간격</SelectItem>
                            <SelectItem value="geometric">등비</SelectItem>
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              )}

              {botType === "position_snowball" && (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                  <FormField
                    control={form.control}
                    name="snow_drop_pct"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>추가 매수 하락률 %</FormLabel>
                        <FormControl>
                          <Input placeholder="예) 5" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="snow_multiplier"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>추가 매수 배수</FormLabel>
                        <FormControl>
                          <Input placeholder="예) 2.0" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="snow_max_buys"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>최대 추가 매수 횟수</FormLabel>
                        <FormControl>
                          <Input placeholder="예) 5" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              )}

              {botType === "rebalancing" && (
                <>
                  <FormField
                    control={form.control}
                    name="rebal_assets_input"
                    render={({ field }) => (
                      <FormItem>
                        <div className="flex items-center justify-between">
                          <FormLabel>자산/비중 목록 (합계 100)</FormLabel>
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              const next = [
                                ...rebalancingAssets,
                                { symbol: "", weight: "" },
                              ]
                              setRebalancingAssets(next)
                              field.onChange(buildRebalancingAssetsInput(next))
                            }}
                          >
                            <Plus className="mr-2 size-4" />
                            자산 추가
                          </Button>
                        </div>
                        <div className="space-y-2">
                          {rebalancingAssets.map((row, index) => (
                            <div
                              key={`${index}-${row.symbol}`}
                              className="grid grid-cols-[1fr_1fr_auto] gap-2"
                            >
                              <Input
                                placeholder="자산 심볼 (예: BTC)"
                                value={row.symbol}
                                onChange={(e) => {
                                  const next = rebalancingAssets.map((item, idx) =>
                                    idx === index
                                      ? { ...item, symbol: e.target.value }
                                      : item,
                                  )
                                  setRebalancingAssets(next)
                                  field.onChange(buildRebalancingAssetsInput(next))
                                }}
                              />
                              <Input
                                placeholder="비중 % (예: 40)"
                                value={row.weight}
                                onChange={(e) => {
                                  const next = rebalancingAssets.map((item, idx) =>
                                    idx === index
                                      ? { ...item, weight: e.target.value }
                                      : item,
                                  )
                                  setRebalancingAssets(next)
                                  field.onChange(buildRebalancingAssetsInput(next))
                                }}
                              />
                              <Button
                                type="button"
                                variant="ghost"
                                size="icon"
                                disabled={rebalancingAssets.length <= 2}
                                onClick={() => {
                                  const next = rebalancingAssets.filter(
                                    (_, idx) => idx !== index,
                                  )
                                  setRebalancingAssets(next)
                                  field.onChange(buildRebalancingAssetsInput(next))
                                }}
                              >
                                <Trash2 className="size-4" />
                              </Button>
                            </div>
                          ))}
                        </div>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <FormField
                      control={form.control}
                      name="rebal_mode"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>리밸런싱 방식</FormLabel>
                          <Select onValueChange={field.onChange} value={field.value ?? "time"}>
                            <FormControl>
                              <SelectTrigger>
                                <SelectValue placeholder="방식 선택" />
                              </SelectTrigger>
                            </FormControl>
                            <SelectContent>
                              <SelectItem value="time">시간 기반</SelectItem>
                              <SelectItem value="deviation">편차 기반</SelectItem>
                            </SelectContent>
                          </Select>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    {form.watch("rebal_mode") === "deviation" ? (
                      <FormField
                        control={form.control}
                        name="rebal_threshold_pct"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>편차 임계값 %</FormLabel>
                            <FormControl>
                              <Input placeholder="예) 5" {...field} />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    ) : (
                      <FormField
                        control={form.control}
                        name="rebal_interval"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>리밸런싱 주기</FormLabel>
                            <Select onValueChange={field.onChange} value={field.value ?? "1w"}>
                              <FormControl>
                                <SelectTrigger>
                                  <SelectValue placeholder="주기 선택" />
                                </SelectTrigger>
                              </FormControl>
                              <SelectContent>
                                <SelectItem value="1d">매일</SelectItem>
                                <SelectItem value="1w">매주</SelectItem>
                                <SelectItem value="1m">매월</SelectItem>
                              </SelectContent>
                            </Select>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    )}
                  </div>
                </>
              )}

              {botType === "spot_dca" && (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="dca_frequency"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>매수 주기</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value ?? "daily"}>
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue placeholder="주기 선택" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="daily">매일</SelectItem>
                            <SelectItem value="weekly">매주</SelectItem>
                            <SelectItem value="monthly">매월</SelectItem>
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="dca_total_orders"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>총 매수 횟수</FormLabel>
                        <FormControl>
                          <Input placeholder="예) 30" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              )}

              {botType === "algo_orders" && (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="algo_side"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>주문 방향</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value ?? "buy"}>
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue placeholder="방향 선택" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="buy">매수</SelectItem>
                            <SelectItem value="sell">매도</SelectItem>
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="algo_total_qty"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>총 주문 수량</FormLabel>
                        <FormControl>
                          <Input placeholder="예) 0.1" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="algo_num_slices"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>분할 주문 수</FormLabel>
                        <FormControl>
                          <Input placeholder="예) 12" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="algo_duration_seconds"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>총 실행 시간(초)</FormLabel>
                        <FormControl>
                          <Input placeholder="예) 3600" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              )}

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <FormField
                  control={form.control}
                  name="stop_loss_pct"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>손절 비율 %</FormLabel>
                      <FormControl>
                        <Input
                          placeholder="선택, 예) 5"
                          type="text"
                          inputMode="decimal"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="take_profit_pct"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>목표수익 비율 %</FormLabel>
                      <FormControl>
                        <Input
                          placeholder="선택, 예) 10"
                          type="text"
                          inputMode="decimal"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
            </div>

            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline" disabled={mutation.isPending}>
                  취소
                </Button>
              </DialogClose>
              <LoadingButton
                type="submit"
                loading={mutation.isPending}
                disabled={Boolean(upbitMinOrderMessage)}
              >
                생성
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default AddBot
