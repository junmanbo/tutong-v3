import { Link as RouterLink, createFileRoute } from "@tanstack/react-router"
import { Bell, ShieldCheck, User } from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export const Route = createFileRoute("/_layout/settings")({
  component: SettingsHub,
  head: () => ({
    meta: [
      {
        title: "Settings - AutoTrade",
      },
    ],
  }),
})

function SettingsHub() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">
          Manage your profile, security, and notification preferences.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <User className="size-5 text-primary" />
              Profile
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-3">
              Update your name and email address.
            </p>
            <RouterLink to="/settings/profile" className="text-sm text-primary hover:underline">
              Go to Profile
            </RouterLink>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <ShieldCheck className="size-5 text-primary" />
              Security
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-3">
              Change password and manage account safety.
            </p>
            <RouterLink to="/settings/security" className="text-sm text-primary hover:underline">
              Go to Security
            </RouterLink>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Bell className="size-5 text-primary" />
              Notifications
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-3">
              Configure event alerts for email and Telegram.
            </p>
            <RouterLink to="/settings/notifications" className="text-sm text-primary hover:underline">
              Go to Notifications
            </RouterLink>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
