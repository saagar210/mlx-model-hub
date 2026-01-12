"use client"

import { useState, useEffect, useCallback } from "react"
import { DashboardLayout } from "@/components/layout"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Progress } from "@/components/ui/progress"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert"
import {
  Search,
  Download,
  HardDrive,
  Clock,
  Heart,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Loader2,
  ExternalLink,
  TrendingUp,
  Sparkles,
} from "lucide-react"
import { toast } from "sonner"
import {
  searchDiscoverModels,
  getPopularModels,
  getRecentModels,
  checkModelCompatibility,
  startModelDownload,
  getDownloadStatus,
  DiscoveredModel,
  MemoryCompatibility,
  DownloadStatus,
} from "@/lib/api"

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B"
  const k = 1024
  const sizes = ["B", "KB", "MB", "GB", "TB"]
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i]
}

function formatNumber(num: number): string {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + "M"
  if (num >= 1000) return (num / 1000).toFixed(1) + "K"
  return num.toString()
}

interface ModelCardProps {
  model: DiscoveredModel
  onDownload: (model: DiscoveredModel) => void
  downloadStatus?: DownloadStatus
}

function ModelCard({ model, onDownload, downloadStatus }: ModelCardProps) {
  const isDownloading = downloadStatus?.status === "downloading" || downloadStatus?.status === "pending"
  const isCompleted = downloadStatus?.status === "completed"

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <CardTitle className="text-base font-medium line-clamp-1">
              {model.model_name}
            </CardTitle>
            <CardDescription className="text-xs">
              by {model.author}
            </CardDescription>
          </div>
          {model.quantization && (
            <Badge variant="secondary" className="shrink-0">
              {model.quantization}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <div className="flex items-center gap-1">
            <Download className="h-3 w-3" />
            {formatNumber(model.downloads)}
          </div>
          <div className="flex items-center gap-1">
            <Heart className="h-3 w-3" />
            {formatNumber(model.likes)}
          </div>
          <div className="flex items-center gap-1">
            <HardDrive className="h-3 w-3" />
            {model.size_gb.toFixed(2)} GB
          </div>
        </div>

        <div className="flex flex-wrap gap-1">
          {model.tags.slice(0, 4).map((tag) => (
            <Badge key={tag} variant="outline" className="text-xs">
              {tag}
            </Badge>
          ))}
          {model.tags.length > 4 && (
            <Badge variant="outline" className="text-xs">
              +{model.tags.length - 4}
            </Badge>
          )}
        </div>

        <div className="flex items-center justify-between pt-2">
          <div className="text-xs text-muted-foreground">
            ~{model.estimated_memory_gb.toFixed(1)} GB RAM
          </div>

          {isDownloading ? (
            <div className="flex items-center gap-2">
              <Progress value={downloadStatus?.progress_percent || 0} className="w-20" />
              <Loader2 className="h-4 w-4 animate-spin" />
            </div>
          ) : isCompleted ? (
            <Button variant="outline" size="sm" disabled>
              <CheckCircle className="h-4 w-4 mr-1 text-green-500" />
              Downloaded
            </Button>
          ) : (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onDownload(model)}
            >
              <Download className="h-4 w-4 mr-1" />
              Download
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

export default function DiscoverPage() {
  const [searchQuery, setSearchQuery] = useState("")
  const [sortBy, setSortBy] = useState("downloads")
  const [models, setModels] = useState<DiscoveredModel[]>([])
  const [popularModels, setPopularModels] = useState<DiscoveredModel[]>([])
  const [recentModels, setRecentModels] = useState<DiscoveredModel[]>([])
  const [loading, setLoading] = useState(true)
  const [searching, setSearching] = useState(false)
  const [page, setPage] = useState(1)
  const [totalCount, setTotalCount] = useState(0)

  // Download state
  const [downloadStatuses, setDownloadStatuses] = useState<Record<string, DownloadStatus>>({})
  const [selectedModel, setSelectedModel] = useState<DiscoveredModel | null>(null)
  const [compatibility, setCompatibility] = useState<MemoryCompatibility | null>(null)
  const [checkingCompatibility, setCheckingCompatibility] = useState(false)
  const [showDownloadDialog, setShowDownloadDialog] = useState(false)

  // Initial load
  useEffect(() => {
    async function loadInitialData() {
      try {
        const [popular, recent] = await Promise.all([
          getPopularModels(8),
          getRecentModels(8),
        ])
        setPopularModels(popular.models)
        setRecentModels(recent.models)
      } catch (error) {
        toast.error("Failed to load models")
      } finally {
        setLoading(false)
      }
    }
    loadInitialData()
  }, [])

  // Search handler
  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim()) {
      setModels([])
      return
    }

    setSearching(true)
    try {
      const result = await searchDiscoverModels(
        searchQuery,
        page,
        20,
        true,
        sortBy,
        "desc"
      )
      setModels(result.models)
      setTotalCount(result.total_count)
    } catch (error) {
      toast.error("Search failed")
    } finally {
      setSearching(false)
    }
  }, [searchQuery, page, sortBy])

  // Trigger search on query/sort change
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchQuery.trim()) {
        handleSearch()
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [searchQuery, sortBy, handleSearch])

  // Download handler
  const handleDownloadClick = async (model: DiscoveredModel) => {
    setSelectedModel(model)
    setCheckingCompatibility(true)
    setShowDownloadDialog(true)

    try {
      const compat = await checkModelCompatibility(model.model_id)
      setCompatibility(compat)
    } catch (error) {
      setCompatibility(null)
      toast.error("Failed to check compatibility")
    } finally {
      setCheckingCompatibility(false)
    }
  }

  const handleStartDownload = async () => {
    if (!selectedModel) return

    setShowDownloadDialog(false)

    try {
      const status = await startModelDownload(selectedModel.model_id)
      setDownloadStatuses(prev => ({
        ...prev,
        [selectedModel.model_id]: status,
      }))

      toast.success(`Started downloading ${selectedModel.model_name}`)

      // Poll for download status
      const pollInterval = setInterval(async () => {
        try {
          const newStatus = await getDownloadStatus(selectedModel.model_id)
          setDownloadStatuses(prev => ({
            ...prev,
            [selectedModel.model_id]: newStatus,
          }))

          if (newStatus.status === "completed") {
            clearInterval(pollInterval)
            toast.success(`Downloaded ${selectedModel.model_name}`)
          } else if (newStatus.status === "failed") {
            clearInterval(pollInterval)
            toast.error(`Download failed: ${newStatus.error}`)
          }
        } catch {
          clearInterval(pollInterval)
        }
      }, 2000)
    } catch (error) {
      toast.error("Failed to start download")
    }
  }

  const getCompatibilityIcon = (status: string) => {
    switch (status) {
      case "compatible":
        return <CheckCircle className="h-5 w-5 text-green-500" />
      case "tight":
        return <AlertTriangle className="h-5 w-5 text-yellow-500" />
      case "incompatible":
        return <XCircle className="h-5 w-5 text-red-500" />
      default:
        return null
    }
  }

  const getCompatibilityVariant = (status: string): "default" | "destructive" => {
    return status === "incompatible" ? "destructive" : "default"
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Discover Models</h2>
          <p className="text-muted-foreground">
            Browse and download MLX models from HuggingFace
          </p>
        </div>

        {/* Search */}
        <div className="flex gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search MLX models..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>
          <Select value={sortBy} onValueChange={setSortBy}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="Sort by" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="downloads">Downloads</SelectItem>
              <SelectItem value="likes">Likes</SelectItem>
              <SelectItem value="lastModified">Recently Updated</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Search Results */}
        {searchQuery && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold">
                Search Results {totalCount > 0 && `(${totalCount})`}
              </h3>
            </div>
            {searching ? (
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                {[...Array(4)].map((_, i) => (
                  <Card key={i}>
                    <CardHeader>
                      <Skeleton className="h-4 w-3/4" />
                      <Skeleton className="h-3 w-1/2" />
                    </CardHeader>
                    <CardContent>
                      <Skeleton className="h-3 w-full mb-2" />
                      <Skeleton className="h-8 w-full" />
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : models.length > 0 ? (
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                {models.map((model) => (
                  <ModelCard
                    key={model.model_id}
                    model={model}
                    onDownload={handleDownloadClick}
                    downloadStatus={downloadStatuses[model.model_id]}
                  />
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                No models found for "{searchQuery}"
              </div>
            )}
          </div>
        )}

        {/* Popular Models */}
        {!searchQuery && (
          <>
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5" />
                <h3 className="font-semibold">Popular Models</h3>
              </div>
              {loading ? (
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                  {[...Array(4)].map((_, i) => (
                    <Card key={i}>
                      <CardHeader>
                        <Skeleton className="h-4 w-3/4" />
                        <Skeleton className="h-3 w-1/2" />
                      </CardHeader>
                      <CardContent>
                        <Skeleton className="h-3 w-full mb-2" />
                        <Skeleton className="h-8 w-full" />
                      </CardContent>
                    </Card>
                  ))}
                </div>
              ) : (
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                  {popularModels.map((model) => (
                    <ModelCard
                      key={model.model_id}
                      model={model}
                      onDownload={handleDownloadClick}
                      downloadStatus={downloadStatuses[model.model_id]}
                    />
                  ))}
                </div>
              )}
            </div>

            {/* Recent Models */}
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <Sparkles className="h-5 w-5" />
                <h3 className="font-semibold">Recently Updated</h3>
              </div>
              {loading ? (
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                  {[...Array(4)].map((_, i) => (
                    <Card key={i}>
                      <CardHeader>
                        <Skeleton className="h-4 w-3/4" />
                        <Skeleton className="h-3 w-1/2" />
                      </CardHeader>
                      <CardContent>
                        <Skeleton className="h-3 w-full mb-2" />
                        <Skeleton className="h-8 w-full" />
                      </CardContent>
                    </Card>
                  ))}
                </div>
              ) : (
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                  {recentModels.map((model) => (
                    <ModelCard
                      key={model.model_id}
                      model={model}
                      onDownload={handleDownloadClick}
                      downloadStatus={downloadStatuses[model.model_id]}
                    />
                  ))}
                </div>
              )}
            </div>
          </>
        )}

        {/* Download Dialog */}
        <Dialog open={showDownloadDialog} onOpenChange={setShowDownloadDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Download Model</DialogTitle>
              <DialogDescription>
                {selectedModel?.model_id}
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-4">
              {/* Model Info */}
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">Size:</span>
                  <span className="ml-2 font-medium">
                    {selectedModel?.size_gb.toFixed(2)} GB
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground">Memory:</span>
                  <span className="ml-2 font-medium">
                    ~{selectedModel?.estimated_memory_gb.toFixed(1)} GB
                  </span>
                </div>
                {selectedModel?.quantization && (
                  <div>
                    <span className="text-muted-foreground">Quantization:</span>
                    <span className="ml-2 font-medium">
                      {selectedModel.quantization}
                    </span>
                  </div>
                )}
              </div>

              {/* Compatibility Check */}
              {checkingCompatibility ? (
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Checking compatibility...
                </div>
              ) : compatibility && (
                <Alert variant={getCompatibilityVariant(compatibility.status)}>
                  <div className="flex items-start gap-2">
                    {getCompatibilityIcon(compatibility.status)}
                    <div>
                      <AlertTitle className="capitalize">
                        {compatibility.status}
                      </AlertTitle>
                      <AlertDescription className="text-sm">
                        {compatibility.message}
                        {compatibility.warning && (
                          <p className="mt-1 font-medium">{compatibility.warning}</p>
                        )}
                      </AlertDescription>
                    </div>
                  </div>
                </Alert>
              )}

              {/* HuggingFace Link */}
              <a
                href={`https://huggingface.co/${selectedModel?.model_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-sm text-primary hover:underline"
              >
                View on HuggingFace
                <ExternalLink className="h-3 w-3" />
              </a>
            </div>

            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setShowDownloadDialog(false)}
              >
                Cancel
              </Button>
              <Button
                onClick={handleStartDownload}
                disabled={checkingCompatibility || compatibility?.status === "incompatible"}
              >
                <Download className="h-4 w-4 mr-2" />
                Download
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </DashboardLayout>
  )
}
