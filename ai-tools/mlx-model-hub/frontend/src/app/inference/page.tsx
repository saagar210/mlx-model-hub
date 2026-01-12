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
import { useModels } from "@/lib/hooks"
import { streamInference, InferenceRequest } from "@/lib/api"
import { Send, Settings, Trash2, Copy, CheckCircle, StopCircle, Zap } from "lucide-react"
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

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const { data: models, isLoading: modelsLoading } = useModels()

  const availableModels = models?.items ?? []

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const handleStreamingInference = useCallback(async () => {
    if (!prompt.trim() || !selectedModel) return

    const userMessage: Message = { role: "user", content: prompt }
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

    const request: InferenceRequest = {
      model_id: selectedModel,
      prompt: prompt,
      max_tokens: settings.max_tokens,
      temperature: settings.temperature,
      top_p: settings.top_p,
      stream: true,
    }

    let accumulatedContent = ""
    let tokenCount = 0
    let ttft: number | undefined
    let tps: number | undefined

    try {
      for await (const chunk of streamInference(request)) {
        if (chunk.type === "token") {
          accumulatedContent += chunk.token || ""
          tokenCount++
          if (chunk.ttft !== undefined && ttft === undefined) {
            ttft = chunk.ttft * 1000 // Convert to ms
          }
          setCurrentStats({ tokens: tokenCount, ttft, tps })

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
          tps = chunk.tokens_per_second
          const totalTime = chunk.total_time ? chunk.total_time * 1000 : 0

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
                  tokens: chunk.total_tokens || tokenCount,
                  ttft_ms: ttft || 0,
                  total_ms: totalTime,
                  tps: tps || 0,
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
  }, [prompt, selectedModel, settings])

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
                <Label htmlFor="model">Model</Label>
                {modelsLoading ? (
                  <Skeleton className="mt-1 h-10 w-full" />
                ) : (
                  <Select
                    value={selectedModel}
                    onValueChange={setSelectedModel}
                  >
                    <SelectTrigger className="mt-1">
                      <SelectValue placeholder="Select a model" />
                    </SelectTrigger>
                    <SelectContent>
                      {availableModels.map((model) => (
                        <SelectItem key={model.id} value={model.id}>
                          {model.name}
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
