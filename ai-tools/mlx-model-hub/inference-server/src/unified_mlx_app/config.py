"""Configuration settings for the Unified MLX App."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Server settings
    host: str = "127.0.0.1"
    api_port: int = 8080
    ui_port: int = 7860

    # Model settings
    text_model: str = "mlx-community/Qwen2.5-7B-Instruct-4bit"
    vision_model: str = "mlx-community/Qwen2-VL-2B-Instruct-4bit"
    speech_model: str = "mlx-community/Llama-OuteTTS-1.0-1B-8bit"
    stt_model: str = "mlx-community/whisper-large-v3-turbo"

    # Available model options for hot-swapping
    available_text_models: list[str] = [
        "mlx-community/Qwen2.5-7B-Instruct-4bit",
        "mlx-community/Qwen2.5-3B-Instruct-4bit",
        "mlx-community/Qwen2.5-1.5B-Instruct-4bit",
    ]
    available_vision_models: list[str] = [
        "mlx-community/Qwen2-VL-2B-Instruct-4bit",
    ]
    available_stt_models: list[str] = [
        "mlx-community/whisper-large-v3-turbo",
        "mlx-community/whisper-large-v3",
        "mlx-community/whisper-small",
    ]

    # Generation defaults
    max_tokens: int = 2048
    temperature: float = 0.7
    top_p: float = 0.9

    # Memory management
    lazy_load: bool = True
    auto_unload_minutes: int = 30

    # Prompt cache settings (KV cache for system prompts)
    prompt_cache_enabled: bool = True
    prompt_cache_dir: Path = Path.home() / ".unified-mlx/cache/prompts"
    prompt_cache_max_entries: int = 10
    prompt_cache_persist: bool = True  # Save to disk for restart survival

    class Config:
        env_prefix = "MLX_"
        env_file = ".env"


settings = Settings()
