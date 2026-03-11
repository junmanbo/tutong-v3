import { createFileRoute, Link as RouterLink } from "@tanstack/react-router"
import { Bell, ShieldCheck, User } from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export const Route = createFileRoute("/_layout/settings")({
  component: SettingsHub,
  head: () => ({
    meta: [
      {
        title: "설정 - AutoTrade",
      },
    ],
  }),
})

function SettingsHub() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">설정</h1>
        <p className="text-muted-foreground">
          프로필, 보안, 알림 설정을 관리합니다.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <User className="size-5 text-primary" />
              프로필
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-3">
              이름과 이메일 주소를 변경합니다.
            </p>
            <RouterLink
              to="/settings/profile"
              className="text-sm text-primary hover:underline"
            >
              프로필 설정으로 이동
            </RouterLink>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <ShieldCheck className="size-5 text-primary" />
              보안
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-3">
              비밀번호 변경 및 계정 보안을 관리합니다.
            </p>
            <RouterLink
              to="/settings/security"
              className="text-sm text-primary hover:underline"
            >
              보안 설정으로 이동
            </RouterLink>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Bell className="size-5 text-primary" />
              알림
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-3">
              이메일 및 텔레그램 알림을 설정합니다.
            </p>
            <RouterLink
              to="/settings/notifications"
              className="text-sm text-primary hover:underline"
            >
              알림 설정으로 이동
            </RouterLink>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
