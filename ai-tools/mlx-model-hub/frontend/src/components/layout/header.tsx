"use client"

import { useHealth } from "@/lib/hooks"
import { Badge } from "@/components/ui/badge"
import { ThemeToggle } from "@/components/theme-toggle"

export function Header() {
  const { data: health, isError } = useHealth()

  return (
    <header className="flex h-16 items-center justify-between border-b bg-card px-6">
      <div className="flex items-center gap-4">
        <h1 className="text-xl font-semibold">Dashboard</h1>
      </div>
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">API Status:</span>
          {isError ? (
            <Badge variant="destructive">Offline</Badge>
          ) : health ? (
            <Badge variant="default" className="bg-green-600">
              Online
            </Badge>
          ) : (
            <Badge variant="secondary">Checking...</Badge>
          )}
        </div>
        <ThemeToggle />
      </div>
    </header>
  )
}
