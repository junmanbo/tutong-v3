import { createFileRoute } from "@tanstack/react-router"
import { ShieldCheck } from "lucide-react"
import { useState } from "react"

import ChangePassword from "@/components/UserSettings/ChangePassword"
import DeleteAccount from "@/components/UserSettings/DeleteAccount"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import useCustomToast from "@/hooks/useCustomToast"

export const Route = createFileRoute("/_layout/settings/security")({
  component: SettingsSecurityPage,
  head: () => ({
    meta: [{ title: "보안 설정 - AutoTrade" }],
  }),
})

function SettingsSecurityPage() {
  const { showSuccessToast } = useCustomToast()
  const [twoFactorEnabled, setTwoFactorEnabled] = useState(false)
  const [otpSecret] = useState("AUTOTRADE-OTP-SECRET-PLACEHOLDER")
  const [otpCode, setOtpCode] = useState("")

  const handleSave2FA = () => {
    showSuccessToast("2FA 백엔드 연동 전입니다. UI만 준비되었습니다.")
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">보안 설정</h1>
        <p className="text-muted-foreground">
          비밀번호를 변경하고 보안 관련 작업을 관리합니다.
        </p>
      </div>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <ShieldCheck className="size-4" />
            2단계 인증 (TOTP)
          </CardTitle>
          <Badge variant={twoFactorEnabled ? "default" : "secondary"}>
            {twoFactorEnabled ? "활성" : "비활성"}
          </Badge>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <Label htmlFor="two-fa-enabled">2FA 사용</Label>
            <Checkbox
              id="two-fa-enabled"
              checked={twoFactorEnabled}
              onCheckedChange={(checked) => setTwoFactorEnabled(checked === true)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="otp-secret">인증앱 등록 키</Label>
            <Input id="otp-secret" value={otpSecret} readOnly />
          </div>
          <div className="space-y-2">
            <Label htmlFor="otp-code">인증 코드 (6자리)</Label>
            <Input
              id="otp-code"
              value={otpCode}
              onChange={(e) => setOtpCode(e.target.value)}
              placeholder="123456"
              maxLength={6}
            />
          </div>
          <div className="flex justify-end">
            <Button type="button" onClick={handleSave2FA}>
              2FA 설정 저장
            </Button>
          </div>
        </CardContent>
      </Card>
      <ChangePassword />
      <DeleteAccount />
    </div>
  )
}
