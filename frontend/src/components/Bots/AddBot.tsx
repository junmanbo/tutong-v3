import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { useState } from "react"
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
    stop_loss_pct: optionalNumberField,
    take_profit_pct: optionalNumberField,
    account_id: z.string().min(1, { message: "계좌를 선택해주세요" }),
  })
  .superRefine((data, ctx) => {
    if (data.bot_type === "rebalancing") {
      if (!data.base_currency?.trim()) {
        ctx.addIssue({
          code: "custom",
          path: ["base_currency"],
          message: "리밸런싱에는 기준 통화가 필요합니다",
        })
      }
      if (!data.quote_currency?.trim()) {
        ctx.addIssue({
          code: "custom",
          path: ["quote_currency"],
          message: "리밸런싱에는 견적 통화가 필요합니다",
        })
      }
      if (
        data.base_currency?.trim() &&
        data.quote_currency?.trim() &&
        data.base_currency.trim().toUpperCase() ===
          data.quote_currency.trim().toUpperCase()
      ) {
        ctx.addIssue({
          code: "custom",
          path: ["quote_currency"],
          message: "기준 통화와 견적 통화는 달라야 합니다",
        })
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
  })

type FormData = z.infer<typeof formSchema>

const BOT_TYPE_OPTIONS = [
  { value: "spot_dca", label: "Spot DCA" },
  { value: "spot_grid", label: "Spot Grid" },
  { value: "position_snowball", label: "Position Snowball" },
  { value: "rebalancing", label: "Rebalancing" },
  { value: "algo_orders", label: "Algo Orders (TWAP)" },
]

const BOT_TYPE_DESCRIPTIONS: Record<BotTypeEnum, string> = {
  spot_grid:
    "설정된 범위에서 매수/매도 주문을 반복 실행합니다. 종목코드와 투자금이 필요합니다.",
  position_snowball:
    "하락 시 분할 매수 후 회복 시 이익 실현합니다. 종목코드와 투자금이 필요합니다.",
  rebalancing:
    "목표 자산 비중을 유지합니다. 기준 통화와 견적 통화가 필요합니다.",
  spot_dca:
    "일정 금액을 주기적으로 매수하여 타이밍 리스크를 줄입니다. 종목코드와 투자금이 필요합니다.",
  algo_orders:
    "대량 주문을 시간에 걸쳐 분할 실행합니다(TWAP). 종목코드와 투자금이 필요합니다.",
}

const AddBot = () => {
  const [isOpen, setIsOpen] = useState(false)
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
      stop_loss_pct: "",
      take_profit_pct: "",
      account_id: "",
    },
  })
  const botType = form.watch("bot_type")

  const mutation = useMutation({
    mutationFn: (data: BotCreate) =>
      BotsService.createBot({ requestBody: data }),
    onSuccess: () => {
      showSuccessToast("봇이 생성되었습니다")
      form.reset()
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
    const baseCurrency = toOptionalString(data.base_currency)?.toUpperCase()
    const quoteCurrency = toOptionalString(data.quote_currency)?.toUpperCase()
    const symbol =
      data.bot_type === "rebalancing"
        ? undefined
        : toOptionalString(data.symbol)?.toUpperCase()

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
      <DialogContent className="sm:max-w-md">
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

              {botType === "rebalancing" ? (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="base_currency"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>
                          기준 통화{" "}
                          <span className="text-destructive">*</span>
                        </FormLabel>
                        <FormControl>
                          <Input placeholder="예) BTC" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
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
                      투자 금액 (KRW){" "}
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
              <LoadingButton type="submit" loading={mutation.isPending}>
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
