"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { StatsCard } from "@/components/stats-card";
import { ContentPieChart } from "@/components/charts/pie-chart";
import {
  FileText,
  Layers,
  Brain,
  Flame,
  Search,
  Play,
  ArrowRight,
  Youtube,
  Bookmark,
  FileIcon,
  StickyNote,
} from "lucide-react";
import {
  getStats,
  getReviewStats,
  getHealth,
  getContent,
  type StatsResponse,
  type ReviewStatsResponse,
  type HealthResponse,
  type ContentItem,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const CONTENT_COLORS: Record<string, string> = {
  youtube: "#ef4444",
  bookmark: "#3b82f6",
  note: "#22c55e",
  pdf: "#f97316",
  file: "#6b7280",
};

export default function DashboardPage() {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [reviewStats, setReviewStats] = useState<ReviewStatsResponse | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [recentContent, setRecentContent] = useState<ContentItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      try {
        const [statsData, reviewData, healthData, contentData] = await Promise.all([
          getStats(),
          getReviewStats(),
          getHealth(),
          getContent(undefined, 5),
        ]);
        setStats(statsData);
        setReviewStats(reviewData);
        setHealth(healthData);
        setRecentContent(contentData.items);
      } catch (error) {
        console.error("Failed to load dashboard data:", error);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  const getTypeIcon = (type: string) => {
    switch (type) {
      case "youtube":
        return <Youtube className="h-4 w-4 text-red-500" />;
      case "bookmark":
        return <Bookmark className="h-4 w-4 text-blue-500" />;
      case "note":
        return <StickyNote className="h-4 w-4 text-green-500" />;
      case "pdf":
        return <FileIcon className="h-4 w-4 text-orange-500" />;
      default:
        return <FileText className="h-4 w-4 text-gray-500" />;
    }
  };

  const pieChartData = stats
    ? Object.entries(stats.content_by_type)
        .filter(([, count]) => count > 0)
        .map(([type, count]) => ({
          name: type.charAt(0).toUpperCase() + type.slice(1),
          value: count,
          color: CONTENT_COLORS[type] || CONTENT_COLORS.file,
        }))
    : [];

  if (loading) {
    return (
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="h-8 w-48 bg-muted rounded animate-pulse" />
            <div className="h-4 w-64 bg-muted rounded animate-pulse mt-2" />
          </div>
        </div>
        <div className="grid grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <Card key={i}>
              <CardContent className="p-6">
                <div className="h-4 w-20 bg-muted rounded animate-pulse" />
                <div className="h-8 w-16 bg-muted rounded animate-pulse mt-2" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-muted-foreground">
            Overview of your knowledge activation system
          </p>
        </div>
        <div className="flex gap-2">
          <Link href="/search">
            <Button variant="outline" className="gap-2">
              <Search className="h-4 w-4" />
              Search
            </Button>
          </Link>
          <Link href="/review">
            <Button className="gap-2">
              <Play className="h-4 w-4" />
              Start Review
            </Button>
          </Link>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard
          title="Total Content"
          value={stats?.total_content || 0}
          icon={FileText}
          description="Items in your knowledge base"
        />
        <StatsCard
          title="Indexed Chunks"
          value={stats?.total_chunks || 0}
          icon={Layers}
          description="Searchable text segments"
        />
        <StatsCard
          title="Reviews Due"
          value={reviewStats?.due_now || 0}
          icon={Brain}
          description="Items to review today"
          valueClassName={reviewStats?.due_now && reviewStats.due_now > 0 ? "text-orange-500" : undefined}
        />
        <StatsCard
          title="In Review Queue"
          value={reviewStats?.total_active || 0}
          icon={Flame}
          description="Active items for spaced repetition"
        />
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Content Distribution */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-base">Content by Type</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ContentPieChart data={pieChartData} />
            </div>
          </CardContent>
        </Card>

        {/* Recent Content */}
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Recent Content</CardTitle>
            <Link href="/content">
              <Button variant="ghost" size="sm" className="gap-1 text-muted-foreground">
                View all <ArrowRight className="h-3 w-3" />
              </Button>
            </Link>
          </CardHeader>
          <CardContent>
            {recentContent.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <FileText className="h-12 w-12 mx-auto mb-4 opacity-20" />
                <p>No content yet</p>
                <p className="text-sm mt-1">
                  Use the CLI to ingest YouTube videos, bookmarks, or files
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {recentContent.map((item) => (
                  <Link
                    key={item.id}
                    href={`/content/${item.id}`}
                    className="flex items-center gap-3 p-3 rounded-lg hover:bg-muted/50 transition-colors group"
                  >
                    {getTypeIcon(item.content_type)}
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate group-hover:text-primary transition-colors">
                        {item.title}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {new Date(item.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    {item.tags.length > 0 && (
                      <div className="hidden sm:flex gap-1">
                        {item.tags.slice(0, 2).map((tag) => (
                          <Badge key={tag} variant="secondary" className="text-xs">
                            {tag}
                          </Badge>
                        ))}
                        {item.tags.length > 2 && (
                          <Badge variant="secondary" className="text-xs">
                            +{item.tags.length - 2}
                          </Badge>
                        )}
                      </div>
                    )}
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* System Status & Review Queue */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Review Queue Stats */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Review Queue Breakdown</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-4 gap-4">
              <div className="text-center p-4 rounded-lg bg-muted/50">
                <p className="text-2xl font-bold text-blue-500">
                  {reviewStats?.new || 0}
                </p>
                <p className="text-xs text-muted-foreground">New</p>
              </div>
              <div className="text-center p-4 rounded-lg bg-muted/50">
                <p className="text-2xl font-bold text-yellow-500">
                  {reviewStats?.learning || 0}
                </p>
                <p className="text-xs text-muted-foreground">Learning</p>
              </div>
              <div className="text-center p-4 rounded-lg bg-muted/50">
                <p className="text-2xl font-bold text-green-500">
                  {reviewStats?.review || 0}
                </p>
                <p className="text-xs text-muted-foreground">Review</p>
              </div>
              <div className="text-center p-4 rounded-lg bg-muted/50">
                <p className="text-2xl font-bold text-orange-500">
                  {reviewStats?.due_now || 0}
                </p>
                <p className="text-xs text-muted-foreground">Due Now</p>
              </div>
            </div>
            {reviewStats && reviewStats.due_now > 0 && (
              <div className="mt-4">
                <Link href="/review">
                  <Button className="w-full gap-2">
                    <Play className="h-4 w-4" />
                    Start Review Session ({reviewStats.due_now} due)
                  </Button>
                </Link>
              </div>
            )}
          </CardContent>
        </Card>

        {/* System Status */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">System Status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {health?.services?.map((service) => (
                <div
                  key={service.name}
                  className="flex items-center justify-between p-3 rounded-lg bg-muted/50"
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={cn(
                        "h-2 w-2 rounded-full",
                        service.status === "healthy" ? "bg-green-500" : "bg-red-500"
                      )}
                    />
                    <span className="font-medium">{service.name}</span>
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {service.status === "healthy" ? (
                      service.details && (
                        <span>
                          {service.name === "PostgreSQL" && service.details.content_count !== undefined
                            ? `${service.details.content_count} items`
                            : Array.isArray(service.details.models_loaded)
                            ? (service.details.models_loaded as string[]).join(", ")
                            : "OK"}
                        </span>
                      )
                    ) : (
                      <span className="text-red-500">Unhealthy</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Quick Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Link href="/search">
              <div className="p-4 rounded-lg border border-border hover:border-primary/50 hover:bg-muted/50 transition-colors cursor-pointer group">
                <Search className="h-8 w-8 mb-3 text-muted-foreground group-hover:text-primary transition-colors" />
                <h3 className="font-medium mb-1">Search Knowledge</h3>
                <p className="text-sm text-muted-foreground">
                  Find content using hybrid search
                </p>
              </div>
            </Link>
            <Link href="/review">
              <div className="p-4 rounded-lg border border-border hover:border-primary/50 hover:bg-muted/50 transition-colors cursor-pointer group">
                <Brain className="h-8 w-8 mb-3 text-muted-foreground group-hover:text-primary transition-colors" />
                <h3 className="font-medium mb-1">Review Session</h3>
                <p className="text-sm text-muted-foreground">
                  Practice with spaced repetition
                </p>
              </div>
            </Link>
            <Link href="/content">
              <div className="p-4 rounded-lg border border-border hover:border-primary/50 hover:bg-muted/50 transition-colors cursor-pointer group">
                <FileText className="h-8 w-8 mb-3 text-muted-foreground group-hover:text-primary transition-colors" />
                <h3 className="font-medium mb-1">Browse Content</h3>
                <p className="text-sm text-muted-foreground">
                  View and manage your library
                </p>
              </div>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
