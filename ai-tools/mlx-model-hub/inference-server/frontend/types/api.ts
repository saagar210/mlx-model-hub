export interface Message {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

export interface ChatCompletionRequest {
  model: string;
  messages: Message[];
  temperature?: number;
  top_p?: number;
  max_tokens?: number;
  stream?: boolean;
}

export interface ChatCompletionChoice {
  index: number;
  message: Message;
  finish_reason: string | null;
}

export interface Usage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface ChatCompletionResponse {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: ChatCompletionChoice[];
  usage: Usage;
}

export interface StreamDelta {
  content?: string;
}

export interface StreamChoice {
  index: number;
  delta: StreamDelta;
  finish_reason: string | null;
}

export interface ChatCompletionChunk {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: StreamChoice[];
}

export interface SpeechRequest {
  model: string;
  input: string;
  voice?: string;
  response_format?: 'wav' | 'mp3';
  speed?: number;
}

export interface TranscriptionResponse {
  text: string;
}

export interface VisionResponse {
  text: string;
  prompt_tokens: number;
  generation_tokens: number;
}

export interface ModelInfo {
  id: string;
  object: string;
  created: number;
  owned_by: string;
}

export interface ModelList {
  object: string;
  data: ModelInfo[];
}

export interface ModelStatus {
  loaded: boolean;
  model_path?: string;
  loaded_at?: number;
  last_used?: number;
  loading?: boolean;
}

export interface HealthResponse {
  status: string;
  models: {
    text: ModelStatus;
    vision: ModelStatus;
    speech: ModelStatus;
    stt: ModelStatus;
  };
}
