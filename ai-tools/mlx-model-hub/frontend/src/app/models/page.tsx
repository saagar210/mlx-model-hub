"use client"

import { useState } from "react"
import { DashboardLayout } from "@/components/layout"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { useModels, useDeleteModel, useScanExports } from "@/lib/hooks"
import { Model } from "@/lib/api"
import { Trash2, RefreshCw, Plus, Eye, Scan } from "lucide-react"
import { toast } from "sonner"
import Link from "next/link"

function formatDate(dateString?: string): string {
  if (!dateString) return "Never"
  return new Date(dateString).toLocaleDateString("en-US", {
    month: "short",
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

function ModelRow({
  model,
  onDelete,
}: {
  model: Model
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
        {model.description && (
          <div className="text-sm text-muted-foreground line-clamp-1">
            {model.description}
          </div>
        )}
      </TableCell>
      <TableCell>
        <TaskTypeBadge taskType={model.task_type} />
      </TableCell>
      <TableCell className="font-mono text-sm">{model.base_model}</TableCell>
      <TableCell>{model.version_count}</TableCell>
      <TableCell>{formatDate(model.created_at)}</TableCell>
      <TableCell>
        <div className="flex items-center gap-2">
          <Link href={`/models/${model.id}`}>
            <Button variant="ghost" size="icon" title="View details">
              <Eye className="h-4 w-4" />
            </Button>
          </Link>
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
                  Are you sure you want to delete {model.name}? This action
                  cannot be undone.
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

function CreateModelDialog({ onSuccess }: { onSuccess: () => void }) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState("")
  const [taskType, setTaskType] = useState("text-generation")
  const [baseModel, setBaseModel] = useState("")
  const [description, setDescription] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleCreate = async () => {
    if (!name.trim() || !baseModel.trim()) return
    setIsSubmitting(true)
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/models`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name,
            task_type: taskType,
            base_model: baseModel,
            description: description || undefined,
          }),
        }
      )
      if (!response.ok) {
        throw new Error("Failed to create model")
      }
      toast.success(`Created model ${name}`)
      setName("")
      setBaseModel("")
      setDescription("")
      setOpen(false)
      onSuccess()
    } catch (error) {
      toast.error(`Failed to create model: ${error}`)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          Create Model
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create Model</DialogTitle>
          <DialogDescription>
            Register a new MLX model for training and inference.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              placeholder="My Model"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="taskType">Task Type</Label>
            <Select value={taskType} onValueChange={setTaskType}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="text-generation">Text Generation</SelectItem>
                <SelectItem value="chat">Chat</SelectItem>
                <SelectItem value="classification">Classification</SelectItem>
                <SelectItem value="summarization">Summarization</SelectItem>
                <SelectItem value="question-answering">Question Answering</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="baseModel">Base Model</Label>
            <Input
              id="baseModel"
              placeholder="mlx-community/Llama-3.2-3B-Instruct-4bit"
              value={baseModel}
              onChange={(e) => setBaseModel(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="description">Description (optional)</Label>
            <Input
              id="description"
              placeholder="A fine-tuned model for..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleCreate}
            disabled={!name.trim() || !baseModel.trim() || isSubmitting}
          >
            {isSubmitting ? (
              <>
                <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                Creating...
              </>
            ) : (
              "Create"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function ModelsPage() {
  const { data, isLoading, refetch } = useModels()
  const deleteModel = useDeleteModel()
  const scan = useScanExports()

  const handleDelete = (id: string) => {
    deleteModel.mutate(id, {
      onSuccess: () => toast.success("Model deleted"),
      onError: (error) => toast.error(`Failed to delete: ${error.message}`),
    })
  }

  const handleScan = () => {
    scan.mutate(undefined, {
      onSuccess: (data) => {
        toast.success(`Scanned exports: ${data.discovered} found, ${data.registered} registered`)
        refetch()
      },
      onError: (error) => toast.error(`Scan failed: ${error.message}`),
    })
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-3xl font-bold tracking-tight">Models</h2>
            <p className="text-muted-foreground">
              Manage your MLX models for training and inference
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              onClick={handleScan}
              disabled={scan.isPending}
            >
              <Scan className={`mr-2 h-4 w-4 ${scan.isPending ? "animate-spin" : ""}`} />
              Sync to Unified MLX
            </Button>
            <Button variant="outline" size="icon" onClick={() => refetch()}>
              <RefreshCw className="h-4 w-4" />
            </Button>
            <CreateModelDialog onSuccess={() => refetch()} />
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
            ) : data?.items.length === 0 ? (
              <div className="py-8 text-center text-muted-foreground">
                <p>No models yet.</p>
                <p className="mt-2">
                  Click "Create Model" to register a new model.
                </p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Model</TableHead>
                    <TableHead>Task Type</TableHead>
                    <TableHead>Base Model</TableHead>
                    <TableHead>Versions</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data?.items.map((model) => (
                    <ModelRow
                      key={model.id}
                      model={model}
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
