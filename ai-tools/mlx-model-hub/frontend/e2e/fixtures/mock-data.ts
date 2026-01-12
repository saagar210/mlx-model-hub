// Mock data for E2E tests

export const mockModels = {
  items: [
    {
      id: "model-1",
      name: "Test Model 1",
      task_type: "text-generation",
      description: "A test model for E2E testing",
      base_model: "mlx-community/Llama-3.2-3B-Instruct-4bit",
      tags: {},
      mlflow_experiment_id: null,
      version_count: 1,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    },
    {
      id: "model-2",
      name: "Test Model 2",
      task_type: "chat",
      description: "Another test model",
      base_model: "mlx-community/Mistral-7B-Instruct-4bit",
      tags: {},
      mlflow_experiment_id: null,
      version_count: 2,
      created_at: "2024-01-02T00:00:00Z",
      updated_at: "2024-01-02T00:00:00Z",
    },
  ],
  total: 2,
  page: 1,
  page_size: 20,
}

export const mockTrainingJobs = {
  items: [
    {
      id: "job-123-456-789",
      model_id: "model-1",
      status: "running" as const,
      config: {
        base_model: "mlx-community/Llama-3.2-3B-Instruct-4bit",
        dataset_path: "/data/train.jsonl",
        output_dir: "/output",
        num_epochs: 3,
        batch_size: 4,
        learning_rate: 0.0001,
        use_lora: true,
        lora_rank: 8,
        lora_alpha: 16,
      },
      metrics: {
        epoch: 1,
        step: 100,
        loss: 2.5,
        learning_rate: 0.0001,
        tokens_per_second: 45.2,
      },
      started_at: "2024-01-01T10:00:00Z",
      created_at: "2024-01-01T09:55:00Z",
      updated_at: "2024-01-01T10:30:00Z",
    },
    {
      id: "job-987-654-321",
      model_id: "model-2",
      status: "completed" as const,
      config: {
        base_model: "mlx-community/Mistral-7B-Instruct-4bit",
        dataset_path: "/data/train2.jsonl",
        output_dir: "/output2",
        num_epochs: 5,
        batch_size: 2,
        learning_rate: 0.00005,
        use_lora: true,
        lora_rank: 16,
        lora_alpha: 32,
      },
      metrics: {
        epoch: 5,
        step: 500,
        loss: 0.8,
        learning_rate: 0.00005,
        tokens_per_second: 38.5,
      },
      started_at: "2024-01-01T08:00:00Z",
      completed_at: "2024-01-01T09:30:00Z",
      created_at: "2024-01-01T07:55:00Z",
      updated_at: "2024-01-01T09:30:00Z",
    },
  ],
  total: 2,
  page: 1,
  page_size: 20,
}

export const mockHealth = {
  status: "healthy",
  version: "0.1.0",
  timestamp: new Date().toISOString(),
}

export const mockMetrics = {
  models_loaded: 2,
  active_inferences: 1,
  training_jobs_running: 1,
  cache_size_bytes: 5368709120, // 5 GB
  uptime_seconds: 86400, // 24 hours
}

export const mockDiscoverModels = {
  models: [
    {
      model_id: "mlx-community/Llama-3.2-3B-Instruct-4bit",
      author: "mlx-community",
      model_name: "Llama-3.2-3B-Instruct-4bit",
      downloads: 150000,
      likes: 2500,
      tags: ["llama", "4bit", "instruct", "mlx"],
      pipeline_tag: "text-generation",
      library_name: "mlx",
      total_size_bytes: 2147483648,
      size_gb: 2.0,
      estimated_memory_gb: 3.5,
      quantization: "4bit",
      is_mlx: true,
      is_quantized: true,
      files: [],
    },
    {
      model_id: "mlx-community/Mistral-7B-Instruct-4bit",
      author: "mlx-community",
      model_name: "Mistral-7B-Instruct-4bit",
      downloads: 120000,
      likes: 1800,
      tags: ["mistral", "4bit", "instruct", "mlx"],
      pipeline_tag: "text-generation",
      library_name: "mlx",
      total_size_bytes: 4294967296,
      size_gb: 4.0,
      estimated_memory_gb: 6.5,
      quantization: "4bit",
      is_mlx: true,
      is_quantized: true,
      files: [],
    },
  ],
  total_count: 2,
  page: 1,
  page_size: 20,
}

export const mockCompatibility = {
  status: "compatible" as const,
  message: "Model fits comfortably in available memory",
  required_memory_gb: 3.5,
  available_memory_gb: 32.0,
  total_memory_gb: 48.0,
}

// Empty state mocks
export const emptyModels = { items: [], total: 0, page: 1, page_size: 20 }
export const emptyTrainingJobs = { items: [], total: 0, page: 1, page_size: 20 }
export const emptyDiscoverModels = { models: [], total_count: 0, page: 1, page_size: 20 }
