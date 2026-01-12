// API client for MLX Model Hub backend

import { API_BASE_URL } from "./config"

export class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    message: string
  ) {
    super(message)
    this.name = "ApiError"
  }
}

async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  })

  if (!response.ok) {
    const errorText = await response.text()
    throw new ApiError(response.status, response.statusText, errorText)
  }

  return response.json()
}

// Types
export interface Model {
  id: string
  name: string
  task_type: string
  description?: string
  base_model: string
  tags: Record<string, string>
  mlflow_experiment_id?: string
  version_count: number
  created_at: string
  updated_at: string
}

export interface ModelListResponse {
  items: Model[]
  total: number
  page: number
  page_size: number
}

export interface TrainingJob {
  id: string
  model_id: string
  status: "pending" | "running" | "completed" | "failed" | "cancelled"
  config: TrainingConfig
  metrics?: TrainingMetrics
  started_at?: string
  completed_at?: string
  error?: string
  created_at: string
  updated_at: string
}

export interface TrainingConfig {
  base_model: string
  dataset_path: string
  output_dir: string
  num_epochs: number
  batch_size: number
  learning_rate: number
  lora_rank?: number
  lora_alpha?: number
  use_lora: boolean
}

export interface TrainingMetrics {
  epoch: number
  step: number
  loss: number
  learning_rate: number
  tokens_per_second?: number
}

export interface TrainingJobListResponse {
  items: TrainingJob[]
  total: number
  page: number
  page_size: number
}

export interface InferenceRequest {
  model_id: string
  prompt: string
  max_tokens?: number
  temperature?: number
  top_p?: number
  stream?: boolean
}

export interface InferenceResponse {
  id: string
  model_id: string
  prompt: string
  response: string
  tokens_generated: number
  time_to_first_token_ms: number
  total_time_ms: number
  tokens_per_second: number
  created_at: string
}

export interface HealthResponse {
  status: string
  version: string
  timestamp: string
}

export interface MetricsResponse {
  models_loaded: number
  active_inferences: number
  training_jobs_running: number
  cache_size_bytes: number
  uptime_seconds: number
}

// API Functions

// Models
export async function getModels(
  page = 1,
  pageSize = 20,
  status?: string
): Promise<ModelListResponse> {
  const params = new URLSearchParams({
    page: page.toString(),
    page_size: pageSize.toString(),
  })
  if (status) params.append("status", status)
  return fetchApi<ModelListResponse>(`/api/models?${params}`)
}

export async function getModel(id: string): Promise<Model> {
  return fetchApi<Model>(`/api/models/${id}`)
}

export async function deleteModel(id: string): Promise<void> {
  return fetchApi<void>(`/api/models/${id}`, {
    method: "DELETE",
  })
}

// Training
export async function getTrainingJobs(
  page = 1,
  pageSize = 20,
  status?: string
): Promise<TrainingJobListResponse> {
  const params = new URLSearchParams({
    page: page.toString(),
    page_size: pageSize.toString(),
  })
  if (status) params.append("status", status)
  return fetchApi<TrainingJobListResponse>(`/api/training/jobs?${params}`)
}

export async function getTrainingJob(id: string): Promise<TrainingJob> {
  return fetchApi<TrainingJob>(`/api/training/jobs/${id}`)
}

export async function createTrainingJob(
  config: TrainingConfig
): Promise<TrainingJob> {
  return fetchApi<TrainingJob>("/api/training/jobs", {
    method: "POST",
    body: JSON.stringify(config),
  })
}

export async function cancelTrainingJob(id: string): Promise<TrainingJob> {
  return fetchApi<TrainingJob>(`/api/training/jobs/${id}/cancel`, {
    method: "POST",
  })
}

// Inference
export async function runInference(
  request: InferenceRequest
): Promise<InferenceResponse> {
  return fetchApi<InferenceResponse>("/api/inference", {
    method: "POST",
    body: JSON.stringify(request),
  })
}

export async function* streamInference(
  request: InferenceRequest
): AsyncGenerator<string, void, unknown> {
  const url = `${API_BASE_URL}/api/inference/stream`
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ ...request, stream: true }),
  })

  if (!response.ok) {
    const errorText = await response.text()
    throw new ApiError(response.status, response.statusText, errorText)
  }

  const reader = response.body?.getReader()
  if (!reader) throw new Error("No response body")

  const decoder = new TextDecoder()
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    yield decoder.decode(value, { stream: true })
  }
}

// Health & Metrics
export async function getHealth(): Promise<HealthResponse> {
  return fetchApi<HealthResponse>("/health")
}

export async function getMetrics(): Promise<MetricsResponse> {
  return fetchApi<MetricsResponse>("/health/detailed")
}

// Model Discovery Types
export interface DiscoveredModel {
  model_id: string
  author: string
  model_name: string
  downloads: number
  likes: number
  tags: string[]
  pipeline_tag: string | null
  library_name: string | null
  created_at: string | null
  last_modified: string | null
  total_size_bytes: number
  size_gb: number
  estimated_memory_gb: number
  quantization: string | null
  is_mlx: boolean
  is_quantized: boolean
  files: { filename: string; size_bytes: number; lfs: boolean }[]
}

export interface DiscoverSearchResponse {
  models: DiscoveredModel[]
  total_count: number
  page: number
  page_size: number
}

export interface MemoryCompatibility {
  status: "compatible" | "tight" | "incompatible"
  message: string
  warning: string | null
  required_memory_gb: number
  available_memory_gb: number
  total_memory_gb: number
}

export interface DownloadStatus {
  model_id: string
  status: "pending" | "downloading" | "completed" | "failed" | "cancelled"
  progress_percent: number
  downloaded_bytes: number
  total_bytes: number
  error: string | null
  output_path: string | null
}

// Model Discovery Functions
export async function searchDiscoverModels(
  query: string,
  page = 1,
  pageSize = 20,
  mlxOnly = true,
  sort = "downloads",
  direction = "desc"
): Promise<DiscoverSearchResponse> {
  const params = new URLSearchParams({
    query,
    page: page.toString(),
    page_size: pageSize.toString(),
    mlx_only: mlxOnly.toString(),
    sort,
    direction,
  })
  return fetchApi<DiscoverSearchResponse>(`/api/discover/search?${params}`)
}

export async function getDiscoveredModel(modelId: string): Promise<DiscoveredModel> {
  return fetchApi<DiscoveredModel>(`/api/discover/models/${encodeURIComponent(modelId)}`)
}

export async function checkModelCompatibility(modelId: string): Promise<MemoryCompatibility> {
  return fetchApi<MemoryCompatibility>(
    `/api/discover/models/${encodeURIComponent(modelId)}/compatibility`
  )
}

export async function startModelDownload(modelId: string): Promise<DownloadStatus> {
  return fetchApi<DownloadStatus>(
    `/api/discover/models/${encodeURIComponent(modelId)}/download`,
    { method: "POST" }
  )
}

export async function getDownloadStatus(modelId: string): Promise<DownloadStatus> {
  return fetchApi<DownloadStatus>(
    `/api/discover/download/${encodeURIComponent(modelId)}/status`
  )
}

export async function cancelDownload(modelId: string): Promise<void> {
  return fetchApi<void>(`/api/discover/download/${encodeURIComponent(modelId)}`, {
    method: "DELETE",
  })
}

export async function getPopularModels(limit = 10): Promise<DiscoverSearchResponse> {
  const params = new URLSearchParams({ limit: limit.toString() })
  return fetchApi<DiscoverSearchResponse>(`/api/discover/popular?${params}`)
}

export async function getRecentModels(limit = 10): Promise<DiscoverSearchResponse> {
  const params = new URLSearchParams({ limit: limit.toString() })
  return fetchApi<DiscoverSearchResponse>(`/api/discover/recent?${params}`)
}
