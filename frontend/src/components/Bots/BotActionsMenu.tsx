import { useMutation, useQueryClient } from "@tanstack/react-query"
import { EllipsisVertical, Play, Square } from "lucide-react"
import { useState } from "react"

import type { BotPublic } from "@/client"
import { BotsService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import DeleteBot from "./DeleteBot"

interface BotActionsMenuProps {
  bot: BotPublic
}

export const BotActionsMenu = ({ bot }: BotActionsMenuProps) => {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const canStart = bot.status === "stopped" || bot.status === "error"
  const canStop = bot.status === "running" || bot.status === "pending"
  const canDelete = bot.status === "stopped"

  const startMutation = useMutation({
    mutationFn: () => BotsService.startBot({ id: bot.id }),
    onSuccess: () => {
      showSuccessToast("봇이 시작되었습니다")
      setOpen(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["bots"] })
    },
  })

  const stopMutation = useMutation({
    mutationFn: () => BotsService.stopBot({ id: bot.id }),
    onSuccess: () => {
      showSuccessToast("봇이 중지되었습니다")
      setOpen(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["bots"] })
    },
  })

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {canStart && (
          <DropdownMenuItem
            onClick={() => startMutation.mutate()}
            disabled={startMutation.isPending}
          >
            <Play />
            시작
          </DropdownMenuItem>
        )}
        {canStop && (
          <DropdownMenuItem
            onClick={() => stopMutation.mutate()}
            disabled={stopMutation.isPending}
          >
            <Square />
            중지
          </DropdownMenuItem>
        )}
        {canDelete && (
          <DeleteBot id={bot.id} onSuccess={() => setOpen(false)} />
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
