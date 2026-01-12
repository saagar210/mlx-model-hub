"use client"

import { DashboardLayout } from "@/components/layout"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { useHealth, useMetrics } from "@/lib/hooks"
import {
  Activity,
  Brain,
  Clock,
  Database,
  ExternalLink,
  RefreshCw,
  Server,
  Zap,
} from "lucide-react"

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B"
  const k = 1024
  const sizes = ["B", "KB", "MB", "GB", "TB"]
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i]
}

function formatUptime(seconds: number): string {
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)

  if (days > 0) return `${days}d ${hours}h ${minutes}m`
  if (hours > 0) return `${hours}h ${minutes}m`
  return `${minutes}m`
}

function MetricCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  isLoading,
}: {
  title: string
  value: string | number
  subtitle?: string
  icon: React.ElementType
  trend?: "up" | "down" | "neutral"
  isLoading?: boolean
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-8 w-20" />
        ) : (
          <>
            <div className="text-2xl font-bold">{value}</div>
            {subtitle && (
              <p className="text-xs text-muted-foreground">{subtitle}</p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}

export default function MetricsPage() {
  const {
    data: health,
    isLoading: healthLoading,
    refetch: refetchHealth,
  } = useHealth()
  const {
    data: metrics,
    isLoading: metricsLoading,
    refetch: refetchMetrics,
  } = useMetrics()

  const handleRefresh = () => {
    refetchHealth()
    refetchMetrics()
  }

  const isLoading = healthLoading || metricsLoading

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-3xl font-bold tracking-tight">Metrics</h2>
            <p className="text-muted-foreground">
              Monitor system health and performance
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="icon" onClick={handleRefresh}>
              <RefreshCw className="h-4 w-4" />
            </Button>
            <a
              href="http://localhost:3001"
              target="_blank"
              rel="noopener noreferrer"
            >
              <Button variant="outline">
                <ExternalLink className="mr-2 h-4 w-4" />
                Open Grafana
              </Button>
            </a>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Server className="h-5 w-5" />
              API Status
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4">
              {healthLoading ? (
                <Skeleton className="h-6 w-20" />
              ) : health ? (
                <>
                  <Badge variant="default" className="bg-green-600">
                    Online
                  </Badge>
                  <span className="text-sm text-muted-foreground">
                    Version {health.version}
                  </span>
                </>
              ) : (
                <Badge variant="destructive">Offline</Badge>
              )}
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            title="Models Loaded"
            value={metrics?.models_loaded ?? 0}
            subtitle="Ready for inference"
            icon={Brain}
            isLoading={isLoading}
          />
          <MetricCard
            title="Active Inferences"
            value={metrics?.active_inferences ?? 0}
            subtitle="Currently processing"
            icon={Zap}
            isLoading={isLoading}
          />
          <MetricCard
            title="Training Jobs"
            value={metrics?.training_jobs_running ?? 0}
            subtitle="Currently running"
            icon={Activity}
            isLoading={isLoading}
          />
          <MetricCard
            title="Uptime"
            value={formatUptime(metrics?.uptime_seconds ?? 0)}
            subtitle="Since last restart"
            icon={Clock}
            isLoading={isLoading}
          />
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Database className="h-5 w-5" />
                Storage
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <div className="mb-2 flex justify-between text-sm">
                  <span>Cache Size</span>
                  <span>{formatBytes(metrics?.cache_size_bytes ?? 0)}</span>
                </div>
                <Progress
                  value={
                    metrics?.cache_size_bytes
                      ? (metrics.cache_size_bytes / (50 * 1024 * 1024 * 1024)) *
                        100
                      : 0
                  }
                  className="h-2"
                />
                <p className="mt-1 text-xs text-muted-foreground">
                  of 50 GB estimated capacity
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Quick Links</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <a
                href="http://localhost:9090"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-between rounded-md border p-3 transition-colors hover:bg-accent"
              >
                <span>Prometheus</span>
                <ExternalLink className="h-4 w-4" />
              </a>
              <a
                href="http://localhost:3001"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-between rounded-md border p-3 transition-colors hover:bg-accent"
              >
                <span>Grafana Dashboard</span>
                <ExternalLink className="h-4 w-4" />
              </a>
              <a
                href="http://localhost:5001"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-between rounded-md border p-3 transition-colors hover:bg-accent"
              >
                <span>MLflow Tracking</span>
                <ExternalLink className="h-4 w-4" />
              </a>
              <a
                href="http://localhost:8000/docs"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-between rounded-md border p-3 transition-colors hover:bg-accent"
              >
                <span>API Documentation</span>
                <ExternalLink className="h-4 w-4" />
              </a>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Prometheus Metrics</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              The following metrics are exposed at{" "}
              <code className="rounded bg-muted px-1 py-0.5">
                http://localhost:8000/metrics
              </code>
              :
            </p>
            <div className="mt-4 grid gap-2 md:grid-cols-2">
              <div className="rounded-md border p-3">
                <code className="text-sm font-medium">http_requests_total</code>
                <p className="text-xs text-muted-foreground">
                  Total HTTP requests by method, path, status
                </p>
              </div>
              <div className="rounded-md border p-3">
                <code className="text-sm font-medium">
                  http_request_duration_seconds
                </code>
                <p className="text-xs text-muted-foreground">
                  Request latency histogram
                </p>
              </div>
              <div className="rounded-md border p-3">
                <code className="text-sm font-medium">inference_ttft_seconds</code>
                <p className="text-xs text-muted-foreground">
                  Time to first token for inference
                </p>
              </div>
              <div className="rounded-md border p-3">
                <code className="text-sm font-medium">model_cache_size</code>
                <p className="text-xs text-muted-foreground">
                  Number of models in cache
                </p>
              </div>
              <div className="rounded-md border p-3">
                <code className="text-sm font-medium">training_loss</code>
                <p className="text-xs text-muted-foreground">
                  Current training loss by job
                </p>
              </div>
              <div className="rounded-md border p-3">
                <code className="text-sm font-medium">
                  training_tokens_per_second
                </code>
                <p className="text-xs text-muted-foreground">
                  Training throughput by job
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  )
}
