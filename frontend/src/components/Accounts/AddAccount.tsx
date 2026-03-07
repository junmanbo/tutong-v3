import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { AccountsService, type ExchangeAccountCreate } from "@/client"
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

const formSchema = z
  .object({
    exchange: z.enum(["binance", "upbit", "kis", "kiwoom"]),
    label: z
      .string()
      .min(1, { message: "Label is required" })
      .max(100, { message: "Label must be at most 100 characters" }),
    api_key: z.string().min(1, { message: "API Key is required" }),
    api_secret: z.string().min(1, { message: "API Secret is required" }),
    kis_cano: z.string().optional(),
    kis_acnt_prdt_cd: z.string().optional(),
    kiwoom_account_no: z.string().optional(),
    use_mock: z.enum(["real", "mock"]).default("real"),
  })
  .superRefine((data, ctx) => {
    if (data.exchange === "kis") {
      if (!data.kis_cano?.trim()) {
        ctx.addIssue({
          code: "custom",
          path: ["kis_cano"],
          message: "KIS account number (CANO) is required",
        })
      }
    }

    if (data.exchange === "kiwoom") {
      if (!data.kiwoom_account_no?.trim()) {
        ctx.addIssue({
          code: "custom",
          path: ["kiwoom_account_no"],
          message: "Kiwoom account number is required",
        })
      }
    }
  })

type FormData = z.input<typeof formSchema>
type SubmitData = z.output<typeof formSchema>

const EXCHANGE_OPTIONS = [
  { value: "binance", label: "Binance" },
  { value: "upbit", label: "Upbit" },
  { value: "kis", label: "Korea Investment Securities (KIS)" },
  { value: "kiwoom", label: "Kiwoom Securities" },
]

const AddAccount = () => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm<FormData, unknown, SubmitData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    defaultValues: {
      exchange: undefined,
      label: "",
      api_key: "",
      api_secret: "",
      kis_cano: "",
      kis_acnt_prdt_cd: "01",
      kiwoom_account_no: "",
      use_mock: "real",
    },
  })
  const exchange = form.watch("exchange")

  const mutation = useMutation({
    mutationFn: (data: ExchangeAccountCreate) =>
      AccountsService.createAccount({ requestBody: data }),
    onSuccess: () => {
      showSuccessToast("Account added successfully")
      form.reset()
      setIsOpen(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["accounts"] })
    },
  })

  const onSubmit = (data: SubmitData) => {
    let extra_params: Record<string, unknown> | undefined

    if (data.exchange === "kis") {
      extra_params = {
        CANO: data.kis_cano?.trim(),
        ACNT_PRDT_CD: data.kis_acnt_prdt_cd?.trim() || "01",
        is_mock: data.use_mock === "mock",
      }
    }

    if (data.exchange === "kiwoom") {
      extra_params = {
        account_no: data.kiwoom_account_no?.trim(),
        is_mock: data.use_mock === "mock",
      }
    }

    mutation.mutate({
      exchange: data.exchange,
      label: data.label,
      api_key: data.api_key,
      api_secret: data.api_secret,
      extra_params,
    })
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="mr-2" />
          Add Account
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add Exchange Account</DialogTitle>
          <DialogDescription>
            Enter your exchange API credentials. Keys are encrypted and stored
            securely.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)}>
            <div className="grid gap-4 py-4">
              <FormField
                control={form.control}
                name="exchange"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      Exchange <span className="text-destructive">*</span>
                    </FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      value={field.value ?? ""}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select exchange" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {EXCHANGE_OPTIONS.map((opt) => (
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
                name="label"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      Label <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input placeholder="e.g. My Binance Account" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="api_key"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      API Key <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input
                        placeholder="API Key"
                        type="password"
                        autoComplete="off"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="api_secret"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      API Secret <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input
                        placeholder="API Secret"
                        type="password"
                        autoComplete="off"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {exchange === "kis" && (
                <>
                  <FormField
                    control={form.control}
                    name="kis_cano"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>
                          KIS Account Number (CANO){" "}
                          <span className="text-destructive">*</span>
                        </FormLabel>
                        <FormControl>
                          <Input placeholder="e.g. 12345678" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="kis_acnt_prdt_cd"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Account Product Code</FormLabel>
                        <FormControl>
                          <Input placeholder="01" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </>
              )}

              {exchange === "kiwoom" && (
                <FormField
                  control={form.control}
                  name="kiwoom_account_no"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>
                        Kiwoom Account Number{" "}
                        <span className="text-destructive">*</span>
                      </FormLabel>
                      <FormControl>
                        <Input placeholder="e.g. 1234567890" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}

              {(exchange === "kis" || exchange === "kiwoom") && (
                <FormField
                  control={form.control}
                  name="use_mock"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Environment</FormLabel>
                      <Select
                        onValueChange={field.onChange}
                        value={field.value ?? "real"}
                      >
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Select environment" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="real">Real</SelectItem>
                          <SelectItem value="mock">Mock</SelectItem>
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}
            </div>

            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline" disabled={mutation.isPending}>
                  Cancel
                </Button>
              </DialogClose>
              <LoadingButton type="submit" loading={mutation.isPending}>
                Save
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default AddAccount
