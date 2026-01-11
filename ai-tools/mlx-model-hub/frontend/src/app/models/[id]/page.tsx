"use client"

import { use } from "react"
import Link from "next/link"
import { DashboardLayout } from "@/components/layout"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { useModel, useLoadModel, useUnloadModel, useDeleteModel } from "@/lib/hooks"
import { Model } from "@/lib/api"
import {
  ArrowLeft,
  Play,
  Square,
  Trash2,
  ExternalLink,
  Download,
} from "lucide-react"
import { toast } from "sonner"
import { useRouter } from "next/navigation"

function formatBytes(bytes?: number): string {
  if (!bytes) return "Unknown"
  const k = 1024
  const sizes = ["B", "KB", "MB", "GB", "TB"]
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i]
}

function formatDate(dateString?: string): string {
  if (!dateString) return "Never"
  return new Date(dateString).toLocaleString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

function StatusBadge({ status }: { status: Model["status"] }) {
  const variants: Record<Model["status"], "default" | "secondary" | "destructive" | "outline"> = {
    available: "outline",
    downloading: "secondary",
    cached: "default",
    error: "destructive",
  }

  return <Badge variant={variants[status]}>{status}</Badge>
}

export default function ModelDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)
  const router = useRouter()
  const { data: model, isLoading, error } = useModel(id)
  const loadModel = useLoadModel()
  const unloadModel = useUnloadModel()
  const deleteModel = useDeleteModel()

  const handleLoad = () => {
    loadModel.mutate(id, {
      onSuccess: () => toast.success("Model loaded"),
      onError: (err) => toast.error(`Failed to load: ${err.message}`),
    })
  }

  const handleUnload = () => {
    unloadModel.mutate(id, {
      onSuccess: () => toast.success("Model unloaded"),
      onError: (err) => toast.error(`Failed to unload: ${err.message}`),
    })
  }

  const handleDelete = () => {
    deleteModel.mutate(id, {
      onSuccess: () => {
        toast.success("Model deleted")
        router.push("/models")
      },
      onError: (err) => toast.error(`Failed to delete: ${err.message}`),
    })
  }

  if (error) {
    return (
      <DashboardLayout>
        <div className="space-y-6">
          <Link
            href="/models"
            className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Models
          </Link>
          <Card>
            <CardContent className="py-8 text-center">
              <p className="text-destructive">Failed to load model: {error.message}</p>
            </CardContent>
          </Card>
        </div>
      </DashboardLayout>
    )
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <Link
          href="/models"
          className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Models
        </Link>

        {isLoading ? (
          <div className="space-y-4">
            <Skeleton className="h-10 w-1/3" />
            <Skeleton className="h-64 w-full" />
          </div>
        ) : model ? (
          <>
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-3xl font-bold tracking-tight">
                  {model.name}
                </h2>
                <p className="text-muted-foreground">{model.repository}</p>
              </div>
              <div className="flex items-center gap-2">
                {model.cached ? (
                  <>
                    <Button onClick={handleLoad} disabled={loadModel.isPending}>
                      <Play className="mr-2 h-4 w-4" />
                      Load
                    </Button>
                    <Button
                      variant="outline"
                      onClick={handleUnload}
                      disabled={unloadModel.isPending}
                    >
                      <Square className="mr-2 h-4 w-4" />
                      Unload
                    </Button>
                  </>
                ) : (
                  <Button disabled={model.status === "downloading"}>
                    <Download className="mr-2 h-4 w-4" />
                    Download
                  </Button>
                )}
                <Button
                  variant="destructive"
                  onClick={handleDelete}
                  disabled={deleteModel.isPending}
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  Delete
                </Button>
              </div>
            </div>

            <div className="grid gap-6 md:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Model Information</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Status</span>
                    <StatusBadge status={model.status} />
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Size</span>
                    <span>{formatBytes(model.size_bytes)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Quantization</span>
                    <span>{model.quantization || "None"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Cached</span>
                    <span>{model.cached ? "Yes" : "No"}</span>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Timestamps</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Created</span>
                    <span>{formatDate(model.created_at)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Updated</span>
                    <span>{formatDate(model.updated_at)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Last Used</span>
                    <span>{formatDate(model.last_used)}</span>
                  </div>
                </CardContent>
              </Card>

              {model.description && (
                <Card className="md:col-span-2">
                  <CardHeader>
                    <CardTitle>Description</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-muted-foreground">{model.description}</p>
                  </CardContent>
                </Card>
              )}

              <Card className="md:col-span-2">
                <CardHeader>
                  <CardTitle>External Links</CardTitle>
                </CardHeader>
                <CardContent>
                  <a
                    href={`https://huggingface.co/${model.repository}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center text-primary hover:underline"
                  >
                    <ExternalLink className="mr-2 h-4 w-4" />
                    View on Hugging Face
                  </a>
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader>
                <CardTitle>Quick Actions</CardTitle>
              </CardHeader>
              <CardContent className="flex gap-4">
                <Link href={`/inference?model=${model.id}`}>
                  <Button variant="outline">Run Inference</Button>
                </Link>
                <Link href={`/training?base_model=${model.id}`}>
                  <Button variant="outline">Fine-tune Model</Button>
                </Link>
              </CardContent>
            </Card>
          </>
        ) : null}
      </div>
    </DashboardLayout>
  )
}
