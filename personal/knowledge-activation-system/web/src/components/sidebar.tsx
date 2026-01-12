"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";
import {
  LayoutDashboard,
  Search,
  Library,
  Brain,
  ChevronLeft,
  ChevronRight,
  BookOpen,
  FileText,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "@/components/ui/tooltip";
import { getStats, getReviewStats, type StatsResponse, type ReviewStatsResponse } from "@/lib/api";

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
}

const navItems: NavItem[] = [
  { href: "/", label: "Dashboard", icon: <LayoutDashboard className="h-5 w-5" /> },
  { href: "/search", label: "Search", icon: <Search className="h-5 w-5" /> },
  { href: "/content", label: "Content", icon: <Library className="h-5 w-5" /> },
  { href: "/review", label: "Review", icon: <Brain className="h-5 w-5" /> },
];

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [reviewStats, setReviewStats] = useState<ReviewStatsResponse | null>(null);

  useEffect(() => {
    const loadStats = async () => {
      try {
        const [statsData, reviewData] = await Promise.all([
          getStats(),
          getReviewStats(),
        ]);
        setStats(statsData);
        setReviewStats(reviewData);
      } catch {
        // Silently fail - stats are optional
      }
    };
    loadStats();
    // Refresh stats every 60 seconds
    const interval = setInterval(loadStats, 60000);
    return () => clearInterval(interval);
  }, []);

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  };

  return (
    <TooltipProvider delayDuration={0}>
      <aside
        className={cn(
          "flex flex-col h-screen bg-card border-r border-border transition-all duration-300",
          collapsed ? "w-16" : "w-56"
        )}
      >
        {/* Logo / Brand */}
        <div className="h-14 flex items-center px-4 border-b border-border">
          {!collapsed && (
            <Link href="/" className="flex items-center gap-2">
              <BookOpen className="h-6 w-6 text-primary" />
              <span className="font-semibold text-lg">Knowledge</span>
            </Link>
          )}
          {collapsed && (
            <Link href="/">
              <BookOpen className="h-6 w-6 text-primary mx-auto" />
            </Link>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-4 px-2 space-y-1">
          {navItems.map((item) => {
            const active = isActive(item.href);
            const linkContent = (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-md transition-colors",
                  active
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                  collapsed && "justify-center px-2"
                )}
              >
                {item.icon}
                {!collapsed && <span className="text-sm font-medium">{item.label}</span>}
              </Link>
            );

            if (collapsed) {
              return (
                <Tooltip key={item.href}>
                  <TooltipTrigger asChild>{linkContent}</TooltipTrigger>
                  <TooltipContent side="right" sideOffset={10}>
                    {item.label}
                  </TooltipContent>
                </Tooltip>
              );
            }

            return linkContent;
          })}
        </nav>

        <Separator />

        {/* Quick Stats */}
        {!collapsed && (stats || reviewStats) && (
          <div className="p-4 space-y-3">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Quick Stats
            </p>
            <div className="space-y-2">
              {stats && (
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground flex items-center gap-2">
                    <FileText className="h-4 w-4" />
                    Content
                  </span>
                  <span className="font-medium">{stats.total_content}</span>
                </div>
              )}
              {reviewStats && (
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground flex items-center gap-2">
                    <Brain className="h-4 w-4" />
                    Due Now
                  </span>
                  <span className={cn(
                    "font-medium",
                    reviewStats.due_now > 0 && "text-orange-500"
                  )}>
                    {reviewStats.due_now}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        {collapsed && (stats || reviewStats) && (
          <div className="p-2 space-y-2">
            {reviewStats && reviewStats.due_now > 0 && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <div className="flex items-center justify-center p-2 rounded-md bg-orange-500/10">
                    <span className="text-sm font-medium text-orange-500">
                      {reviewStats.due_now}
                    </span>
                  </div>
                </TooltipTrigger>
                <TooltipContent side="right">
                  {reviewStats.due_now} reviews due
                </TooltipContent>
              </Tooltip>
            )}
          </div>
        )}

        <Separator />

        {/* Collapse Toggle */}
        <div className="p-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setCollapsed(!collapsed)}
            className={cn("w-full", collapsed && "px-2")}
          >
            {collapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <>
                <ChevronLeft className="h-4 w-4 mr-2" />
                <span className="text-xs">Collapse</span>
              </>
            )}
          </Button>
        </div>
      </aside>
    </TooltipProvider>
  );
}
