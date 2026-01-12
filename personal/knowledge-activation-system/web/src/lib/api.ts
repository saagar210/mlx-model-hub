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
  mode: SearchMode = "hybrid"
): Promise<SearchResponse> {
  return apiRequest<SearchResponse>("/search", {
    method: "POST",
    body: JSON.stringify({ query, limit, mode }),
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
