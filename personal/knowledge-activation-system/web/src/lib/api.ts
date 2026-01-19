/**
 * API client for Knowledge Activation System backend.
 * Handles all communication with the FastAPI backend.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Custom error class for API errors
export class APIError extends Error {
  constructor(
    message: string,
    public status?: number,
    public code?: string
  ) {
    super(message);
    this.name = "APIError";
  }
}

// Types matching backend schemas

export type ContentType = "youtube" | "bookmark" | "note" | "pdf" | "file";
export type ConfidenceLevel = "low" | "medium" | "high";
export type SearchMode = "hybrid" | "bm25" | "vector";

export interface SearchResult {
  content_id: string;
  title: string;
  content_type: ContentType;
  chunk_text: string;
  score: number;
  bm25_rank: number | null;
  vector_rank: number | null;
  source_ref: string | null;
}

export interface SearchResponse {
  query: string;
  mode: SearchMode;
  results: SearchResult[];
  total: number;
}

export interface Citation {
  index: number;
  title: string;
  content_type: ContentType;
  chunk_text: string | null;
}

export interface AskResponse {
  query: string;
  answer: string;
  confidence: ConfidenceLevel;
  confidence_score: number;
  citations: Citation[];
  warning: string | null;
  error: string | null;
}

export interface ContentItem {
  id: string;
  filepath: string;
  content_type: ContentType;
  title: string;
  summary: string | null;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface ContentListResponse {
  items: ContentItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface ContentDetail {
  id: string;
  filepath: string;
  content_type: ContentType;
  title: string;
  url: string | null;
  tags: string[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  chunks: Array<{
    id: string;
    chunk_index: number;
    chunk_text: string;
    source_ref: string | null;
  }>;
}

export interface ServiceHealth {
  name: string;
  status: "healthy" | "unhealthy";
  details: Record<string, unknown>;
}

export interface HealthResponse {
  status: "healthy" | "unhealthy";
  services: ServiceHealth[];
}

export interface StatsResponse {
  total_content: number;
  total_chunks: number;
  content_by_type: Record<string, number>;
  review_active: number;
  review_due: number;
}

// Review types

export type ReviewRating = "again" | "hard" | "good" | "easy";

export interface ReviewQueueItem {
  content_id: string;
  title: string;
  content_type: ContentType;
  preview_text: string;
  state: string;
  due: string;
  stability: number | null;
  difficulty: number | null;
  is_new: boolean;
  is_learning: boolean;
  is_review: boolean;
  last_review: string | null;
}

export interface ReviewDueResponse {
  items: ReviewQueueItem[];
  total: number;
}

export interface ReviewStatsResponse {
  total_active: number;
  due_now: number;
  new: number;
  learning: number;
  review: number;
}

export interface SubmitReviewResponse {
  content_id: string;
  rating: string;
  old_state: string;
  new_state: string;
  old_due: string;
  new_due: string;
  review_time: string;
}

export interface ReviewIntervalsResponse {
  again: string;
  hard: string;
  good: string;
  easy: string;
}

export interface ScheduleStatusResponse {
  enabled: boolean;
  scheduled_time: string;
  timezone: string;
  next_run: string | null;
  last_run: string | null;
  due_count: number;
  status: "running" | "waiting" | "disabled";
}

// Helper function for API requests with error handling
async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;

  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
    });

    if (!response.ok) {
      let message = `Request failed: ${response.statusText}`;
      try {
        const errorData = await response.json();
        message = errorData.detail || errorData.message || message;
      } catch {
        // Ignore JSON parse errors
      }

      if (response.status === 404) {
        throw new APIError("Resource not found", 404, "NOT_FOUND");
      }
      if (response.status === 422) {
        throw new APIError("Invalid request data", 422, "VALIDATION_ERROR");
      }
      if (response.status === 500) {
        throw new APIError("Server error occurred", 500, "SERVER_ERROR");
      }

      throw new APIError(message, response.status);
    }

    return response.json();
  } catch (error) {
    if (error instanceof APIError) {
      throw error;
    }

    // Network errors
    if (error instanceof TypeError && error.message.includes("fetch")) {
      throw new APIError(
        "Unable to connect to the API server. Please ensure the backend is running.",
        undefined,
        "NETWORK_ERROR"
      );
    }

    throw new APIError(
      error instanceof Error ? error.message : "An unexpected error occurred"
    );
  }
}

// API functions

export async function search(
  query: string,
  limit: number = 10,
  mode: SearchMode = "hybrid",
  namespace?: string
): Promise<SearchResponse> {
  return apiRequest<SearchResponse>("/search", {
    method: "POST",
    body: JSON.stringify({ query, limit, mode, namespace }),
  });
}

export async function ask(
  query: string,
  limit: number = 10,
  minConfidence: number = 0.0
): Promise<AskResponse> {
  return apiRequest<AskResponse>("/search/ask", {
    method: "POST",
    body: JSON.stringify({
      query,
      limit,
      min_confidence: minConfidence,
    }),
  });
}

export async function summarize(
  query: string,
  limit: number = 5
): Promise<AskResponse> {
  return apiRequest<AskResponse>("/search/summarize", {
    method: "POST",
    body: JSON.stringify({ query, limit }),
  });
}

export async function getContent(
  contentType?: ContentType,
  limit: number = 50,
  page: number = 1
): Promise<ContentListResponse> {
  const params = new URLSearchParams({
    page_size: limit.toString(),
    page: page.toString(),
  });
  if (contentType) {
    params.set("content_type", contentType);
  }

  return apiRequest<ContentListResponse>(`/content?${params}`);
}

export async function getContentById(id: string): Promise<ContentDetail> {
  return apiRequest<ContentDetail>(`/content/${id}`);
}

export async function deleteContent(id: string): Promise<void> {
  await apiRequest<{ message: string }>(`/content/${id}`, {
    method: "DELETE",
  });
}

export async function getHealth(): Promise<HealthResponse> {
  return apiRequest<HealthResponse>("/health");
}

export async function getStats(): Promise<StatsResponse> {
  return apiRequest<StatsResponse>("/stats");
}

// Review API functions

export async function getReviewDue(limit: number = 20): Promise<ReviewDueResponse> {
  return apiRequest<ReviewDueResponse>(`/review/due?limit=${limit}`);
}

export async function getReviewStats(): Promise<ReviewStatsResponse> {
  return apiRequest<ReviewStatsResponse>("/review/stats");
}

export async function submitReview(
  contentId: string,
  rating: ReviewRating
): Promise<SubmitReviewResponse> {
  return apiRequest<SubmitReviewResponse>(`/review/${contentId}`, {
    method: "POST",
    body: JSON.stringify({ rating }),
  });
}

export async function getReviewIntervals(contentId: string): Promise<ReviewIntervalsResponse> {
  return apiRequest<ReviewIntervalsResponse>(`/review/${contentId}/intervals`);
}

export async function suspendReview(contentId: string): Promise<void> {
  await apiRequest<{ message: string }>(`/review/${contentId}/suspend`, {
    method: "POST",
  });
}

export async function enableReview(contentId: string): Promise<void> {
  await apiRequest<{ message: string }>(`/review/${contentId}/enable`, {
    method: "POST",
  });
}

export async function getScheduleStatus(): Promise<ScheduleStatusResponse> {
  return apiRequest<ScheduleStatusResponse>("/review/schedule/status");
}

// Utility to check if API is reachable
export async function checkConnection(): Promise<boolean> {
  try {
    await getHealth();
    return true;
  } catch {
    return false;
  }
}

// Capture API functions

export interface CaptureRequest {
  content: string;
  title?: string;
  content_type?: ContentType;
  tags?: string[];
  metadata?: Record<string, unknown>;
}

export interface CaptureResponse {
  content_id: string;
  title: string;
  content_type: ContentType;
  chunks_created: number;
  message: string;
}

export interface CaptureUrlRequest {
  url: string;
  tags?: string[];
}

export async function captureContent(data: CaptureRequest): Promise<CaptureResponse> {
  return apiRequest<CaptureResponse>("/api/v1/capture", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function captureUrl(data: CaptureUrlRequest): Promise<CaptureResponse> {
  return apiRequest<CaptureResponse>("/api/v1/capture/url", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// Export/Import API functions

export interface ExportOptions {
  namespace?: string;
  content_type?: ContentType;
  format?: "json" | "markdown";
  include_chunks?: boolean;
}

export interface ExportResponse {
  filename: string;
  content_count: number;
  chunk_count: number;
  export_date: string;
}

export interface ImportResult {
  imported: number;
  skipped: number;
  errors: string[];
}

export async function exportContent(options: ExportOptions = {}): Promise<Blob> {
  const params = new URLSearchParams();
  if (options.namespace) params.set("namespace", options.namespace);
  if (options.content_type) params.set("content_type", options.content_type);
  if (options.format) params.set("format", options.format);
  if (options.include_chunks !== undefined) {
    params.set("include_chunks", String(options.include_chunks));
  }

  const url = `${API_BASE}/api/v1/export?${params}`;
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
  });

  if (!response.ok) {
    throw new APIError("Export failed", response.status);
  }

  return response.blob();
}

export async function importContent(file: File): Promise<ImportResult> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE}/api/v1/export/import`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new APIError("Import failed", response.status);
  }

  return response.json();
}

// Analytics API functions

export interface SearchAnalytics {
  total_queries: number;
  unique_queries: number;
  zero_result_rate: number;
  avg_results_per_query: number;
  avg_score: number;
  queries_by_day: Array<{ date: string; count: number }>;
}

export interface SearchGap {
  query: string;
  count: number;
  avg_score: number;
  last_searched: string;
}

export interface ContentQuality {
  high_quality: number;
  medium_quality: number;
  low_quality: number;
  needs_review: Array<{
    id: string;
    title: string;
    quality_score: number;
  }>;
}

export async function getSearchAnalytics(days: number = 30): Promise<SearchAnalytics> {
  return apiRequest<SearchAnalytics>(`/api/v1/analytics/search?days=${days}`);
}

export async function getSearchGaps(limit: number = 20): Promise<SearchGap[]> {
  return apiRequest<SearchGap[]>(`/api/v1/analytics/gaps?limit=${limit}`);
}

export async function getContentQuality(): Promise<ContentQuality> {
  return apiRequest<ContentQuality>("/api/v1/analytics/quality");
}

// Namespace API functions

export interface NamespaceInfo {
  name: string;
  document_count: number;
  chunk_count: number;
  latest_update: string | null;
}

export interface NamespaceListResponse {
  namespaces: NamespaceInfo[];
  total: number;
}

export async function getNamespaces(): Promise<NamespaceListResponse> {
  return apiRequest<NamespaceListResponse>("/api/v1/namespaces");
}

// Webhook API functions

export interface Webhook {
  id: string;
  url: string;
  events: string[];
  secret: string | null;
  active: boolean;
  created_at: string;
  last_triggered: string | null;
  failure_count: number;
}

export interface WebhookCreateRequest {
  url: string;
  events: string[];
  secret?: string;
}

export interface WebhookDelivery {
  id: string;
  webhook_id: string;
  event: string;
  status: "success" | "failure";
  status_code: number | null;
  response_time_ms: number | null;
  error_message: string | null;
  created_at: string;
}

export async function getWebhooks(): Promise<Webhook[]> {
  return apiRequest<Webhook[]>("/api/v1/webhooks");
}

export async function createWebhook(data: WebhookCreateRequest): Promise<Webhook> {
  return apiRequest<Webhook>("/api/v1/webhooks", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function deleteWebhook(id: string): Promise<void> {
  await apiRequest<{ message: string }>(`/api/v1/webhooks/${id}`, {
    method: "DELETE",
  });
}

export async function testWebhook(id: string): Promise<{ success: boolean; message: string }> {
  return apiRequest<{ success: boolean; message: string }>(`/api/v1/webhooks/${id}/test`, {
    method: "POST",
  });
}

export async function getWebhookDeliveries(id: string, limit: number = 10): Promise<WebhookDelivery[]> {
  return apiRequest<WebhookDelivery[]>(`/api/v1/webhooks/${id}/deliveries?limit=${limit}`);
}

// Entity/Knowledge Graph API functions

export interface Entity {
  id: string;
  name: string;
  entity_type: string;
  confidence: number;
}

export interface EntityStats {
  entity_type: string;
  count: number;
  unique_names: number;
}

export interface ConnectedEntity {
  name: string;
  entity_type: string;
  connection_count: number;
}

export interface ContentByEntity {
  content_id: string;
  title: string;
  content_type: string;
  entity_count: number;
  entities: Entity[];
}

export interface RelatedContent {
  content_id: string;
  title: string;
  content_type: string;
  shared_entities: string[];
  relevance_score: number;
}

export async function getEntityStats(): Promise<EntityStats[]> {
  return apiRequest<EntityStats[]>("/entities/stats");
}

export async function getConnectedEntities(limit: number = 20): Promise<ConnectedEntity[]> {
  return apiRequest<ConnectedEntity[]>(`/entities/connected?limit=${limit}`);
}

export async function getEntitiesByContent(contentId: string): Promise<Entity[]> {
  return apiRequest<Entity[]>(`/entities/content/${contentId}`);
}

export async function searchContentByEntity(name: string, limit: number = 10): Promise<ContentByEntity[]> {
  return apiRequest<ContentByEntity[]>(`/entities/search?name=${encodeURIComponent(name)}&limit=${limit}`);
}

export async function getRelatedContentByEntity(entityId: string, limit: number = 10): Promise<RelatedContent[]> {
  return apiRequest<RelatedContent[]>(`/entities/${entityId}/related-content?limit=${limit}`);
}
