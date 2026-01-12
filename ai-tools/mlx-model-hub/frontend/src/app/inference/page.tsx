"use client"

import { Suspense, useState, useRef, useEffect, useCallback } from "react"
import { useSearchParams } from "next/navigation"
import { DashboardLayout } from "@/components/layout"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Switch } from "@/components/ui/switch"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useModels, useAdminHealth, useKASHealth, useKASSearchMutation } from "@/lib/hooks"
import {
  streamChatCompletion,
  getInferenceModels,
  ChatCompletionRequest,
  formatKASContextForRAG,
  KASSearchResult,
} from "@/lib/api"
import { Send, Settings, Trash2, Copy, CheckCircle, StopCircle, Zap, AlertCircle, RefreshCw, Loader2, BookOpen, Search, X, Plus, Database } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { toast } from "sonner"

interface Message {
  role: "user" | "assistant"
  content: string
  isStreaming?: boolean
  stats?: {
    tokens: number
    ttft_ms: number
    total_ms: number
    tps: number
  }
}

function InferencePlayground() {
  const searchParams = useSearchParams()
  const initialModel = searchParams.get("model") || ""

  const [selectedModel, setSelectedModel] = useState(initialModel)
  const [prompt, setPrompt] = useState("")
  const [messages, setMessages] = useState<Message[]>([])
  const [showSettings, setShowSettings] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamEnabled, setStreamEnabled] = useState(true)
  const abortControllerRef = useRef<AbortController | null>(null)
  const [settings, setSettings] = useState({
    max_tokens: 512,
    temperature: 0.7,
    top_p: 0.9,
  })
  const [copied, setCopied] = useState<number | null>(null)
  const [currentStats, setCurrentStats] = useState<{
    tokens: number
    ttft?: number
    tps?: number
  } | null>(null)

  // KAS (Knowledge Activation System) state
  const [showKAS, setShowKAS] = useState(false)
  const [kasQuery, setKasQuery] = useState("")
  const [selectedContext, setSelectedContext] = useState<KASSearchResult[]>([])
  const [ragEnabled, setRagEnabled] = useState(false)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const [availableModels, setAvailableModels] = useState<string[]>([])
  const [modelsLoading, setModelsLoading] = useState(true)
  const [modelsError, setModelsError] = useState<string | null>(null)

  // Check inference server health
  const { data: serverHealth, isLoading: healthLoading, refetch: refetchHealth } = useAdminHealth()
  const isServerOnline = serverHealth?.status === "ok"

  // KAS (Knowledge Activation System) hooks
  const { data: kasHealth } = useKASHealth()
  const kasSearch = useKASSearchMutation()
  const isKASOnline = kasHealth?.status === "healthy"

  // Fetch available models from inference server
  const fetchModels = useCallback(async () => {
    setModelsLoading(true)
    setModelsError(null)
    try {
      const models = await getInferenceModels()
      setAvailableModels(models)
      // Auto-select first model if none selected or initial model not in list
      if (models.length > 0) {
        if (!selectedModel || !models.includes(selectedModel)) {
          // If initial model from URL exists, keep it; otherwise select first
          if (initialModel && models.includes(initialModel)) {
            setSelectedModel(initialModel)
          } else if (!selectedModel) {
            setSelectedModel(models[0])
          }
        }
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error"
      setModelsError(message)
      if (message.includes("fetch") || message.includes("network")) {
        toast.error("Cannot connect to inference server")
      } else {
        toast.error(`Failed to load models: ${message}`)
      }
    } finally {
      setModelsLoading(false)
    }
  }, [initialModel, selectedModel])

  // Fetch models on mount and when server comes online
  useEffect(() => {
    fetchModels()
  }, [])

  // Retry fetching when server health changes to online
  useEffect(() => {
    if (isServerOnline && modelsError) {
      fetchModels()
    }
  }, [isServerOnline, modelsError, fetchModels])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const handleStreamingInference = useCallback(async () => {
    if (!prompt.trim() || !selectedModel) return

    const userMessage: Message = { role: "user", content: prompt }
    const currentPrompt = prompt
    setMessages((prev) => [...prev, userMessage])
    setPrompt("")
    setIsStreaming(true)
    setCurrentStats({ tokens: 0 })

    // Add empty assistant message for streaming
    const assistantMessage: Message = {
      role: "assistant",
      content: "",
      isStreaming: true,
    }
    setMessages((prev) => [...prev, assistantMessage])

    // Build the prompt with optional RAG context
    let augmentedPrompt = currentPrompt
    if (ragEnabled && selectedContext.length > 0) {
      const contextPrefix = formatKASContextForRAG(selectedContext)
      augmentedPrompt = contextPrefix + "Based on the context above, please answer: " + currentPrompt
    }

    // Convert to OpenAI chat format with conversation history
    const chatMessages = [
      ...messages.map((m) => ({ role: m.role, content: m.content })),
      { role: "user" as const, content: augmentedPrompt },
    ]

    const request: ChatCompletionRequest = {
      model: selectedModel,
      messages: chatMessages,
      max_tokens: settings.max_tokens,
      temperature: settings.temperature,
      top_p: settings.top_p,
      stream: true,
    }

    let accumulatedContent = ""
    let tokenCount = 0
    const startTime = Date.now()
    let ttft: number | undefined

    try {
      for await (const chunk of streamChatCompletion(request)) {
        if (chunk.type === "content") {
          accumulatedContent += chunk.content || ""
          tokenCount++
          if (ttft === undefined && tokenCount === 1) {
            ttft = Date.now() - startTime
          }
          setCurrentStats({ tokens: tokenCount, ttft })

          // Update the streaming message
          setMessages((prev) => {
            const updated = [...prev]
            const lastIdx = updated.length - 1
            if (lastIdx >= 0 && updated[lastIdx].role === "assistant") {
              updated[lastIdx] = {
                ...updated[lastIdx],
                content: accumulatedContent,
              }
            }
            return updated
          })
        } else if (chunk.type === "done") {
          const totalTime = Date.now() - startTime
          const tps = totalTime > 0 ? (tokenCount / totalTime) * 1000 : 0

          // Finalize the message with stats
          setMessages((prev) => {
            const updated = [...prev]
            const lastIdx = updated.length - 1
            if (lastIdx >= 0 && updated[lastIdx].role === "assistant") {
              updated[lastIdx] = {
                ...updated[lastIdx],
                content: accumulatedContent,
                isStreaming: false,
                stats: {
                  tokens: tokenCount,
                  ttft_ms: ttft || 0,
                  total_ms: totalTime,
                  tps: tps,
                },
              }
            }
            return updated
          })
        } else if (chunk.type === "error") {
          throw new Error(chunk.error || "Stream error")
        }
      }
    } catch (error) {
      toast.error(`Inference failed: ${error instanceof Error ? error.message : "Unknown error"}`)
      // Remove the streaming message on error
      setMessages((prev) => prev.filter((m) => !m.isStreaming))
    } finally {
      setIsStreaming(false)
      setCurrentStats(null)
    }
  }, [prompt, selectedModel, settings, messages, ragEnabled, selectedContext])

  const handleStopStreaming = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    setIsStreaming(false)
  }

  const handleSend = () => {
    if (streamEnabled) {
      handleStreamingInference()
    } else {
      // Non-streaming fallback (kept for compatibility)
      handleStreamingInference()
    }
  }

  const handleCopy = (index: number, content: string) => {
    navigator.clipboard.writeText(content)
    setCopied(index)
    setTimeout(() => setCopied(null), 2000)
  }

  const handleClear = () => {
    setMessages([])
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  // KAS handlers
  const handleKASSearch = () => {
    if (!kasQuery.trim()) return
    kasSearch.mutate(
      { query: kasQuery, limit: 10 },
      {
        onError: (err) => toast.error(`KAS search failed: ${err.message}`),
      }
    )
  }

  const handleAddContext = (result: KASSearchResult) => {
    if (selectedContext.some((c) => c.content_id === result.content_id)) {
      toast.info("Already added to context")
      return
    }
    setSelectedContext((prev) => [...prev, result])
    setRagEnabled(true)
    toast.success(`Added "${result.title}" to context`)
  }

  const handleRemoveContext = (contentId: string) => {
    setSelectedContext((prev) => prev.filter((c) => c.content_id !== contentId))
  }

  const handleClearContext = () => {
    setSelectedContext([])
    setRagEnabled(false)
  }

  return (
    <div className="flex h-[calc(100vh-10rem)] flex-col space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Inference</h2>
          <p className="text-muted-foreground">
            Test models in the interactive playground
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Database className={`h-4 w-4 ${ragEnabled ? "text-blue-500" : "text-muted-foreground"}`} />
            <Label htmlFor="rag-toggle" className="text-sm">
              RAG
            </Label>
            <Switch
              id="rag-toggle"
              checked={ragEnabled}
              onCheckedChange={setRagEnabled}
              disabled={selectedContext.length === 0}
            />
            {selectedContext.length > 0 && (
              <Badge variant="secondary" className="text-xs">
                {selectedContext.length} sources
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Zap className={`h-4 w-4 ${streamEnabled ? "text-yellow-500" : "text-muted-foreground"}`} />
            <Label htmlFor="stream-toggle" className="text-sm">
              Streaming
            </Label>
            <Switch
              id="stream-toggle"
              checked={streamEnabled}
              onCheckedChange={setStreamEnabled}
            />
          </div>
          <Button
            variant={showKAS ? "default" : "outline"}
            size="icon"
            onClick={() => setShowKAS(!showKAS)}
            title="Knowledge Base"
          >
            <BookOpen className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            onClick={() => setShowSettings(!showSettings)}
          >
            <Settings className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            onClick={handleClear}
            disabled={messages.length === 0}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="flex flex-1 gap-4 overflow-hidden">
        <Card className="flex flex-1 flex-col">
          <CardHeader className="border-b pb-4">
            <div className="flex items-center gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <Label htmlFor="model">Model</Label>
                  {healthLoading ? (
                    <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
                  ) : isServerOnline ? (
                    <span className="flex items-center gap-1 text-xs text-green-600">
                      <CheckCircle className="h-3 w-3" />
                      Server Online
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-xs text-red-600">
                      <AlertCircle className="h-3 w-3" />
                      Server Offline
                    </span>
                  )}
                </div>
                {modelsLoading ? (
                  <Skeleton className="mt-1 h-10 w-full" />
                ) : modelsError ? (
                  <div className="mt-1 p-3 rounded-md border border-destructive/50 bg-destructive/10">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-sm text-destructive">
                        <AlertCircle className="h-4 w-4" />
                        <span>Cannot connect to inference server</span>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={fetchModels}
                      >
                        <RefreshCw className="mr-2 h-3 w-3" />
                        Retry
                      </Button>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      Make sure unified-mlx-app is running on port 8080
                    </p>
                  </div>
                ) : (
                  <Select
                    value={selectedModel}
                    onValueChange={setSelectedModel}
                  >
                    <SelectTrigger className="mt-1">
                      <SelectValue placeholder="Select a model" />
                    </SelectTrigger>
                    <SelectContent>
                      {availableModels.map((modelName) => (
                        <SelectItem key={modelName} value={modelName}>
                          {modelName}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </div>
              {isStreaming && currentStats && (
                <div className="flex items-center gap-4 text-sm text-muted-foreground">
                  <span>{currentStats.tokens} tokens</span>
                  {currentStats.ttft && (
                    <span>{currentStats.ttft.toFixed(0)}ms TTFT</span>
                  )}
                  {currentStats.tps && (
                    <span>{currentStats.tps.toFixed(1)} tok/s</span>
                  )}
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent className="flex flex-1 flex-col overflow-hidden p-0">
            <ScrollArea className="flex-1 p-4">
              {messages.length === 0 ? (
                <div className="flex h-full items-center justify-center text-muted-foreground">
                  <p>Start a conversation by sending a message below.</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {messages.map((message, index) => (
                    <div
                      key={index}
                      className={`flex ${
                        message.role === "user"
                          ? "justify-end"
                          : "justify-start"
                      }`}
                    >
                      <div
                        className={`group relative max-w-[80%] rounded-lg px-4 py-2 ${
                          message.role === "user"
                            ? "bg-primary text-primary-foreground"
                            : "bg-muted"
                        }`}
                      >
                        <p className="whitespace-pre-wrap">
                          {message.content}
                          {message.isStreaming && (
                            <span className="ml-1 inline-block h-4 w-2 animate-pulse bg-primary" />
                          )}
                        </p>
                        {message.stats && (
                          <div className="mt-2 border-t border-border/50 pt-2 text-xs text-muted-foreground">
                            {message.stats.tokens} tokens |{" "}
                            {message.stats.ttft_ms.toFixed(0)}ms TTFT |{" "}
                            {message.stats.tps.toFixed(1)} tok/s
                          </div>
                        )}
                        {!message.isStreaming && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="absolute -right-2 -top-2 h-6 w-6 opacity-0 transition-opacity group-hover:opacity-100"
                            onClick={() => handleCopy(index, message.content)}
                          >
                            {copied === index ? (
                              <CheckCircle className="h-3 w-3 text-green-500" />
                            ) : (
                              <Copy className="h-3 w-3" />
                            )}
                          </Button>
                        )}
                      </div>
                    </div>
                  ))}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </ScrollArea>
            <div className="border-t p-4">
              <div className="flex gap-2">
                <Textarea
                  placeholder="Type your message..."
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  onKeyDown={handleKeyDown}
                  className="min-h-[80px] resize-none"
                  disabled={!selectedModel || isStreaming}
                />
                {isStreaming ? (
                  <Button
                    className="h-auto"
                    variant="destructive"
                    onClick={handleStopStreaming}
                  >
                    <StopCircle className="h-4 w-4" />
                  </Button>
                ) : (
                  <Button
                    className="h-auto"
                    onClick={handleSend}
                    disabled={!prompt.trim() || !selectedModel}
                  >
                    <Send className="h-4 w-4" />
                  </Button>
                )}
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                Press Enter to send, Shift+Enter for new line
                {streamEnabled && " | Streaming enabled"}
              </p>
            </div>
          </CardContent>
        </Card>

        {showSettings && (
          <Card className="w-72 shrink-0">
            <CardHeader>
              <CardTitle className="text-sm">Settings</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="max_tokens">Max Tokens</Label>
                <Input
                  id="max_tokens"
                  type="number"
                  value={settings.max_tokens}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      max_tokens: parseInt(e.target.value),
                    })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="temperature">
                  Temperature: {settings.temperature}
                </Label>
                <Input
                  id="temperature"
                  type="range"
                  min="0"
                  max="2"
                  step="0.1"
                  value={settings.temperature}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      temperature: parseFloat(e.target.value),
                    })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="top_p">Top P: {settings.top_p}</Label>
                <Input
                  id="top_p"
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={settings.top_p}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      top_p: parseFloat(e.target.value),
                    })
                  }
                />
              </div>
            </CardContent>
          </Card>
        )}

        {showKAS && (
          <Card className="w-80 shrink-0 flex flex-col">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm flex items-center gap-2">
                  <BookOpen className="h-4 w-4" />
                  Knowledge Base
                </CardTitle>
                {isKASOnline ? (
                  <Badge variant="outline" className="text-xs text-green-600">
                    <CheckCircle className="h-3 w-3 mr-1" />
                    Online
                  </Badge>
                ) : (
                  <Badge variant="outline" className="text-xs text-red-600">
                    <AlertCircle className="h-3 w-3 mr-1" />
                    Offline
                  </Badge>
                )}
              </div>
              {kasHealth?.stats && (
                <p className="text-xs text-muted-foreground mt-1">
                  {kasHealth.stats.total_content} items | {kasHealth.stats.total_chunks} chunks
                </p>
              )}
            </CardHeader>
            <CardContent className="flex-1 flex flex-col space-y-3 overflow-hidden">
              {/* Search Input */}
              <div className="flex gap-2">
                <Input
                  placeholder="Search knowledge..."
                  value={kasQuery}
                  onChange={(e) => setKasQuery(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleKASSearch()}
                  disabled={!isKASOnline}
                />
                <Button
                  size="icon"
                  onClick={handleKASSearch}
                  disabled={!kasQuery.trim() || !isKASOnline || kasSearch.isPending}
                >
                  {kasSearch.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Search className="h-4 w-4" />
                  )}
                </Button>
              </div>

              {/* Selected Context */}
              {selectedContext.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="text-xs font-medium">Selected Context</Label>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 text-xs"
                      onClick={handleClearContext}
                    >
                      Clear all
                    </Button>
                  </div>
                  <div className="space-y-1 max-h-32 overflow-y-auto">
                    {selectedContext.map((ctx) => (
                      <div
                        key={ctx.content_id}
                        className="flex items-center justify-between p-2 bg-blue-50 dark:bg-blue-950 rounded text-xs"
                      >
                        <span className="truncate flex-1 mr-2">{ctx.title}</span>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-5 w-5"
                          onClick={() => handleRemoveContext(ctx.content_id)}
                        >
                          <X className="h-3 w-3" />
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Search Results */}
              <ScrollArea className="flex-1">
                {kasSearch.data?.results && kasSearch.data.results.length > 0 ? (
                  <div className="space-y-2">
                    <Label className="text-xs font-medium">
                      Search Results ({kasSearch.data.total})
                    </Label>
                    {kasSearch.data.results.map((result) => (
                      <div
                        key={result.content_id}
                        className="p-2 border rounded hover:bg-muted/50 cursor-pointer"
                        onClick={() => handleAddContext(result)}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium truncate">{result.title}</p>
                            <div className="flex items-center gap-2 mt-1">
                              <Badge variant="outline" className="text-xs">
                                {result.content_type}
                              </Badge>
                              <span className="text-xs text-muted-foreground">
                                {(result.score * 100).toFixed(0)}% match
                              </span>
                            </div>
                            {result.chunk_text && (
                              <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                                {result.chunk_text}
                              </p>
                            )}
                          </div>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6 shrink-0"
                            onClick={(e) => {
                              e.stopPropagation()
                              handleAddContext(result)
                            }}
                          >
                            <Plus className="h-3 w-3" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : kasSearch.data?.results?.length === 0 ? (
                  <p className="text-xs text-muted-foreground text-center py-4">
                    No results found
                  </p>
                ) : !isKASOnline ? (
                  <div className="text-center py-4">
                    <AlertCircle className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
                    <p className="text-xs text-muted-foreground">
                      KAS server is offline
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Make sure it&apos;s running on port 8000
                    </p>
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground text-center py-4">
                    Search your knowledge base to add context for RAG
                  </p>
                )}
              </ScrollArea>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}

export default function InferencePage() {
  return (
    <DashboardLayout>
      <Suspense
        fallback={
          <div className="space-y-4">
            <Skeleton className="h-10 w-1/3" />
            <Skeleton className="h-[600px] w-full" />
          </div>
        }
      >
        <InferencePlayground />
      </Suspense>
    </DashboardLayout>
  )
}
