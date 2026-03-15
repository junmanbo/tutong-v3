import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Square } from "lucide-react"
import { type ReactNode, useState } from "react"

import type { BotPublic } from "@/client"
import { BotsService } from "@/client"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface StopBotDialogProps {
  bot: BotPublic
  trigger?: ReactNode
  onStopped?: () => void
}

export const StopBotDialog = ({
  bot,
  trigger,
  onStopped,
}: StopBotDialogProps) => {
  const [open, setOpen] = useState(false)
  const [cancelOpenOrders, setCancelOpenOrders] = useState(true)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const stopMutation = useMutation({
    mutationFn: () =>
      BotsService.stopBot({
        id: bot.id,
        body: { cancel_open_orders: cancelOpenOrders },
      }),
    onSuccess: () => {
      showSuccessToast(
        cancelOpenOrders
          ? "봇을 중지하고 열린 주문 취소를 요청했습니다."
          : "봇 중지를 요청했습니다.",
      )
      setOpen(false)
      onStopped?.()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["bots"] })
      queryClient.invalidateQueries({ queryKey: ["bot", bot.id] })
      queryClient.invalidateQueries({ queryKey: ["bot-orders", bot.id] })
    },
  })

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!stopMutation.isPending) {
          setOpen(nextOpen)
        }
      }}
    >
      <DialogTrigger asChild>
        {trigger ?? (
          <Button variant="outline" size="sm">
            <Square className="mr-2 size-4" />
            중지
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>봇을 중지할까요?</DialogTitle>
          <DialogDescription>
            실행 중인 봇을 멈출 수 있습니다. 기본값은 거래소에 남아 있는 열린
            주문도 함께 취소하는 것입니다.
          </DialogDescription>
        </DialogHeader>
        <div className="rounded-md border p-3">
          <label className="flex cursor-pointer items-start gap-3">
            <Checkbox
              checked={cancelOpenOrders}
              onCheckedChange={(checked) => setCancelOpenOrders(checked === true)}
            />
            <div className="space-y-1">
              <p className="text-sm font-medium">열린 주문도 함께 취소</p>
              <p className="text-sm text-muted-foreground">
                체크하면 중지 요청 시 미체결 주문을 먼저 취소한 뒤 워커 종료까지
                이어집니다.
              </p>
            </div>
          </label>
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => setOpen(false)}
            disabled={stopMutation.isPending}
          >
            닫기
          </Button>
          <Button
            variant="destructive"
            onClick={() => stopMutation.mutate()}
            disabled={stopMutation.isPending}
          >
            {stopMutation.isPending ? "중지 중..." : "중지 요청"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
