import { createFileRoute } from "@tanstack/react-router"

import UserInformation from "@/components/UserSettings/UserInformation"

export const Route = createFileRoute("/_layout/settings/profile")({
  component: SettingsProfilePage,
  head: () => ({
    meta: [{ title: "Profile Settings - AutoTrade" }],
  }),
})

function SettingsProfilePage() {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">프로필 설정</h1>
        <p className="text-muted-foreground">
          개인 계정 정보를 수정합니다.
        </p>
      </div>
      <UserInformation />
    </div>
  )
}
