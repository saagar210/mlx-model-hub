"use client"

import { use } from "react"
import Link from "next/link"
import { DashboardLayout } from "@/components/layout"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { useModel, useDeleteModel } from "@/lib/hooks"
import {
  ArrowLeft,
  Trash2,
  ExternalLink,
  Tag,
} from "lucide-react"
import { toast } from "sonner"
import { useRouter } from "next/navigation"

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

function TaskTypeBadge({ taskType }: { taskType: string }) {
  const variants: Record<string, "default" | "secondary" | "outline"> = {
    "text-generation": "default",
    "chat": "default",
    "classification": "secondary",
    "summarization": "secondary",
    "question-answering": "outline",
  }

  return (
    <Badge variant={variants[taskType] || "secondary"}>
      {taskType.replace(/-/g, " ")}
    </Badge>
  )
}

export default function ModelDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)
  const router = useRouter()
  const { data: model, isLoading, error } = useModel(id)
  const deleteModel = useDeleteModel()

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
                <p className="text-muted-foreground font-mono text-sm">
                  {model.base_model}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Link href={`/inference?model=${model.id}`}>
                  <Button>Run Inference</Button>
                </Link>
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
                    <span className="text-muted-foreground">Task Type</span>
                    <TaskTypeBadge taskType={model.task_type} />
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Base Model</span>
                    <span className="font-mono text-sm">{model.base_model}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Versions</span>
                    <span>{model.version_count}</span>
                  </div>
                  {model.mlflow_experiment_id && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">MLflow Experiment</span>
                      <span className="font-mono text-sm">{model.mlflow_experiment_id}</span>
                    </div>
                  )}
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

              {Object.keys(model.tags).length > 0 && (
                <Card className="md:col-span-2">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Tag className="h-4 w-4" />
                      Tags
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(model.tags).map(([key, value]) => (
                        <Badge key={key} variant="outline">
                          {key}: {value}
                        </Badge>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              <Card className="md:col-span-2">
                <CardHeader>
                  <CardTitle>External Links</CardTitle>
                </CardHeader>
                <CardContent>
                  <a
                    href={`https://huggingface.co/${model.base_model}`}
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
