export interface HealthStatus {
  service: string;
  healthy: boolean;
  message: string;
  latency_ms: number | null;
}

export interface AllHealth {
  router: HealthStatus;
  litellm: HealthStatus;
  ollama: HealthStatus;
  redis: HealthStatus;
  langfuse: HealthStatus;
}

export interface ModelConfig {
  model_name: string;
  litellm_params: {
    model: string;
    api_base: string;
  };
}

export interface Config {
  model_list: ModelConfig[];
  litellm_settings: Record<string, unknown>;
  router_settings: Record<string, unknown>;
  general_settings: Record<string, unknown>;
}

export interface RoutingPolicy {
  version: string;
  privacy: {
    enabled: boolean;
    pii_regexes: string[];
    entropy_threshold: number;
    min_token_length: number;
    sensitive_model: string;
  };
  complexity: {
    enabled: boolean;
    simple_max_tokens: number;
    medium_max_tokens: number;
    code_signals: string[];
    reasoning_signals: string[];
  };
  injection: {
    enabled: boolean;
    patterns: string[];
    block_on_injection: boolean;
  };
  routing: Record<string, unknown>;
}

export interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
}

export interface OllamaModel {
  name: string;
  size: string;
  modified: string;
}

export interface Metrics {
  requests: {
    total: number;
    by_model: Record<string, number>;
    by_complexity: Record<string, number>;
    by_routing_reason: Record<string, number>;
  };
  latency: {
    p50_ms: number;
    p95_ms: number;
    p99_ms: number;
    avg_ms: number;
  };
  errors: {
    total: number;
    rate: number;
  };
  security: {
    sensitive_requests: number;
    injection_attempts: number;
  };
  cache: {
    hits: number;
    misses: number;
    hit_rate: number;
  };
  timestamp: string;
}
