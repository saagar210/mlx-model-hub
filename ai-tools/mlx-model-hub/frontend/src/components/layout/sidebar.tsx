"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  Box,
  Brain,
  Gauge,
  GraduationCap,
  LayoutDashboard,
  MessageSquare,
} from "lucide-react"
import { cn } from "@/lib/utils"

const navigation = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Models", href: "/models", icon: Box },
  { name: "Training", href: "/training", icon: GraduationCap },
  { name: "Inference", href: "/inference", icon: MessageSquare },
  { name: "Metrics", href: "/metrics", icon: Gauge },
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <div className="flex h-full w-64 flex-col border-r bg-card">
      <div className="flex h-16 items-center gap-2 border-b px-6">
        <Brain className="h-6 w-6 text-primary" />
        <span className="text-lg font-semibold">MLX Hub</span>
      </div>
      <nav className="flex-1 space-y-1 px-3 py-4">
        {navigation.map((item) => {
          const isActive =
            pathname === item.href ||
            (item.href !== "/" && pathname.startsWith(item.href))
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.name}
            </Link>
          )
        })}
      </nav>
      <div className="border-t p-4">
        <div className="text-xs text-muted-foreground">
          MLX Model Hub v0.1.0
        </div>
      </div>
    </div>
  )
}
