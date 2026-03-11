import { useMutation, useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Bell, MessageCircle } from "lucide-react"
import { useEffect, useState } from "react"

import {
  type NotificationSettingsPublic,
  type NotificationSettingsUpdate,
  NotificationsService,
} from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/settings/notifications")({
  component: NotificationsSettingsPage,
  head: () => ({
    meta: [{ title: "알림 설정 - AutoTrade" }],
  }),
})

function NotificationsSettingsPage() {
  const { user } = useAuth()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [events, setEvents] = useState({
    botStart: true,
    botStop: true,
    takeProfit: true,
    stopLoss: true,
    botError: true,
    accountError: true,
  })
  const [emailEnabled, setEmailEnabled] = useState(true)
  const [telegramEnabled, setTelegramEnabled] = useState(false)
  const [telegramChatId, setTelegramChatId] = useState("")

  const { data, isLoading } = useQuery<NotificationSettingsPublic>({
    queryKey: ["notification-settings"],
    queryFn: () => NotificationsService.readNotificationSettings(),
  })

  useEffect(() => {
    if (!data) return
    setEmailEnabled(data.email_enabled ?? true)
    setTelegramEnabled(data.telegram_enabled ?? false)
    setTelegramChatId(data.telegram_chat_id ?? "")
    setEvents({
      botStart: data.notify_bot_start ?? true,
      botStop: data.notify_bot_stop ?? true,
      takeProfit: data.notify_take_profit ?? true,
      stopLoss: data.notify_stop_loss ?? true,
      botError: data.notify_bot_error ?? true,
      accountError: data.notify_account_error ?? true,
    })
  }, [data])

  const mutation = useMutation({
    mutationFn: (requestBody: NotificationSettingsUpdate) =>
      NotificationsService.updateNotificationSettings({ requestBody }),
    onSuccess: () => {
      showSuccessToast("알림 설정이 저장되었습니다")
    },
    onError: handleError.bind(showErrorToast),
  })

  const onSave = () => {
    mutation.mutate({
      email_enabled: emailEnabled,
      telegram_enabled: telegramEnabled,
      telegram_chat_id: telegramChatId || null,
      notify_bot_start: events.botStart,
      notify_bot_stop: events.botStop,
      notify_take_profit: events.takeProfit,
      notify_stop_loss: events.stopLoss,
      notify_bot_error: events.botError,
      notify_account_error: events.accountError,
    })
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          알림 설정
        </h1>
        <p className="text-muted-foreground">
          이메일 및 텔레그램 알림 이벤트를 설정합니다.
        </p>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Bell className="size-4" />
            이메일 알림
          </CardTitle>
          <Badge variant="outline">{user?.email ?? "이메일 없음"}</Badge>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <Label htmlFor="email-enabled">이메일 알림 전체</Label>
            <Checkbox
              id="email-enabled"
              checked={emailEnabled}
              onCheckedChange={(checked) => setEmailEnabled(checked === true)}
            />
          </div>
          <div className="flex items-center justify-between">
            <Label htmlFor="bot-start">봇 시작</Label>
            <Checkbox
              id="bot-start"
              checked={events.botStart}
              onCheckedChange={(checked) =>
                setEvents((prev) => ({ ...prev, botStart: checked === true }))
              }
            />
          </div>
          <div className="flex items-center justify-between">
            <Label htmlFor="bot-stop">봇 중지</Label>
            <Checkbox
              id="bot-stop"
              checked={events.botStop}
              onCheckedChange={(checked) =>
                setEvents((prev) => ({ ...prev, botStop: checked === true }))
              }
            />
          </div>
          <div className="flex items-center justify-between">
            <Label htmlFor="take-profit">목표 수익 달성</Label>
            <Checkbox
              id="take-profit"
              checked={events.takeProfit}
              onCheckedChange={(checked) =>
                setEvents((prev) => ({ ...prev, takeProfit: checked === true }))
              }
            />
          </div>
          <div className="flex items-center justify-between">
            <Label htmlFor="stop-loss">손절 한도 도달</Label>
            <Checkbox
              id="stop-loss"
              checked={events.stopLoss}
              onCheckedChange={(checked) =>
                setEvents((prev) => ({ ...prev, stopLoss: checked === true }))
              }
            />
          </div>
          <div className="flex items-center justify-between">
            <Label htmlFor="bot-error">봇 오류 발생</Label>
            <Checkbox
              id="bot-error"
              checked={events.botError}
              onCheckedChange={(checked) =>
                setEvents((prev) => ({ ...prev, botError: checked === true }))
              }
            />
          </div>
          <div className="flex items-center justify-between">
            <Label htmlFor="account-error">계좌 API 오류</Label>
            <Checkbox
              id="account-error"
              checked={events.accountError}
              onCheckedChange={(checked) =>
                setEvents((prev) => ({
                  ...prev,
                  accountError: checked === true,
                }))
              }
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MessageCircle className="size-4" />
            텔레그램 알림
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between">
            <Label htmlFor="telegram-enabled">텔레그램 알림 전체</Label>
            <Checkbox
              id="telegram-enabled"
              checked={telegramEnabled}
              onCheckedChange={(checked) =>
                setTelegramEnabled(checked === true)
              }
            />
          </div>
          <Label htmlFor="telegram-chat-id">텔레그램 채팅 ID</Label>
          <Input
            id="telegram-chat-id"
            value={telegramChatId}
            onChange={(e) => setTelegramChatId(e.target.value)}
            placeholder="텔레그램 채팅 ID를 입력하세요"
          />
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button
          type="button"
          onClick={onSave}
          disabled={isLoading || mutation.isPending}
        >
          설정 저장
        </Button>
      </div>
    </div>
  )
}
