import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import {
  AccountsService,
  type BotCreate,
  type BotTypeEnum,
  BotsService,
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
      message: "Must be a positive number",
    })

const optionalNumberField = z
  .string()
  .optional()
  .refine(
    (val) => val === undefined || val === "" || !Number.isNaN(Number(val)),
    {
      message: "Must be a valid number",
    },
  )

const formSchema = z.object({
  name: z
    .string()
    .min(1, { message: "Name is required" })
    .max(100, { message: "Name must be at most 100 characters" }),
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
  investment_amount: requiredNumberField("Investment amount is required"),
  stop_loss_pct: optionalNumberField,
  take_profit_pct: optionalNumberField,
  account_id: z.string().min(1, { message: "Account is required" }),
}).superRefine((data, ctx) => {
  if (data.bot_type === "rebalancing") {
    if (!data.base_currency?.trim()) {
      ctx.addIssue({
        code: "custom",
        path: ["base_currency"],
        message: "Base currency is required for rebalancing",
      })
    }
    if (!data.quote_currency?.trim()) {
      ctx.addIssue({
        code: "custom",
        path: ["quote_currency"],
        message: "Quote currency is required for rebalancing",
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
        message: "Base and quote currency must be different",
      })
    }
    return
  }

  if (!data.symbol?.trim()) {
    ctx.addIssue({
      code: "custom",
      path: ["symbol"],
      message: "Symbol is required for this strategy",
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
    "Place repeated buy/sell orders across a configured range. Requires symbol and capital.",
  position_snowball:
    "Average down on drawdowns and exit on recovery. Requires symbol and capital.",
  rebalancing:
    "Maintain a target asset mix by base/quote allocation. Requires base and quote currencies.",
  spot_dca:
    "Buy a fixed amount over time to reduce timing risk. Requires symbol and capital.",
  algo_orders:
    "Split large orders into smaller slices over time. Requires symbol and capital.",
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
      showSuccessToast("Bot created successfully")
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
          Create Bot
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create Trading Bot</DialogTitle>
          <DialogDescription>
            Configure your new trading bot. You can start it after creation.
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
                      Exchange Account{" "}
                      <span className="text-destructive">*</span>
                    </FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select account" />
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
                      Bot Type <span className="text-destructive">*</span>
                    </FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select strategy" />
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
                      Bot Name <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input placeholder="e.g. BTC DCA Bot" {...field} />
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
                          Base Currency{" "}
                          <span className="text-destructive">*</span>
                        </FormLabel>
                        <FormControl>
                          <Input placeholder="e.g. BTC" {...field} />
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
                          Quote Currency{" "}
                          <span className="text-destructive">*</span>
                        </FormLabel>
                        <FormControl>
                          <Input placeholder="e.g. USDT" {...field} />
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
                        Symbol <span className="text-destructive">*</span>
                      </FormLabel>
                      <FormControl>
                        <Input placeholder="e.g. BTC/USDT" {...field} />
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
                      Investment Amount (USDT){" "}
                      <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input
                        placeholder="e.g. 100"
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
                      <FormLabel>Stop Loss %</FormLabel>
                      <FormControl>
                        <Input
                          placeholder="optional, e.g. 5"
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
                      <FormLabel>Take Profit %</FormLabel>
                      <FormControl>
                        <Input
                          placeholder="optional, e.g. 10"
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
                  Cancel
                </Button>
              </DialogClose>
              <LoadingButton type="submit" loading={mutation.isPending}>
                Create
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default AddBot
