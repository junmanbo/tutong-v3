import { createFileRoute } from "@tanstack/react-router"
import { Bell, MessageCircle } from "lucide-react"
import { useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

export const Route = createFileRoute("/_layout/settings/notifications")({
  component: NotificationsSettingsPage,
  head: () => ({
    meta: [{ title: "Notification Settings - AutoTrade" }],
  }),
})

function NotificationsSettingsPage() {
  const [events, setEvents] = useState({
    botLifecycle: true,
    takeProfit: true,
    stopLoss: true,
    botError: true,
    accountError: true,
  })

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Notification Settings</h1>
        <p className="text-muted-foreground">
          Configure event subscriptions for email and Telegram alerts.
        </p>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Bell className="size-4" />
            Email Alerts
          </CardTitle>
          <Badge variant="outline">abc@email.com</Badge>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <Label htmlFor="bot-lifecycle">봇 시작/중지</Label>
            <Checkbox
              id="bot-lifecycle"
              checked={events.botLifecycle}
              onCheckedChange={(checked) =>
                setEvents((prev) => ({ ...prev, botLifecycle: checked === true }))
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
                setEvents((prev) => ({ ...prev, accountError: checked === true }))
              }
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MessageCircle className="size-4" />
            Telegram Alerts
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Label htmlFor="telegram-token">Telegram Bot Token</Label>
          <Input id="telegram-token" placeholder="Connect your Telegram bot token" />
        </CardContent>
      </Card>
    </div>
  )
}

