/**
 * API Types for Knowledge Engine
 *
 * These types mirror the Pydantic models from the backend.
 * Keep in sync with: src/knowledge_engine/models/
 */

// ============================================================
// Common Types
// ============================================================

export interface ChunkMetadata {
  document_id: string;
  chunk_index: number;
  start_char: number;
  end_char: number;
  section?: string;
  page?: number;
  timestamp_start?: number;
  timestamp_end?: number;
}

// ============================================================
// Search Types
// ============================================================

export type SearchType = "vector" | "keyword" | "hybrid" | "memory";

export interface SearchRequest {
  query: string;
  namespace?: string;
  search_type?: SearchType;
  limit?: number;
  filters?: Record<string, unknown>;
  include_content?: boolean;
  rerank?: boolean;
}

export interface SearchResult {
  id: string;
  content: string;
  score: number;
  document_id: string;
  document_title?: string;
  metadata: ChunkMetadata & Record<string, unknown>;
  source_url?: string;
  highlights?: string[];
}

export interface SearchResponse {
  query: string;
  namespace: string;
  search_type: SearchType;
  results: SearchResult[];
  total_found: number;
  search_time_ms: number;
  reranked: boolean;
}

// ============================================================
// Query (RAG) Types
// ============================================================

export interface QueryRequest {
  query: string;
  namespace?: string;
  max_context_chunks?: number;
  include_sources?: boolean;
  temperature?: number;
  stream?: boolean;
}

export interface QuerySource {
  document_id: string;
  document_title: string;
  chunk_id: string;
  relevance_score: number;
  content_preview: string;
  source_url?: string;
}

export interface QueryResponse {
  query: string;
  answer: string;
  confidence: number;
  sources: QuerySource[];
  query_time_ms: number;
  tokens_used?: {
    input: number;
    output: number;
  };
}

// ============================================================
// Document Types
// ============================================================

export type DocumentSourceType = "url" | "youtube" | "file" | "text" | "api";

export interface Document {
  id: string;
  title: string;
  source_type: DocumentSourceType;
  source_url?: string;
  content_hash: string;
  namespace: string;
  chunk_count: number;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

// ============================================================
// Ingestion Types
// ============================================================

export interface IngestRequest {
  url?: string;
  video_id?: string;
  content?: string;
  title?: string;
  namespace?: string;
  metadata?: Record<string, unknown>;
}

export interface IngestResponse {
  document_id: string;
  title: string;
  source_type: DocumentSourceType;
  chunk_count: number;
  content_length: number;
  ingestion_time_ms: number;
  status: "success" | "partial" | "error";
  message?: string;
}

// ============================================================
// Memory Types
// ============================================================

export type MemoryType =
  | "fact"
  | "preference"
  | "context"
  | "procedure"
  | "entity"
  | "relation";

export interface MemoryStoreRequest {
  content: string;
  memory_type?: MemoryType;
  namespace?: string;
  context?: string;
  source?: string;
  importance?: number;
  tags?: string[];
  metadata?: Record<string, unknown>;
  expires_at?: string;
}

export interface Memory {
  id: string;
  content: string;
  memory_type: MemoryType;
  namespace: string;
  context?: string;
  source?: string;
  importance: number;
  tags: string[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  accessed_at?: string;
  access_count: number;
  expires_at?: string;
  is_deleted: boolean;
  related_memories: string[];
  related_entities: string[];
}

export interface MemoryRecallRequest {
  query: string;
  namespace?: string;
  limit?: number;
  memory_types?: MemoryType[];
  min_importance?: number;
  include_related?: boolean;
  session_id?: string;
}

export interface MemoryRecallResponse {
  query: string;
  namespace: string;
  memories: Memory[];
  total_found: number;
  recall_time_ms: number;
}

// ============================================================
// Health Types
// ============================================================

export type HealthStatus = "healthy" | "degraded" | "unhealthy" | "unknown";

export interface ComponentHealth {
  name: string;
  status: HealthStatus;
  latency_ms?: number;
  message?: string;
  details?: Record<string, unknown>;
  last_checked: string;
}

export interface HealthResponse {
  status: HealthStatus;
  is_healthy: boolean;
  is_live: boolean;
  uptime_seconds: number;
  version: string;
  environment: string;
  timestamp: string;
  components?: ComponentHealth[];
}
