import { Link } from "@tanstack/react-router"

import { useTheme } from "@/components/theme-provider"
import { cn } from "@/lib/utils"

interface LogoProps {
  variant?: "full" | "icon" | "responsive"
  className?: string
  asLink?: boolean
}

export function Logo({
  variant = "full",
  className,
  asLink = true,
}: LogoProps) {
  useTheme()

  const content =
    variant === "responsive" ? (
      <>
        <span
          aria-label="투통 오토트레이드"
          className={cn(
            "text-base font-bold tracking-tight group-data-[collapsible=icon]:hidden",
            className,
          )}
        >
          투통 AutoTrade
        </span>
        <span
          aria-label="투통"
          className={cn(
            "hidden size-7 items-center justify-center rounded-md bg-primary font-bold text-primary-foreground group-data-[collapsible=icon]:inline-flex",
            className,
          )}
        >
          투
        </span>
      </>
    ) : (
      <span
        aria-label="투통 오토트레이드"
        className={cn(
          variant === "full"
            ? "text-base font-bold tracking-tight"
            : "inline-flex size-7 items-center justify-center rounded-md bg-primary font-bold text-primary-foreground",
          className,
        )}
      >
        {variant === "full" ? "투통 AutoTrade" : "투"}
      </span>
    )

  if (!asLink) {
    return content
  }

  return <Link to="/">{content}</Link>
}
