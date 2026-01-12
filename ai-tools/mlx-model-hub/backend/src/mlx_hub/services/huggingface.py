"""HuggingFace Hub integration service.

Provides search, metadata retrieval, and download capabilities
for MLX models from HuggingFace Hub.
"""

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from mlx_hub.config import get_settings

logger = logging.getLogger(__name__)

# HuggingFace API endpoints
HF_API_BASE = "https://huggingface.co/api"
HF_MODEL_ENDPOINT = f"{HF_API_BASE}/models"


@dataclass
class ModelFile:
    """Information about a model file."""

    filename: str
    size_bytes: int
    lfs: bool = False  # Large File Storage


@dataclass
class ModelMetadata:
    """Metadata for a HuggingFace model."""

    model_id: str
    author: str
    model_name: str
    downloads: int
    likes: int
    tags: list[str]
    pipeline_tag: str | None
    library_name: str | None
    created_at: str | None
    last_modified: str | None

    # Size and memory info
    total_size_bytes: int = 0
    estimated_memory_gb: float = 0.0
    quantization: str | None = None

    # Files
    files: list[ModelFile] = field(default_factory=list)

    @property
    def is_mlx(self) -> bool:
        """Check if this is an MLX model."""
        return "mlx" in self.tags or self.library_name == "mlx"

    @property
    def is_quantized(self) -> bool:
        """Check if this is a quantized model."""
        return self.quantization is not None

    @property
    def size_gb(self) -> float:
        """Get total size in GB."""
        return self.total_size_bytes / (1024**3)


@dataclass
class SearchResult:
    """Search results from HuggingFace."""

    models: list[ModelMetadata]
    total_count: int
    page: int
    page_size: int


class HuggingFaceService:
    """Service for interacting with HuggingFace Hub."""

    def __init__(self, token: str | None = None):
        """Initialize the service.

        Args:
            token: Optional HuggingFace API token for private models.
        """
        self.token = token or os.environ.get("HF_TOKEN")
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            headers = {}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            self._client = httpx.AsyncClient(
                headers=headers,
                timeout=30.0,
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def search_models(
        self,
        query: str = "",
        page: int = 1,
        page_size: int = 20,
        mlx_only: bool = True,
        sort: str = "downloads",
        direction: str = "desc",
    ) -> SearchResult:
        """Search for models on HuggingFace.

        Args:
            query: Search query string.
            page: Page number (1-indexed).
            page_size: Number of results per page.
            mlx_only: Only return MLX models.
            sort: Sort field (downloads, likes, lastModified).
            direction: Sort direction (asc, desc).

        Returns:
            SearchResult with matching models.
        """
        params: dict[str, Any] = {
            "limit": page_size,
            "offset": (page - 1) * page_size,
            "sort": sort,
            "direction": -1 if direction == "desc" else 1,
            "full": "true",  # Get full model info
        }

        if query:
            params["search"] = query

        if mlx_only:
            # Filter for MLX models
            params["filter"] = "mlx"

        try:
            response = await self.client.get(HF_MODEL_ENDPOINT, params=params)
            response.raise_for_status()
            data = response.json()

            models = []
            for item in data:
                metadata = self._parse_model_metadata(item)
                if metadata:
                    models.append(metadata)

            return SearchResult(
                models=models,
                total_count=len(models),  # HF doesn't return total, estimate
                page=page,
                page_size=page_size,
            )

        except httpx.HTTPError as e:
            logger.error(f"HuggingFace API error: {e}")
            return SearchResult(models=[], total_count=0, page=page, page_size=page_size)

    async def get_model_info(self, model_id: str) -> ModelMetadata | None:
        """Get detailed information about a model.

        Args:
            model_id: HuggingFace model ID (e.g., "mlx-community/Llama-3.2-3B-4bit").

        Returns:
            ModelMetadata or None if not found.
        """
        try:
            response = await self.client.get(f"{HF_MODEL_ENDPOINT}/{model_id}")
            response.raise_for_status()
            data = response.json()

            metadata = self._parse_model_metadata(data)

            # Get file list for size info
            if metadata:
                await self._fetch_model_files(metadata)

            return metadata

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            logger.error(f"HuggingFace API error: {e}")
            return None
        except httpx.HTTPError as e:
            logger.error(f"HuggingFace API error: {e}")
            return None

    async def _fetch_model_files(self, metadata: ModelMetadata) -> None:
        """Fetch file information for a model."""
        try:
            response = await self.client.get(f"{HF_API_BASE}/models/{metadata.model_id}/tree/main")
            response.raise_for_status()
            files = response.json()

            total_size = 0
            model_files = []

            for f in files:
                if f.get("type") == "file":
                    size = f.get("size", 0)
                    # LFS files have their size in lfs.size
                    lfs_info = f.get("lfs")
                    if lfs_info:
                        size = lfs_info.get("size", size)

                    model_files.append(
                        ModelFile(
                            filename=f.get("path", ""),
                            size_bytes=size,
                            lfs=lfs_info is not None,
                        )
                    )
                    total_size += size

            metadata.files = model_files
            metadata.total_size_bytes = total_size
            metadata.estimated_memory_gb = self._estimate_memory(metadata)

        except httpx.HTTPError as e:
            logger.warning(f"Could not fetch file info for {metadata.model_id}: {e}")

    def _parse_model_metadata(self, data: dict) -> ModelMetadata | None:
        """Parse model metadata from API response."""
        try:
            model_id = data.get("modelId") or data.get("id", "")
            if "/" in model_id:
                author, model_name = model_id.split("/", 1)
            else:
                author = ""
                model_name = model_id

            tags = data.get("tags", [])

            # Detect quantization from tags or model name
            quantization = self._detect_quantization(model_id, tags)

            return ModelMetadata(
                model_id=model_id,
                author=author,
                model_name=model_name,
                downloads=data.get("downloads", 0),
                likes=data.get("likes", 0),
                tags=tags,
                pipeline_tag=data.get("pipeline_tag"),
                library_name=data.get("library_name"),
                created_at=data.get("createdAt"),
                last_modified=data.get("lastModified"),
                quantization=quantization,
            )
        except Exception as e:
            logger.warning(f"Failed to parse model metadata: {e}")
            return None

    def _detect_quantization(self, model_id: str, tags: list[str]) -> str | None:
        """Detect quantization level from model ID and tags."""
        model_lower = model_id.lower()

        # Common quantization patterns
        patterns = [
            (r"(\d+)bit", lambda m: f"{m.group(1)}-bit"),
            (r"q(\d+)_k_m", lambda m: f"Q{m.group(1)}_K_M"),
            (r"q(\d+)_k_s", lambda m: f"Q{m.group(1)}_K_S"),
            (r"q(\d+)_0", lambda m: f"Q{m.group(1)}_0"),
            (r"q(\d+)", lambda m: f"Q{m.group(1)}"),
            (r"fp16", lambda m: "FP16"),
            (r"bf16", lambda m: "BF16"),
            (r"fp32", lambda m: "FP32"),
        ]

        for pattern, formatter in patterns:
            match = re.search(pattern, model_lower)
            if match:
                return formatter(match)

        # Check tags
        for tag in tags:
            tag_lower = tag.lower()
            if "4bit" in tag_lower or "4-bit" in tag_lower:
                return "4-bit"
            if "8bit" in tag_lower or "8-bit" in tag_lower:
                return "8-bit"

        return None

    def _estimate_memory(self, metadata: ModelMetadata) -> float:
        """Estimate memory requirements for a model.

        This is a rough estimate based on model size and quantization.
        Actual memory usage depends on context length, batch size, etc.
        """
        # Base estimate from file size (model weights)
        base_gb = metadata.total_size_bytes / (1024**3)

        # For MLX models, the safetensors files ARE the model weights
        # Memory usage is roughly: weights + KV cache + activations
        # We estimate ~1.2-1.5x the weight size for inference

        if metadata.quantization:
            # Quantized models are more memory efficient
            if "4" in metadata.quantization:
                multiplier = 1.2
            elif "8" in metadata.quantization:
                multiplier = 1.3
            else:
                multiplier = 1.4
        else:
            # Full precision models need more overhead
            multiplier = 1.5

        return base_gb * multiplier

    def check_memory_compatibility(
        self,
        model: ModelMetadata,
        available_memory_gb: float | None = None,
    ) -> dict:
        """Check if a model is compatible with available memory.

        Args:
            model: Model metadata.
            available_memory_gb: Available memory in GB (auto-detected if None).

        Returns:
            Dict with compatibility info and warnings.
        """
        import psutil

        if available_memory_gb is None:
            # Get system memory
            mem = psutil.virtual_memory()
            available_memory_gb = mem.available / (1024**3)
            total_memory_gb = mem.total / (1024**3)
        else:
            total_memory_gb = available_memory_gb

        required = model.estimated_memory_gb

        # Leave some headroom for system
        safe_threshold = available_memory_gb * 0.8

        if required <= safe_threshold:
            status = "compatible"
            message = f"Model should fit comfortably ({required:.1f}GB needed, {available_memory_gb:.1f}GB available)"
            warning = None
        elif required <= available_memory_gb:
            status = "tight"
            message = f"Model may fit but memory will be tight ({required:.1f}GB needed, {available_memory_gb:.1f}GB available)"
            warning = "Consider closing other applications before loading this model"
        else:
            status = "incompatible"
            message = f"Model is too large for available memory ({required:.1f}GB needed, {available_memory_gb:.1f}GB available)"
            warning = "This model requires more memory than available. Consider a smaller or more quantized version."

        return {
            "status": status,
            "message": message,
            "warning": warning,
            "required_memory_gb": required,
            "available_memory_gb": available_memory_gb,
            "total_memory_gb": total_memory_gb,
        }

    async def download_model(
        self,
        model_id: str,
        output_dir: str | Path | None = None,
        progress_callback: Any | None = None,
    ) -> Path:
        """Download a model from HuggingFace.

        Args:
            model_id: HuggingFace model ID.
            output_dir: Directory to save the model. Must be under storage_models_path.
            progress_callback: Optional callback for download progress.

        Returns:
            Path to the downloaded model directory.

        Raises:
            ValueError: If model_id is invalid or output_dir is outside allowed path.
        """
        from huggingface_hub import snapshot_download

        settings = get_settings()

        # Validate model ID format to prevent injection
        if not self._validate_model_id(model_id):
            raise ValueError(f"Invalid model ID format: {model_id}")

        # Determine and validate output directory
        base_path = settings.storage_models_path.resolve()

        if output_dir is None:
            # Safe: we control the path construction
            safe_name = model_id.replace("/", "--")
            output_dir = base_path / safe_name
        else:
            # User-provided path: validate it's under base_path
            output_dir = Path(output_dir).resolve()
            if not str(output_dir).startswith(str(base_path)):
                logger.warning(f"Path traversal attempt blocked: {output_dir}")
                raise ValueError(f"Output directory must be under {base_path}")

        output_dir.mkdir(parents=True, exist_ok=True)

        # Use huggingface_hub for actual download (handles resume, caching, etc.)
        try:
            path = await asyncio.to_thread(
                snapshot_download,
                repo_id=model_id,
                local_dir=str(output_dir),
                token=self.token,
            )
            return Path(path)
        except Exception as e:
            logger.error(f"Failed to download model {model_id}: {e}")
            raise

    def _validate_model_id(self, model_id: str) -> bool:
        """Validate a HuggingFace model ID format.

        Valid model IDs: owner/model-name
        Characters allowed: alphanumeric, hyphen, underscore, period
        """
        if not model_id or len(model_id) > 256:
            return False

        # Must have exactly one slash
        if model_id.count("/") != 1:
            return False

        # Pattern: alphanumeric, hyphen, underscore, period
        pattern = r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$"
        return bool(re.match(pattern, model_id))


# Global service instance
_hf_service: HuggingFaceService | None = None


def get_huggingface_service() -> HuggingFaceService:
    """Get the global HuggingFace service instance."""
    global _hf_service
    if _hf_service is None:
        _hf_service = HuggingFaceService()
    return _hf_service
