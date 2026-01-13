/**
 * KAS (Knowledge Activation System) API Client
 *
 * Provides typed access to the KAS API for search, Q&A, and ingestion.
 */

export interface SearchResult {
  content_id: string;
  title: string;
  content_type: string;
  score: number;
  namespace: string | null;
  chunk_text: string | null;
  source_ref: string | null;
  vector_similarity: number | null;
  bm25_score: number | null;
}

export interface SearchResponse {
  results: SearchResult[];
  query: string;
  total: number;
  source: string;
  reranked: boolean;
}

export interface Citation {
  index: number;
  title: string;
  content_type: string;
  chunk_text: string;
}

export interface AskResponse {
  query: string;
  answer: string;
  confidence: string;
  confidence_score: number;
  citations: Citation[];
  warning: string | null;
  error: string | null;
}

export interface IngestResponse {
  content_id: string;
  success: boolean;
  chunks_created: number;
  message: string;
  namespace: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  services: {
    database: string;
    embeddings: string;
  };
  stats: {
    total_content: number;
    total_chunks: number;
  };
}

export interface IngestExternalResponse {
  content_id: string;
  title: string;
  success: boolean;
  chunks_created: number;
  message: string;
  namespace: string;
}

export interface ReviewItem {
  content_id: string;
  title: string;
  content_type: string;
  preview_text: string | null;
  is_new: boolean;
  is_learning: boolean;
  reps: number;
}

export interface ReviewSubmitResponse {
  success: boolean;
  next_review: string;
  new_state: string;
}

export interface ReviewStats {
  due_now: number;
  new: number;
  learning: number;
  review: number;
  total_active: number;
  reviews_today: number;
}

export interface KASClientOptions {
  baseUrl: string;
  timeout?: number;
}

export class KASClient {
  private baseUrl: string;
  private timeout: number;

  constructor(options: KASClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, '');
    this.timeout = options.timeout ?? 30000;
  }

  private async fetch<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        ...options,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`KAS API error (${response.status}): ${errorText}`);
      }

      return await response.json() as T;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  /**
   * Check KAS API health
   */
  async health(): Promise<HealthResponse> {
    return this.fetch<HealthResponse>('/api/v1/health');
  }

  /**
   * Search the knowledge base
   */
  async search(
    query: string,
    options: {
      limit?: number;
      namespace?: string;
      min_score?: number;
      rerank?: boolean;
    } = {}
  ): Promise<SearchResponse> {
    const params = new URLSearchParams({ q: query });
    if (options.limit) params.set('limit', options.limit.toString());
    if (options.namespace) params.set('namespace', options.namespace);
    if (options.min_score) params.set('min_score', options.min_score.toString());
    if (options.rerank) params.set('rerank', 'true');

    return this.fetch<SearchResponse>(`/api/v1/search?${params}`);
  }

  /**
   * Ask a question and get a synthesized answer
   */
  async ask(
    query: string,
    options: {
      context_limit?: number;
    } = {}
  ): Promise<AskResponse> {
    return this.fetch<AskResponse>('/search/ask', {
      method: 'POST',
      body: JSON.stringify({
        query,
        limit: options.context_limit ?? 5,
      }),
    });
  }

  /**
   * Quick ingest content into KAS
   */
  async ingest(
    content: string,
    options: {
      title: string;
      namespace?: string;
      document_type?: 'markdown' | 'text' | 'code';
      tags?: string[];
      source?: string;
    }
  ): Promise<IngestResponse> {
    return this.fetch<IngestResponse>('/api/v1/ingest/document', {
      method: 'POST',
      body: JSON.stringify({
        content,
        title: options.title,
        namespace: options.namespace ?? 'quick-capture',
        document_type: options.document_type ?? 'markdown',
        metadata: {
          tags: options.tags ?? [],
          source: options.source ?? 'claude-code-mcp',
          captured_at: new Date().toISOString(),
          custom: {},
        },
      }),
    });
  }

  /**
   * List all namespaces
   */
  async listNamespaces(): Promise<{ namespaces: Array<{ name: string; document_count: number }> }> {
    return this.fetch('/api/v1/namespaces');
  }

  /**
   * Get stats about the knowledge base
   */
  async stats(): Promise<HealthResponse['stats']> {
    const health = await this.health();
    return health.stats;
  }

  /**
   * Ingest external content (YouTube, bookmarks, URLs)
   */
  async ingestExternal(
    type: 'youtube' | 'bookmark' | 'url',
    source: string,
    options: {
      title?: string;
      namespace?: string;
      tags?: string[];
    } = {}
  ): Promise<IngestExternalResponse> {
    const endpoint = type === 'youtube' ? '/api/v1/ingest/youtube' : '/api/v1/ingest/bookmark';

    return this.fetch<IngestExternalResponse>(endpoint, {
      method: 'POST',
      body: JSON.stringify({
        url: source,
        video_id: type === 'youtube' ? source : undefined,
        title: options.title,
        namespace: options.namespace,
        tags: options.tags ?? [],
      }),
    });
  }

  /**
   * Get items due for review
   */
  async getReviewItems(limit: number = 5): Promise<ReviewItem[]> {
    const response = await this.fetch<{ items: ReviewItem[] }>(
      `/api/v1/review/due?limit=${limit}`
    );
    return response.items;
  }

  /**
   * Submit a review rating
   */
  async submitReview(
    contentId: string,
    rating: number
  ): Promise<ReviewSubmitResponse> {
    return this.fetch<ReviewSubmitResponse>('/api/v1/review/submit', {
      method: 'POST',
      body: JSON.stringify({
        content_id: contentId,
        rating,
      }),
    });
  }

  /**
   * Get review statistics
   */
  async getReviewStats(): Promise<ReviewStats> {
    return this.fetch<ReviewStats>('/api/v1/review/stats');
  }
}

// Default client instance pointing to local KAS
export const kasClient = new KASClient({
  baseUrl: process.env.KAS_API_URL ?? 'http://localhost:8000',
});
