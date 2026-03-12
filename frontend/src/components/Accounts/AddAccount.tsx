import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { AccountsService, OpenAPI, type ExchangeAccountCreate } from "@/client"
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
      .min(1, { message: "계좌명을 입력해주세요" })
      .max(100, { message: "계좌명은 최대 100자까지 입력 가능합니다" }),
    api_key: z.string().min(1, { message: "API Key를 입력해주세요" }),
    api_secret: z.string().min(1, { message: "API Secret을 입력해주세요" }),
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
          message: "KIS 계좌번호(CANO)를 입력해주세요",
        })
      }
    }

    if (data.exchange === "kiwoom") {
      if (!data.kiwoom_account_no?.trim()) {
        ctx.addIssue({
          code: "custom",
          path: ["kiwoom_account_no"],
          message: "키움증권 계좌번호를 입력해주세요",
        })
      }
    }
  })

type FormData = z.input<typeof formSchema>
type SubmitData = z.output<typeof formSchema>
type AccountFormValues = FormData | SubmitData
type ConnectionTestPayload = Omit<ExchangeAccountCreate, "label">
type ConnectionTestResponse = {
  is_valid: boolean
  message: string
}

const EXCHANGE_OPTIONS = [
  { value: "binance", label: "바이낸스" },
  { value: "upbit", label: "업비트" },
  { value: "kis", label: "한국투자증권 (KIS)" },
  { value: "kiwoom", label: "키움증권" },
]

const buildExtraParams = (
  data: AccountFormValues,
): Record<string, unknown> | undefined => {
  const useMock = (data.use_mock ?? "real") === "mock"
  if (data.exchange === "kis") {
    return {
      CANO: data.kis_cano?.trim(),
      ACNT_PRDT_CD: data.kis_acnt_prdt_cd?.trim() || "01",
      is_mock: useMock,
    }
  }

  if (data.exchange === "kiwoom") {
    return {
      account_no: data.kiwoom_account_no?.trim(),
      is_mock: useMock,
    }
  }

  return undefined
}

const buildConnectionPayload = (
  data: AccountFormValues,
): ConnectionTestPayload => ({
  exchange: data.exchange,
  api_key: data.api_key,
  api_secret: data.api_secret,
  extra_params: buildExtraParams(data),
})

const getConnectionFingerprint = (data: AccountFormValues): string =>
  JSON.stringify(buildConnectionPayload(data))

const AddAccount = () => {
  const [isOpen, setIsOpen] = useState(false)
  const [validatedFingerprint, setValidatedFingerprint] = useState<string | null>(
    null,
  )
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
  const isConnectionValidated =
    validatedFingerprint !== null &&
    validatedFingerprint === getConnectionFingerprint(form.getValues())

  const mutation = useMutation({
    mutationFn: (data: ExchangeAccountCreate) =>
      AccountsService.createAccount({ requestBody: data }),
    onSuccess: () => {
      showSuccessToast("계좌가 추가되었습니다")
      form.reset()
      setIsOpen(false)
      setValidatedFingerprint(null)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["accounts"] })
    },
  })

  const connectionTestMutation = useMutation({
    mutationFn: async (
      data: AccountFormValues,
    ): Promise<ConnectionTestResponse> => {
      const accessToken = localStorage.getItem("access_token")
      const response = await fetch(
        `${OpenAPI.BASE}/api/v1/accounts/test-connection`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
          },
          body: JSON.stringify(buildConnectionPayload(data)),
        },
      )

      const raw = (await response.json()) as
        | ConnectionTestResponse
        | { detail?: string }

      if (!response.ok) {
        const detail =
          typeof raw === "object" && raw !== null && "detail" in raw
            ? raw.detail
            : "계좌 연결 테스트 중 오류가 발생했습니다."
        throw new Error(detail)
      }

      return raw as ConnectionTestResponse
    },
    onSuccess: (result, variables) => {
      if (result.is_valid) {
        setValidatedFingerprint(getConnectionFingerprint(variables))
        showSuccessToast(result.message)
        return
      }
      setValidatedFingerprint(null)
      showErrorToast(result.message)
    },
    onError: (error) => {
      setValidatedFingerprint(null)
      showErrorToast(
        error instanceof Error
          ? error.message
          : "계좌 연결 테스트 중 오류가 발생했습니다.",
      )
    },
  })

  const handleDialogOpenChange = (open: boolean) => {
    setIsOpen(open)
    if (!open) {
      form.reset()
      setValidatedFingerprint(null)
      connectionTestMutation.reset()
    }
  }

  const handleConnectionTest = async () => {
    const valid = await form.trigger([
      "exchange",
      "api_key",
      "api_secret",
      "kis_cano",
      "kis_acnt_prdt_cd",
      "kiwoom_account_no",
      "use_mock",
    ])
    if (!valid) {
      showErrorToast("필수 입력값을 확인해주세요.")
      return
    }
    connectionTestMutation.mutate(form.getValues())
  }

  const onSubmit = (data: SubmitData) => {
    const currentFingerprint = getConnectionFingerprint(data)
    if (validatedFingerprint !== currentFingerprint) {
      showErrorToast("연결 테스트를 먼저 완료해주세요.")
      return
    }

    mutation.mutate({
      exchange: data.exchange,
      label: data.label,
      api_key: data.api_key,
      api_secret: data.api_secret,
      extra_params: buildExtraParams(data),
    })
  }

  return (
    <Dialog open={isOpen} onOpenChange={handleDialogOpenChange}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="mr-2" />
          계좌 추가
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>거래소 계좌 추가</DialogTitle>
          <DialogDescription>
            거래소 API 자격증명을 입력한 뒤 연결 테스트를 완료하면 저장할 수 있습니다.
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
                      거래소 <span className="text-destructive">*</span>
                    </FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      value={field.value ?? ""}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="거래소 선택" />
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
                      계좌명 <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input placeholder="예) 내 바이낸스 계좌" {...field} />
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
                      API 키 <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input
                        placeholder="API 키 입력"
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
                      API 시크릿 <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input
                        placeholder="API 시크릿 입력"
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
                          KIS 계좌번호 (CANO){" "}
                          <span className="text-destructive">*</span>
                        </FormLabel>
                        <FormControl>
                          <Input placeholder="예) 12345678" {...field} />
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
                        <FormLabel>계좌상품코드</FormLabel>
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
                        키움 계좌번호{" "}
                        <span className="text-destructive">*</span>
                      </FormLabel>
                      <FormControl>
                        <Input placeholder="예) 1234567890" {...field} />
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
                      <FormLabel>거래 환경</FormLabel>
                      <Select
                        onValueChange={field.onChange}
                        value={field.value ?? "real"}
                      >
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="환경 선택" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="real">실거래</SelectItem>
                          <SelectItem value="mock">모의투자</SelectItem>
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}
            </div>

            <DialogFooter>
              <LoadingButton
                type="button"
                variant="secondary"
                loading={connectionTestMutation.isPending}
                onClick={handleConnectionTest}
              >
                연결 테스트
              </LoadingButton>
              <DialogClose asChild>
                <Button variant="outline" disabled={mutation.isPending}>
                  취소
                </Button>
              </DialogClose>
              <LoadingButton
                type="submit"
                loading={mutation.isPending}
                disabled={!isConnectionValidated}
              >
                저장
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default AddAccount
