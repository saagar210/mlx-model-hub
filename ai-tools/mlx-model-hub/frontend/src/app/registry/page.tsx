"use client"

import { useState } from "react"
import { DashboardLayout } from "@/components/layout"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Checkbox } from "@/components/ui/checkbox"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import {
  useRegistryStatus,
  useAdminHealth,
  useUnregisterModel,
  usePreloadModel,
  useScanExports,
} from "@/lib/hooks"
import {
  Server,
  Trash2,
  Zap,
  RefreshCw,
  CheckCircle,
  XCircle,
  AlertCircle,
  Loader2,
  Filter,
  MessageSquare,
} from "lucide-react"
import { toast } from "sonner"
import Link from "next/link"

export default function RegistryPage() {
  const [showOnlyMlxHub, setShowOnlyMlxHub] = useState(true)
  const [selectedModels, setSelectedModels] = useState<Set<string>>(new Set())
  const [loadingModels, setLoadingModels] = useState<Set<string>>(new Set())

  const { data: registry, isLoading, error, refetch } = useRegistryStatus(
    showOnlyMlxHub ? "mlx-model-hub" : undefined
  )
  const { data: health } = useAdminHealth()
  const unregister = useUnregisterModel()
  const preload = usePreloadModel()
  const scan = useScanExports()

  const handleUnregister = (name: string) => {
    setLoadingModels(prev => new Set(prev).add(name))
    unregister.mutate(name, {
      onSuccess: () => {
        toast.success(`${name} unregistered`)
        setSelectedModels(prev => {
          const next = new Set(prev)
          next.delete(name)
          return next
        })
      },
      onError: (err) => {
        const message = err.message.toLowerCase()
        if (message.includes("404") || message.includes("not found")) {
          toast.error(`${name} not found in registry`)
        } else {
          toast.error(`Failed to unregister: ${err.message}`)
        }
      },
      onSettled: () => {
        setLoadingModels(prev => {
          const next = new Set(prev)
          next.delete(name)
          return next
        })
      },
    })
  }

  const handlePreload = (name: string) => {
    setLoadingModels(prev => new Set(prev).add(name))
    preload.mutate(name, {
      onSuccess: () => toast.success(`${name} loaded into memory`),
      onError: (err) => {
        const message = err.message.toLowerCase()
        if (message.includes("404") || message.includes("not found")) {
          toast.error(`${name} not found in registry`)
        } else if (message.includes("already loaded")) {
          toast.info(`${name} is already loaded`)
        } else {
          toast.error(`Failed to preload: ${err.message}`)
        }
      },
      onSettled: () => {
        setLoadingModels(prev => {
          const next = new Set(prev)
          next.delete(name)
          return next
        })
      },
    })
  }

  const handleBatchPreload = () => {
    const unloadedSelected = registry?.models
      ?.filter(m => selectedModels.has(m.name) && !m.loaded)
      .map(m => m.name) || []

    if (unloadedSelected.length === 0) {
      toast.info("No unloaded models selected")
      return
    }

    unloadedSelected.forEach(name => handlePreload(name))
    toast.info(`Pre-loading ${unloadedSelected.length} models...`)
  }

  const handleBatchUnregister = () => {
    if (selectedModels.size === 0) {
      toast.info("No models selected")
      return
    }

    const count = selectedModels.size
    selectedModels.forEach(name => handleUnregister(name))
    toast.info(`Unregistering ${count} models...`)
  }

  const handleScan = () => {
    scan.mutate(undefined, {
      onSuccess: (data) => {
        if (data.registered === 0) {
          toast.info(`Scanned: ${data.discovered} found, but none needed registration`)
        } else {
          toast.success(`Scanned: ${data.discovered} found, ${data.registered} registered`)
        }
      },
      onError: (err) => {
        const message = err.message.toLowerCase()
        if (message.includes("404") || message.includes("not found")) {
          toast.error("Scan endpoint not available")
        } else {
          toast.error(`Scan failed: ${err.message}`)
        }
      },
    })
  }

  const handleRefresh = () => {
    refetch()
    toast.info("Registry refreshed")
  }

  const toggleModelSelection = (name: string) => {
    setSelectedModels(prev => {
      const next = new Set(prev)
      if (next.has(name)) {
        next.delete(name)
      } else {
        next.add(name)
      }
      return next
    })
  }

  const toggleSelectAll = () => {
    if (!registry?.models) return

    if (selectedModels.size === registry.models.length) {
      setSelectedModels(new Set())
    } else {
      setSelectedModels(new Set(registry.models.map(m => m.name)))
    }
  }

  const inferenceServerStatus = health?.status === "ok" ? "online" : "offline"
  const allSelected = registry?.models && selectedModels.size === registry.models.length

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-3xl font-bold tracking-tight">Model Registry</h2>
            <p className="text-muted-foreground">
              Manage models registered in unified-mlx-app
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              onClick={handleScan}
              disabled={scan.isPending}
            >
              {scan.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 h-4 w-4" />
              )}
              Scan Exports
            </Button>
            <Button
              variant="outline"
              onClick={handleRefresh}
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              Refresh
            </Button>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Inference Server</CardTitle>
              <Server className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-2">
                {inferenceServerStatus === "online" ? (
                  <>
                    <CheckCircle className="h-4 w-4 text-green-500" />
                    <span className="text-2xl font-bold">Online</span>
                  </>
                ) : (
                  <>
                    <XCircle className="h-4 w-4 text-red-500" />
                    <span className="text-2xl font-bold">Offline</span>
                  </>
                )}
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                unified-mlx-app status
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Models</CardTitle>
              <Server className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {health?.models_count ?? 0}
              </div>
              <p className="text-xs text-muted-foreground">
                Registered in inference server
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Loaded Models</CardTitle>
              <Zap className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {health?.loaded_count ?? 0}
              </div>
              <p className="text-xs text-muted-foreground">
                Currently in memory
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Filter and Batch Actions */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center space-x-2">
              <Switch
                id="filter-mlxhub"
                checked={showOnlyMlxHub}
                onCheckedChange={setShowOnlyMlxHub}
              />
              <Label htmlFor="filter-mlxhub" className="flex items-center gap-2">
                <Filter className="h-4 w-4" />
                Show only mlx-model-hub models
              </Label>
            </div>
          </div>

          {selectedModels.size > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">
                {selectedModels.size} selected
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={handleBatchPreload}
              >
                <Zap className="mr-2 h-4 w-4" />
                Pre-load Selected
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={handleBatchUnregister}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Unregister Selected
              </Button>
            </div>
          )}
        </div>

        {error ? (
          <Card>
            <CardContent className="py-8 text-center">
              <AlertCircle className="mx-auto h-12 w-12 text-destructive mb-4" />
              <p className="text-destructive">
                Failed to load registry: {error.message}
              </p>
              <p className="text-sm text-muted-foreground mt-2">
                Make sure unified-mlx-app is running on port 8080
              </p>
              <Button variant="outline" className="mt-4" onClick={handleRefresh}>
                <RefreshCw className="mr-2 h-4 w-4" />
                Retry
              </Button>
            </CardContent>
          </Card>
        ) : isLoading ? (
          <div className="space-y-4">
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-32 w-full" />
          </div>
        ) : registry?.models && registry.models.length > 0 ? (
          <div className="space-y-4">
            {/* Select All Header */}
            <div className="flex items-center gap-2 px-4">
              <Checkbox
                id="select-all"
                checked={allSelected}
                onCheckedChange={toggleSelectAll}
              />
              <Label htmlFor="select-all" className="text-sm text-muted-foreground">
                Select all ({registry.models.length} models)
              </Label>
            </div>

            {registry.models.map((model) => {
              const isModelLoading = loadingModels.has(model.name)
              const isSelected = selectedModels.has(model.name)

              return (
                <Card key={model.name} className={isSelected ? "ring-2 ring-primary" : ""}>
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-3">
                        <Checkbox
                          checked={isSelected}
                          onCheckedChange={() => toggleModelSelection(model.name)}
                          className="mt-1"
                        />
                        <div className="space-y-1">
                          <CardTitle className="text-lg">{model.name}</CardTitle>
                          <p className="text-sm text-muted-foreground font-mono">
                            {model.base_model}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant={model.loaded ? "default" : "secondary"}>
                          {model.loaded ? "Loaded" : "Unloaded"}
                        </Badge>
                        <Badge variant="outline">{model.type}</Badge>
                        {model.registered_by && (
                          <Badge variant="outline" className="bg-blue-50 dark:bg-blue-950">
                            {model.registered_by}
                          </Badge>
                        )}
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center justify-between">
                      <div className="space-y-1">
                        {model.adapter_path && (
                          <p className="text-xs text-muted-foreground">
                            Adapter: {model.adapter_path}
                          </p>
                        )}
                        {model.config && (
                          <p className="text-xs text-muted-foreground">
                            Config: {JSON.stringify(model.config)}
                          </p>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <Link href={`/inference?model=${encodeURIComponent(model.name)}`}>
                          <Button variant="outline" size="sm">
                            <MessageSquare className="mr-2 h-4 w-4" />
                            Chat
                          </Button>
                        </Link>
                        {!model.loaded && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handlePreload(model.name)}
                            disabled={isModelLoading}
                          >
                            {isModelLoading ? (
                              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            ) : (
                              <Zap className="mr-2 h-4 w-4" />
                            )}
                            Pre-load
                          </Button>
                        )}
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => handleUnregister(model.name)}
                          disabled={isModelLoading}
                        >
                          {isModelLoading ? (
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          ) : (
                            <Trash2 className="mr-2 h-4 w-4" />
                          )}
                          Unregister
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )
            })}
          </div>
        ) : (
          <Card>
            <CardContent className="py-8 text-center">
              <Server className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
              <p className="text-muted-foreground">
                {showOnlyMlxHub
                  ? "No models from mlx-model-hub registered yet"
                  : "No models registered yet"
                }
              </p>
              <p className="text-sm text-muted-foreground mt-2">
                Train a model or click "Scan Exports" to discover existing models
              </p>
              {showOnlyMlxHub && (
                <Button
                  variant="link"
                  className="mt-2"
                  onClick={() => setShowOnlyMlxHub(false)}
                >
                  Show all models
                </Button>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardLayout>
  )
}
