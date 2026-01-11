"use client"

import { useState } from "react"
import { DashboardLayout } from "@/components/layout"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import {
  useModels,
  useDownloadModel,
  useDeleteModel,
  useLoadModel,
  useUnloadModel,
} from "@/lib/hooks"
import { Model } from "@/lib/api"
import {
  Download,
  Trash2,
  Play,
  Square,
  RefreshCw,
  Plus,
  ExternalLink,
} from "lucide-react"
import { toast } from "sonner"
import Link from "next/link"

function formatBytes(bytes?: number): string {
  if (!bytes) return "Unknown"
  const k = 1024
  const sizes = ["B", "KB", "MB", "GB", "TB"]
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i]
}

function formatDate(dateString?: string): string {
  if (!dateString) return "Never"
  return new Date(dateString).toLocaleDateString("en-US", {
    month: "short",
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

function ModelRow({
  model,
  onLoad,
  onUnload,
  onDelete,
}: {
  model: Model
  onLoad: (id: string) => void
  onUnload: (id: string) => void
  onDelete: (id: string) => void
}) {
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)

  return (
    <TableRow>
      <TableCell>
        <Link
          href={`/models/${model.id}`}
          className="font-medium hover:underline"
        >
          {model.name}
        </Link>
        <div className="text-sm text-muted-foreground">{model.repository}</div>
      </TableCell>
      <TableCell>
        <StatusBadge status={model.status} />
        {model.status === "downloading" && model.download_progress && (
          <Progress value={model.download_progress} className="mt-2 h-1 w-20" />
        )}
      </TableCell>
      <TableCell>{formatBytes(model.size_bytes)}</TableCell>
      <TableCell>{model.quantization || "None"}</TableCell>
      <TableCell>{formatDate(model.last_used)}</TableCell>
      <TableCell>
        <div className="flex items-center gap-2">
          {model.cached ? (
            <>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => onLoad(model.id)}
                title="Load model"
              >
                <Play className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => onUnload(model.id)}
                title="Unload model"
              >
                <Square className="h-4 w-4" />
              </Button>
            </>
          ) : (
            <Button
              variant="ghost"
              size="icon"
              disabled={model.status === "downloading"}
              title="Download model"
            >
              <Download className="h-4 w-4" />
            </Button>
          )}
          <a
            href={`https://huggingface.co/${model.repository}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex"
          >
            <Button variant="ghost" size="icon" title="View on Hugging Face">
              <ExternalLink className="h-4 w-4" />
            </Button>
          </a>
          <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
            <DialogTrigger asChild>
              <Button variant="ghost" size="icon" title="Delete model">
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Delete Model</DialogTitle>
                <DialogDescription>
                  Are you sure you want to delete {model.name}? This will remove
                  the cached model files from your local storage.
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => setDeleteDialogOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  onClick={() => {
                    onDelete(model.id)
                    setDeleteDialogOpen(false)
                  }}
                >
                  Delete
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </TableCell>
    </TableRow>
  )
}

function DownloadModelDialog() {
  const [open, setOpen] = useState(false)
  const [repository, setRepository] = useState("")
  const downloadModel = useDownloadModel()

  const handleDownload = () => {
    if (!repository.trim()) return
    downloadModel.mutate(repository, {
      onSuccess: () => {
        toast.success(`Started downloading ${repository}`)
        setRepository("")
        setOpen(false)
      },
      onError: (error) => {
        toast.error(`Failed to download: ${error.message}`)
      },
    })
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          Download Model
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Download Model</DialogTitle>
          <DialogDescription>
            Enter a Hugging Face repository ID to download an MLX model.
          </DialogDescription>
        </DialogHeader>
        <div className="py-4">
          <Input
            placeholder="mlx-community/Llama-3.2-3B-Instruct-4bit"
            value={repository}
            onChange={(e) => setRepository(e.target.value)}
          />
          <p className="mt-2 text-sm text-muted-foreground">
            Browse models at{" "}
            <a
              href="https://huggingface.co/mlx-community"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              huggingface.co/mlx-community
            </a>
          </p>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleDownload}
            disabled={!repository.trim() || downloadModel.isPending}
          >
            {downloadModel.isPending ? (
              <>
                <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                Downloading...
              </>
            ) : (
              <>
                <Download className="mr-2 h-4 w-4" />
                Download
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function ModelsPage() {
  const { data, isLoading, refetch } = useModels()
  const loadModel = useLoadModel()
  const unloadModel = useUnloadModel()
  const deleteModel = useDeleteModel()

  const handleLoad = (id: string) => {
    loadModel.mutate(id, {
      onSuccess: () => toast.success("Model loaded"),
      onError: (error) => toast.error(`Failed to load: ${error.message}`),
    })
  }

  const handleUnload = (id: string) => {
    unloadModel.mutate(id, {
      onSuccess: () => toast.success("Model unloaded"),
      onError: (error) => toast.error(`Failed to unload: ${error.message}`),
    })
  }

  const handleDelete = (id: string) => {
    deleteModel.mutate(id, {
      onSuccess: () => toast.success("Model deleted"),
      onError: (error) => toast.error(`Failed to delete: ${error.message}`),
    })
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-3xl font-bold tracking-tight">Models</h2>
            <p className="text-muted-foreground">
              Manage your MLX models from Hugging Face
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="icon" onClick={() => refetch()}>
              <RefreshCw className="h-4 w-4" />
            </Button>
            <DownloadModelDialog />
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>All Models</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : data?.models.length === 0 ? (
              <div className="py-8 text-center text-muted-foreground">
                <p>No models yet.</p>
                <p className="mt-2">
                  Click "Download Model" to get started with MLX models.
                </p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Model</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Size</TableHead>
                    <TableHead>Quantization</TableHead>
                    <TableHead>Last Used</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data?.models.map((model) => (
                    <ModelRow
                      key={model.id}
                      model={model}
                      onLoad={handleLoad}
                      onUnload={handleUnload}
                      onDelete={handleDelete}
                    />
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  )
}
