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
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import {
  useTrainingJobs,
  useCreateTrainingJob,
  useCancelTrainingJob,
  useModels,
} from "@/lib/hooks"
import { TrainingJob, TrainingConfig } from "@/lib/api"
import { RefreshCw, Plus, XCircle, CheckCircle, Clock, AlertCircle } from "lucide-react"
import { toast } from "sonner"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

function formatDate(dateString?: string): string {
  if (!dateString) return "-"
  return new Date(dateString).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

function StatusBadge({ status }: { status: TrainingJob["status"] }) {
  const config: Record<
    TrainingJob["status"],
    { variant: "default" | "secondary" | "destructive" | "outline"; icon: React.ReactNode }
  > = {
    pending: { variant: "secondary", icon: <Clock className="mr-1 h-3 w-3" /> },
    running: { variant: "default", icon: <RefreshCw className="mr-1 h-3 w-3 animate-spin" /> },
    completed: { variant: "outline", icon: <CheckCircle className="mr-1 h-3 w-3 text-green-500" /> },
    failed: { variant: "destructive", icon: <AlertCircle className="mr-1 h-3 w-3" /> },
    cancelled: { variant: "secondary", icon: <XCircle className="mr-1 h-3 w-3" /> },
  }

  const { variant, icon } = config[status]

  return (
    <Badge variant={variant} className="flex w-fit items-center">
      {icon}
      {status}
    </Badge>
  )
}

function TrainingJobRow({
  job,
  onCancel,
}: {
  job: TrainingJob
  onCancel: (id: string) => void
}) {
  const progress = job.metrics
    ? (job.metrics.epoch / job.config.num_epochs) * 100
    : 0

  return (
    <TableRow>
      <TableCell className="font-mono text-xs">{job.id.slice(0, 8)}</TableCell>
      <TableCell>{job.config.base_model}</TableCell>
      <TableCell>
        <StatusBadge status={job.status} />
      </TableCell>
      <TableCell>
        {job.status === "running" && job.metrics ? (
          <div className="space-y-1">
            <div className="flex justify-between text-xs">
              <span>
                Epoch {job.metrics.epoch}/{job.config.num_epochs}
              </span>
              <span>{progress.toFixed(0)}%</span>
            </div>
            <Progress value={progress} className="h-1" />
          </div>
        ) : job.status === "completed" ? (
          "100%"
        ) : (
          "-"
        )}
      </TableCell>
      <TableCell>
        {job.metrics?.loss !== undefined ? job.metrics.loss.toFixed(4) : "-"}
      </TableCell>
      <TableCell>{formatDate(job.started_at)}</TableCell>
      <TableCell>
        {(job.status === "pending" || job.status === "running") && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onCancel(job.id)}
            className="text-destructive hover:text-destructive"
          >
            <XCircle className="mr-1 h-4 w-4" />
            Cancel
          </Button>
        )}
      </TableCell>
    </TableRow>
  )
}

function CreateTrainingJobDialog() {
  const [open, setOpen] = useState(false)
  const [config, setConfig] = useState<Partial<TrainingConfig>>({
    num_epochs: 3,
    batch_size: 4,
    learning_rate: 1e-4,
    use_lora: true,
    lora_rank: 8,
    lora_alpha: 16,
  })
  const { data: models } = useModels()
  const createJob = useCreateTrainingJob()

  const handleCreate = () => {
    if (!config.base_model || !config.dataset_path || !config.output_dir) {
      toast.error("Please fill in all required fields")
      return
    }
    createJob.mutate(config as TrainingConfig, {
      onSuccess: () => {
        toast.success("Training job created")
        setOpen(false)
      },
      onError: (error) => {
        toast.error(`Failed to create job: ${error.message}`)
      },
    })
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          New Training Job
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Create Training Job</DialogTitle>
          <DialogDescription>
            Fine-tune a model using LoRA on your dataset.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="base_model">Base Model</Label>
            <Select
              value={config.base_model}
              onValueChange={(value) =>
                setConfig({ ...config, base_model: value })
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="Select a model" />
              </SelectTrigger>
              <SelectContent>
                {models?.items?.map((model) => (
                  <SelectItem key={model.id} value={model.base_model}>
                    {model.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="dataset_path">Dataset Path</Label>
            <Input
              id="dataset_path"
              placeholder="/path/to/dataset.jsonl"
              value={config.dataset_path || ""}
              onChange={(e) =>
                setConfig({ ...config, dataset_path: e.target.value })
              }
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="output_dir">Output Directory</Label>
            <Input
              id="output_dir"
              placeholder="/path/to/output"
              value={config.output_dir || ""}
              onChange={(e) =>
                setConfig({ ...config, output_dir: e.target.value })
              }
            />
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div className="grid gap-2">
              <Label htmlFor="num_epochs">Epochs</Label>
              <Input
                id="num_epochs"
                type="number"
                value={config.num_epochs}
                onChange={(e) =>
                  setConfig({ ...config, num_epochs: parseInt(e.target.value) })
                }
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="batch_size">Batch Size</Label>
              <Input
                id="batch_size"
                type="number"
                value={config.batch_size}
                onChange={(e) =>
                  setConfig({ ...config, batch_size: parseInt(e.target.value) })
                }
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="learning_rate">Learning Rate</Label>
              <Input
                id="learning_rate"
                type="number"
                step="0.0001"
                value={config.learning_rate}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    learning_rate: parseFloat(e.target.value),
                  })
                }
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="grid gap-2">
              <Label htmlFor="lora_rank">LoRA Rank</Label>
              <Input
                id="lora_rank"
                type="number"
                value={config.lora_rank}
                onChange={(e) =>
                  setConfig({ ...config, lora_rank: parseInt(e.target.value) })
                }
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="lora_alpha">LoRA Alpha</Label>
              <Input
                id="lora_alpha"
                type="number"
                value={config.lora_alpha}
                onChange={(e) =>
                  setConfig({ ...config, lora_alpha: parseInt(e.target.value) })
                }
              />
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button onClick={handleCreate} disabled={createJob.isPending}>
            {createJob.isPending ? (
              <>
                <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                Creating...
              </>
            ) : (
              "Start Training"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function TrainingPage() {
  const { data, isLoading, refetch } = useTrainingJobs()
  const cancelJob = useCancelTrainingJob()

  const handleCancel = (id: string) => {
    cancelJob.mutate(id, {
      onSuccess: () => toast.success("Training job cancelled"),
      onError: (error) => toast.error(`Failed to cancel: ${error.message}`),
    })
  }

  const runningJobs = data?.items.filter((j) => j.status === "running").length ?? 0
  const completedJobs = data?.items.filter((j) => j.status === "completed").length ?? 0

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-3xl font-bold tracking-tight">Training</h2>
            <p className="text-muted-foreground">
              Fine-tune models with LoRA on Apple Silicon
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="icon" onClick={() => refetch()}>
              <RefreshCw className="h-4 w-4" />
            </Button>
            <CreateTrainingJobDialog />
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Total Jobs</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{data?.total ?? 0}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Running</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{runningJobs}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Completed</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{completedJobs}</div>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Training Jobs</CardTitle>
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
                <p>No training jobs yet.</p>
                <p className="mt-2">
                  Click "New Training Job" to fine-tune a model.
                </p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ID</TableHead>
                    <TableHead>Base Model</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Progress</TableHead>
                    <TableHead>Loss</TableHead>
                    <TableHead>Started</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data?.items.map((job) => (
                    <TrainingJobRow
                      key={job.id}
                      job={job}
                      onCancel={handleCancel}
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
