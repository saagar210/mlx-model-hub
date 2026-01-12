"use client"

import { DashboardLayout } from "@/components/layout"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useMetrics, useModels, useTrainingJobs } from "@/lib/hooks"
import { Skeleton } from "@/components/ui/skeleton"
import { Box, Brain, Gauge, GraduationCap } from "lucide-react"
import Link from "next/link"

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B"
  const k = 1024
  const sizes = ["B", "KB", "MB", "GB", "TB"]
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i]
}

function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  href,
  isLoading,
}: {
  title: string
  value: string | number
  subtitle?: string
  icon: React.ElementType
  href: string
  isLoading?: boolean
}) {
  return (
    <Link href={href}>
      <Card className="transition-colors hover:bg-accent/50">
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
    </Link>
  )
}

export default function Home() {
  const { data: models, isLoading: modelsLoading } = useModels()
  const { data: training, isLoading: trainingLoading } = useTrainingJobs()
  const { data: metrics, isLoading: metricsLoading } = useMetrics()

  const totalModels = models?.total ?? 0
  const runningJobs =
    training?.items.filter((j) => j.status === "running").length ?? 0

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Dashboard</h2>
          <p className="text-muted-foreground">
            Overview of your MLX Model Hub
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <StatCard
            title="Total Models"
            value={totalModels}
            subtitle="Registered models"
            icon={Box}
            href="/models"
            isLoading={modelsLoading}
          />
          <StatCard
            title="Training Jobs"
            value={training?.total ?? 0}
            subtitle={`${runningJobs} running`}
            icon={GraduationCap}
            href="/training"
            isLoading={trainingLoading}
          />
          <StatCard
            title="Models Loaded"
            value={metrics?.models_loaded ?? 0}
            subtitle="Ready for inference"
            icon={Brain}
            href="/inference"
            isLoading={metricsLoading}
          />
          <StatCard
            title="Cache Size"
            value={formatBytes(metrics?.cache_size_bytes ?? 0)}
            subtitle="Local storage used"
            icon={Gauge}
            href="/metrics"
            isLoading={metricsLoading}
          />
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Quick Actions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <Link
                href="/models"
                className="block rounded-md border p-4 transition-colors hover:bg-accent"
              >
                <div className="font-medium">Download a Model</div>
                <div className="text-sm text-muted-foreground">
                  Browse and download MLX models from Hugging Face
                </div>
              </Link>
              <Link
                href="/training"
                className="block rounded-md border p-4 transition-colors hover:bg-accent"
              >
                <div className="font-medium">Start Training</div>
                <div className="text-sm text-muted-foreground">
                  Fine-tune a model with LoRA on your data
                </div>
              </Link>
              <Link
                href="/inference"
                className="block rounded-md border p-4 transition-colors hover:bg-accent"
              >
                <div className="font-medium">Run Inference</div>
                <div className="text-sm text-muted-foreground">
                  Test models in the interactive playground
                </div>
              </Link>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>System Status</CardTitle>
            </CardHeader>
            <CardContent>
              {metricsLoading ? (
                <div className="space-y-3">
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-4 w-1/2" />
                </div>
              ) : metrics ? (
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">
                      Active Inferences
                    </span>
                    <span className="font-medium">
                      {metrics.active_inferences}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Running Jobs</span>
                    <span className="font-medium">
                      {metrics.training_jobs_running}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Uptime</span>
                    <span className="font-medium">
                      {Math.floor(metrics.uptime_seconds / 3600)}h{" "}
                      {Math.floor((metrics.uptime_seconds % 3600) / 60)}m
                    </span>
                  </div>
                </div>
              ) : (
                <div className="text-center text-muted-foreground">
                  Unable to load metrics. Is the API running?
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </DashboardLayout>
  )
}
