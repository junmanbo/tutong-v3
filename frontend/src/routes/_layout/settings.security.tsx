import { createFileRoute } from "@tanstack/react-router"

import ChangePassword from "@/components/UserSettings/ChangePassword"
import DeleteAccount from "@/components/UserSettings/DeleteAccount"

export const Route = createFileRoute("/_layout/settings/security")({
  component: SettingsSecurityPage,
  head: () => ({
    meta: [{ title: "Security Settings - AutoTrade" }],
  }),
})

function SettingsSecurityPage() {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Security Settings</h1>
        <p className="text-muted-foreground">
          Change your password and manage security-sensitive actions.
        </p>
      </div>
      <ChangePassword />
      <DeleteAccount />
    </div>
  )
}
