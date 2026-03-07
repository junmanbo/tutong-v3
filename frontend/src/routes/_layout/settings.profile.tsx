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
        <h1 className="text-2xl font-bold tracking-tight">Profile Settings</h1>
        <p className="text-muted-foreground">
          Update your personal account information.
        </p>
      </div>
      <UserInformation />
    </div>
  )
}
