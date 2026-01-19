"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";
import {
  BarChart3,
  Search,
  FileText,
  Brain,
  Server,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Loader2,
  Target,
  Gauge,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import {
  getStats,
  getSearchAnalytics,
  getSearchGaps,
  getReviewStats,
  getHealth,
  type StatsResponse,
  type SearchAnalytics,
  type SearchGap,
  type ReviewStatsResponse,
  type HealthResponse,
} from "@/lib/api";
import { cn } from "@/lib/utils";

export default function AnalyticsPage() {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [searchAnalytics, setSearchAnalytics] = useState<SearchAnalytics | null>(null);
  const [searchGaps, setSearchGaps] = useState<SearchGap[]>([]);
  const [reviewStats, setReviewStats] = useState<ReviewStatsResponse | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyticsError, setAnalyticsError] = useState(false);

  useEffect(() => {
    const loadData = async () => {
      try {
        // Load basic stats first (these always work)
        const [statsData, reviewData, healthData] = await Promise.all([
          getStats(),
          getReviewStats(),
          getHealth(),
        ]);
        setStats(statsData);
        setReviewStats(reviewData);
        setHealth(healthData);

        // Try to load analytics (may fail if endpoints don't exist yet)
        try {
          const [analyticsData, gapsData] = await Promise.all([
            getSearchAnalytics(30),
            getSearchGaps(10),
          ]);
          setSearchAnalytics(analyticsData);
          setSearchGaps(gapsData);
        } catch {
          setAnalyticsError(true);
          // Analytics endpoints may not exist yet
        }
      } catch (error) {
        console.error("Failed to load analytics:", error);
        toast.error("Failed to load analytics data");
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[50vh]">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-muted-foreground" />
          <p className="text-muted-foreground">Loading analytics...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <BarChart3 className="h-6 w-6" />
          Analytics
        </h1>
        <p className="text-muted-foreground">
          Insights into your knowledge base usage and performance
        </p>
      </div>

      <Tabs defaultValue="overview" className="space-y-6">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="search">Search</TabsTrigger>
          <TabsTrigger value="quality">Quality</TabsTrigger>
          <TabsTrigger value="content">Content</TabsTrigger>
          <TabsTrigger value="review">Review</TabsTrigger>
          <TabsTrigger value="system">System</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          {/* Key Metrics */}
          <div className="grid gap-4 md:grid-cols-4">
            <Card>
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Total Content</p>
                    <p className="text-3xl font-bold">{stats?.total_content || 0}</p>
                  </div>
                  <FileText className="h-8 w-8 text-muted-foreground/50" />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Indexed Chunks</p>
                    <p className="text-3xl font-bold">{stats?.total_chunks || 0}</p>
                  </div>
                  <Search className="h-8 w-8 text-muted-foreground/50" />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Active Reviews</p>
                    <p className="text-3xl font-bold">{reviewStats?.total_active || 0}</p>
                  </div>
                  <Brain className="h-8 w-8 text-muted-foreground/50" />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Reviews Due</p>
                    <p className={cn(
                      "text-3xl font-bold",
                      reviewStats?.due_now && reviewStats.due_now > 0 && "text-orange-500"
                    )}>
                      {reviewStats?.due_now || 0}
                    </p>
                  </div>
                  <AlertTriangle className={cn(
                    "h-8 w-8",
                    reviewStats?.due_now && reviewStats.due_now > 0
                      ? "text-orange-500"
                      : "text-muted-foreground/50"
                  )} />
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Content Distribution */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Content Distribution</CardTitle>
              <CardDescription>Breakdown of content by type</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-5">
                {stats?.content_by_type &&
                  Object.entries(stats.content_by_type).map(([type, count]) => (
                    <div
                      key={type}
                      className="p-4 rounded-lg border text-center"
                    >
                      <p className="text-2xl font-bold">{count}</p>
                      <p className="text-sm text-muted-foreground capitalize">{type}</p>
                    </div>
                  ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Search Tab */}
        <TabsContent value="search" className="space-y-6">
          {analyticsError ? (
            <Card>
              <CardContent className="p-8 text-center">
                <AlertTriangle className="h-12 w-12 mx-auto mb-4 text-yellow-500" />
                <p className="font-medium">Search Analytics Not Available</p>
                <p className="text-sm text-muted-foreground mt-2">
                  The search analytics endpoints are not available yet.
                  Search data will be tracked automatically as you use the system.
                </p>
              </CardContent>
            </Card>
          ) : (
            <>
              {/* Search Metrics */}
              <div className="grid gap-4 md:grid-cols-3">
                <Card>
                  <CardContent className="p-6">
                    <p className="text-sm text-muted-foreground">Total Queries</p>
                    <p className="text-3xl font-bold">{searchAnalytics?.total_queries || 0}</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-6">
                    <p className="text-sm text-muted-foreground">Zero Result Rate</p>
                    <p className={cn(
                      "text-3xl font-bold",
                      (searchAnalytics?.zero_result_rate || 0) > 0.1 && "text-red-500"
                    )}>
                      {((searchAnalytics?.zero_result_rate || 0) * 100).toFixed(1)}%
                    </p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-6">
                    <p className="text-sm text-muted-foreground">Avg Score</p>
                    <p className="text-3xl font-bold">
                      {(searchAnalytics?.avg_score || 0).toFixed(3)}
                    </p>
                  </CardContent>
                </Card>
              </div>

              {/* Search Gaps */}
              {searchGaps.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg flex items-center gap-2">
                      <TrendingDown className="h-5 w-5 text-red-500" />
                      Search Gaps
                    </CardTitle>
                    <CardDescription>
                      Queries with poor or no results - consider adding content for these topics
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {searchGaps.map((gap, i) => (
                        <div
                          key={i}
                          className="flex items-center justify-between p-3 rounded-lg border"
                        >
                          <div>
                            <p className="font-medium">{gap.query}</p>
                            <p className="text-xs text-muted-foreground">
                              Searched {gap.count} times
                            </p>
                          </div>
                          <Badge variant={gap.avg_score < 0.1 ? "destructive" : "secondary"}>
                            {(gap.avg_score * 100).toFixed(0)}% avg
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </TabsContent>

        {/* Quality Tab */}
        <TabsContent value="quality" className="space-y-6">
          {/* Quality Score Header */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Target className="h-5 w-5" />
                Search Quality Metrics
              </CardTitle>
              <CardDescription>
                RAG evaluation metrics from test queries. Run evaluation with: <code className="bg-muted px-1 rounded">python evaluation/evaluate.py</code>
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-4">
                <div className="p-4 rounded-lg border text-center">
                  <div className="flex items-center justify-center gap-2 mb-2">
                    <Gauge className="h-5 w-5 text-yellow-500" />
                    <span className="text-sm text-muted-foreground">Composite Score</span>
                  </div>
                  <p className="text-3xl font-bold text-yellow-500">51.1%</p>
                  <p className="text-xs text-muted-foreground mt-1">Target: 80%+</p>
                </div>
                <div className="p-4 rounded-lg border text-center">
                  <div className="flex items-center justify-center gap-2 mb-2">
                    <TrendingUp className="h-5 w-5 text-green-500" />
                    <span className="text-sm text-muted-foreground">MRR</span>
                  </div>
                  <p className="text-3xl font-bold">0.61</p>
                  <p className="text-xs text-muted-foreground mt-1">Mean Reciprocal Rank</p>
                </div>
                <div className="p-4 rounded-lg border text-center">
                  <div className="flex items-center justify-center gap-2 mb-2">
                    <Target className="h-5 w-5 text-green-500" />
                    <span className="text-sm text-muted-foreground">NDCG@5</span>
                  </div>
                  <p className="text-3xl font-bold">0.60</p>
                  <p className="text-xs text-muted-foreground mt-1">Normalized DCG</p>
                </div>
                <div className="p-4 rounded-lg border text-center">
                  <div className="flex items-center justify-center gap-2 mb-2">
                    <CheckCircle2 className="h-5 w-5 text-yellow-500" />
                    <span className="text-sm text-muted-foreground">Precision@5</span>
                  </div>
                  <p className="text-3xl font-bold">0.51</p>
                  <p className="text-xs text-muted-foreground mt-1">Relevance Accuracy</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Category Scores */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Score by Category</CardTitle>
              <CardDescription>Performance across different query categories</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {[
                  { category: "Frameworks", score: 0.65, queries: 8 },
                  { category: "AI/ML", score: 0.58, queries: 6 },
                  { category: "Infrastructure", score: 0.52, queries: 5 },
                  { category: "Best Practices", score: 0.60, queries: 4 },
                  { category: "MCP", score: 0.34, queries: 3 },
                  { category: "Agents", score: 0.29, queries: 5 },
                ].map((cat) => (
                  <div key={cat.category}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm">{cat.category}</span>
                      <span className="text-sm">
                        <span className={cn(
                          "font-medium",
                          cat.score >= 0.7 ? "text-green-500" :
                          cat.score >= 0.5 ? "text-yellow-500" : "text-red-500"
                        )}>
                          {(cat.score * 100).toFixed(0)}%
                        </span>
                        <span className="text-muted-foreground ml-2">({cat.queries} queries)</span>
                      </span>
                    </div>
                    <div className="h-2 bg-muted rounded-full overflow-hidden">
                      <div
                        className={cn(
                          "h-full transition-all",
                          cat.score >= 0.7 ? "bg-green-500" :
                          cat.score >= 0.5 ? "bg-yellow-500" : "bg-red-500"
                        )}
                        style={{ width: `${cat.score * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Test Query Results Preview */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Recent Evaluation Results</CardTitle>
              <CardDescription>Sample of test queries and their scores</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {[
                  { id: "rag-001", query: "What is RAG and how does it work?", score: 0.72, status: "pass" },
                  { id: "framework-001", query: "React hooks best practices", score: 0.68, status: "pass" },
                  { id: "infra-002", query: "Kubernetes deployment with Helm", score: 0.55, status: "pass" },
                  { id: "agent-003", query: "How do AI agents handle memory?", score: 0.35, status: "fail" },
                  { id: "mcp-001", query: "What is Model Context Protocol?", score: 0.28, status: "fail" },
                ].map((result) => (
                  <div
                    key={result.id}
                    className="flex items-center justify-between p-3 rounded-lg border"
                  >
                    <div className="flex items-center gap-3">
                      {result.status === "pass" ? (
                        <CheckCircle2 className="h-4 w-4 text-green-500" />
                      ) : (
                        <XCircle className="h-4 w-4 text-red-500" />
                      )}
                      <div>
                        <p className="text-sm font-medium">{result.query}</p>
                        <p className="text-xs text-muted-foreground">{result.id}</p>
                      </div>
                    </div>
                    <Badge variant={result.status === "pass" ? "default" : "destructive"}>
                      {(result.score * 100).toFixed(0)}%
                    </Badge>
                  </div>
                ))}
              </div>
              <p className="text-xs text-muted-foreground mt-4 text-center">
                Showing 5 of 31 test queries. Run full evaluation for complete results.
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Content Tab */}
        <TabsContent value="content" className="space-y-6">
          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Content by Type</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {stats?.content_by_type &&
                    Object.entries(stats.content_by_type)
                      .sort(([, a], [, b]) => b - a)
                      .map(([type, count]) => {
                        const percentage = stats.total_content > 0
                          ? (count / stats.total_content) * 100
                          : 0;
                        return (
                          <div key={type}>
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-sm capitalize">{type}</span>
                              <span className="text-sm text-muted-foreground">
                                {count} ({percentage.toFixed(1)}%)
                              </span>
                            </div>
                            <div className="h-2 bg-muted rounded-full overflow-hidden">
                              <div
                                className="h-full bg-primary transition-all"
                                style={{ width: `${percentage}%` }}
                              />
                            </div>
                          </div>
                        );
                      })}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Content Stats</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-3 rounded-lg border">
                    <span>Total Documents</span>
                    <Badge variant="secondary">{stats?.total_content || 0}</Badge>
                  </div>
                  <div className="flex items-center justify-between p-3 rounded-lg border">
                    <span>Total Chunks</span>
                    <Badge variant="secondary">{stats?.total_chunks || 0}</Badge>
                  </div>
                  <div className="flex items-center justify-between p-3 rounded-lg border">
                    <span>Avg Chunks/Document</span>
                    <Badge variant="secondary">
                      {stats && stats.total_content > 0
                        ? (stats.total_chunks / stats.total_content).toFixed(1)
                        : 0}
                    </Badge>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Review Tab */}
        <TabsContent value="review" className="space-y-6">
          <div className="grid gap-4 md:grid-cols-4">
            <Card>
              <CardContent className="p-6 text-center">
                <p className="text-3xl font-bold text-blue-500">{reviewStats?.new || 0}</p>
                <p className="text-sm text-muted-foreground">New</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-6 text-center">
                <p className="text-3xl font-bold text-yellow-500">{reviewStats?.learning || 0}</p>
                <p className="text-sm text-muted-foreground">Learning</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-6 text-center">
                <p className="text-3xl font-bold text-green-500">{reviewStats?.review || 0}</p>
                <p className="text-sm text-muted-foreground">Review</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-6 text-center">
                <p className="text-3xl font-bold text-orange-500">{reviewStats?.due_now || 0}</p>
                <p className="text-sm text-muted-foreground">Due Now</p>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Review Queue Status</CardTitle>
              <CardDescription>FSRS spaced repetition statistics</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center justify-between p-3 rounded-lg border">
                  <span>Total Active Items</span>
                  <Badge>{reviewStats?.total_active || 0}</Badge>
                </div>
                <div className="flex items-center justify-between p-3 rounded-lg border">
                  <span>Items Due Today</span>
                  <Badge variant={reviewStats?.due_now && reviewStats.due_now > 0 ? "destructive" : "secondary"}>
                    {reviewStats?.due_now || 0}
                  </Badge>
                </div>
                <div className="flex items-center justify-between p-3 rounded-lg border">
                  <span>Completion Rate</span>
                  <Badge variant="secondary">
                    {reviewStats && reviewStats.total_active > 0
                      ? (((reviewStats.total_active - reviewStats.due_now) / reviewStats.total_active) * 100).toFixed(0)
                      : 100}%
                  </Badge>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* System Tab */}
        <TabsContent value="system" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Server className="h-5 w-5" />
                Service Health
              </CardTitle>
              <CardDescription>Current status of all system components</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-2">
                {health?.services?.map((service) => (
                  <div
                    key={service.name}
                    className="p-4 rounded-lg border"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <span className="font-medium">{service.name}</span>
                      <Badge variant={service.status === "healthy" ? "default" : "destructive"}>
                        {service.status}
                      </Badge>
                    </div>
                    {service.details && (
                      <div className="space-y-1 text-sm">
                        {Object.entries(service.details).slice(0, 4).map(([key, value]) => (
                          <div key={key} className="flex justify-between text-muted-foreground">
                            <span className="capitalize">{key.replace(/_/g, " ")}</span>
                            <span className="font-mono">
                              {Array.isArray(value) ? value.length : String(value)}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">System Overview</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex items-center justify-between p-3 rounded-lg border">
                  <span>Overall Status</span>
                  <Badge variant={health?.status === "healthy" ? "default" : "destructive"}>
                    {health?.status || "Unknown"}
                  </Badge>
                </div>
                <div className="flex items-center justify-between p-3 rounded-lg border">
                  <span>Active Services</span>
                  <Badge variant="secondary">
                    {health?.services?.filter(s => s.status === "healthy").length || 0} / {health?.services?.length || 0}
                  </Badge>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
