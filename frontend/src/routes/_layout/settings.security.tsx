import { createFileRoute } from "@tanstack/react-router"

import ChangePassword from "@/components/UserSettings/ChangePassword"
import DeleteAccount from "@/components/UserSettings/DeleteAccount"

export const Route = createFileRoute("/_layout/settings/security")({
  component: SettingsSecurityPage,
  head: () => ({
    meta: [{ title: "보안 설정 - AutoTrade" }],
  }),
})

function SettingsSecurityPage() {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">보안 설정</h1>
        <p className="text-muted-foreground">
          비밀번호를 변경하고 보안 관련 작업을 관리합니다.
        </p>
      </div>
      <ChangePassword />
      <DeleteAccount />
    </div>
  )
}
