/**
 * Centralized frontend configuration.
 *
 * All external URLs and environment-dependent settings should be defined here.
 */

// API Configuration
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Inference Server (unified-mlx-app) - separate from main API
export const INFERENCE_SERVER_URL =
  process.env.NEXT_PUBLIC_INFERENCE_URL || "http://localhost:8080";

// Knowledge Activation System (KAS) - knowledge retrieval and RAG
export const KAS_URL =
  process.env.NEXT_PUBLIC_KAS_URL || "http://localhost:8000";

// External Service URLs (configured via environment)
export const GRAFANA_URL =
  process.env.NEXT_PUBLIC_GRAFANA_URL || "http://localhost:3001";
export const PROMETHEUS_URL =
  process.env.NEXT_PUBLIC_PROMETHEUS_URL || "http://localhost:9090";
export const MLFLOW_URL =
  process.env.NEXT_PUBLIC_MLFLOW_URL || "http://localhost:5001";

// API Endpoints
export const API_ENDPOINTS = {
  // Health
  health: `${API_BASE_URL}/health`,
  healthDetailed: `${API_BASE_URL}/health/detailed`,
  metrics: `${API_BASE_URL}/metrics`,

  // Models
  models: `${API_BASE_URL}/api/models`,
  model: (id: string) => `${API_BASE_URL}/api/models/${id}`,

  // Discovery
  discoverSearch: `${API_BASE_URL}/api/discover/search`,
  discoverModel: (id: string) =>
    `${API_BASE_URL}/api/discover/models/${encodeURIComponent(id)}`,
  discoverPopular: `${API_BASE_URL}/api/discover/popular`,
  discoverRecent: `${API_BASE_URL}/api/discover/recent`,

  // Training
  trainingJobs: `${API_BASE_URL}/api/training/jobs`,
  trainingJob: (id: string) => `${API_BASE_URL}/api/training/jobs/${id}`,

  // Inference (legacy - mlx-model-hub backend)
  inference: `${API_BASE_URL}/api/inference`,
  inferenceStream: `${API_BASE_URL}/api/inference/stream`,

  // OpenAI-compatible (unified-mlx-app inference server)
  chatCompletions: `${INFERENCE_SERVER_URL}/v1/chat/completions`,
  completions: `${INFERENCE_SERVER_URL}/v1/completions`,
  v1Models: `${INFERENCE_SERVER_URL}/v1/models`,
} as const;

// Feature flags (can be extended for A/B testing, etc.)
export const FEATURES = {
  enableStreaming: true,
  enableMetrics: true,
  enableTraining: true,
} as const;

// Polling intervals (in milliseconds)
export const POLLING_INTERVALS = {
  health: 30000, // 30 seconds
  metrics: 15000, // 15 seconds
  trainingJobs: 5000, // 5 seconds for active jobs
  downloadStatus: 2000, // 2 seconds for active downloads
} as const;
