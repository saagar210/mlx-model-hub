"""Model discovery API endpoints.

Provides endpoints for searching, browsing, and downloading
MLX models from HuggingFace Hub.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from mlx_hub.services.huggingface import (
    HuggingFaceService,
    ModelMetadata,
    get_huggingface_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/discover", tags=["discover"])


# Response models
class ModelFileResponse(BaseModel):
    """Response model for a model file."""

    filename: str
    size_bytes: int
    lfs: bool = False


class ModelInfoResponse(BaseModel):
    """Response model for model information."""

    model_id: str
    author: str
    model_name: str
    downloads: int
    likes: int
    tags: list[str]
    pipeline_tag: str | None = None
    library_name: str | None = None
    created_at: str | None = None
    last_modified: str | None = None

    # Size and memory info
    total_size_bytes: int = 0
    size_gb: float = 0.0
    estimated_memory_gb: float = 0.0
    quantization: str | None = None

    # Flags
    is_mlx: bool = False
    is_quantized: bool = False

    # Files
    files: list[ModelFileResponse] = []


class SearchResultResponse(BaseModel):
    """Response model for search results."""

    models: list[ModelInfoResponse]
    total_count: int
    page: int
    page_size: int


class MemoryCompatibilityResponse(BaseModel):
    """Response model for memory compatibility check."""

    status: str  # "compatible", "tight", "incompatible"
    message: str
    warning: str | None = None
    required_memory_gb: float
    available_memory_gb: float
    total_memory_gb: float


class DownloadStatusResponse(BaseModel):
    """Response model for download status."""

    model_id: str
    status: str  # "pending", "downloading", "completed", "failed"
    progress_percent: float = 0.0
    downloaded_bytes: int = 0
    total_bytes: int = 0
    error: str | None = None
    output_path: str | None = None


class DownloadRequest(BaseModel):
    """Request model for starting a download."""

    output_dir: str | None = Field(None, description="Optional custom output directory")


# In-memory download tracking (in production, use Redis or database)
_download_status: dict[str, DownloadStatusResponse] = {}


def _metadata_to_response(metadata: ModelMetadata) -> ModelInfoResponse:
    """Convert ModelMetadata to API response."""
    return ModelInfoResponse(
        model_id=metadata.model_id,
        author=metadata.author,
        model_name=metadata.model_name,
        downloads=metadata.downloads,
        likes=metadata.likes,
        tags=metadata.tags,
        pipeline_tag=metadata.pipeline_tag,
        library_name=metadata.library_name,
        created_at=metadata.created_at,
        last_modified=metadata.last_modified,
        total_size_bytes=metadata.total_size_bytes,
        size_gb=metadata.size_gb,
        estimated_memory_gb=metadata.estimated_memory_gb,
        quantization=metadata.quantization,
        is_mlx=metadata.is_mlx,
        is_quantized=metadata.is_quantized,
        files=[
            ModelFileResponse(
                filename=f.filename,
                size_bytes=f.size_bytes,
                lfs=f.lfs,
            )
            for f in metadata.files
        ],
    )


@router.get("/search", response_model=SearchResultResponse)
async def search_models(
    query: Annotated[str, Query(description="Search query")] = "",
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Results per page")] = 20,
    mlx_only: Annotated[bool, Query(description="Only show MLX models")] = True,
    sort: Annotated[
        str, Query(description="Sort field: downloads, likes, lastModified")
    ] = "downloads",
    direction: Annotated[str, Query(description="Sort direction: asc, desc")] = "desc",
    hf_service: HuggingFaceService = Depends(get_huggingface_service),
) -> SearchResultResponse:
    """Search for MLX models on HuggingFace.

    Returns a paginated list of models matching the search criteria.
    By default, only returns MLX-compatible models sorted by downloads.
    """
    result = await hf_service.search_models(
        query=query,
        page=page,
        page_size=page_size,
        mlx_only=mlx_only,
        sort=sort,
        direction=direction,
    )

    return SearchResultResponse(
        models=[_metadata_to_response(m) for m in result.models],
        total_count=result.total_count,
        page=result.page,
        page_size=result.page_size,
    )


@router.get("/models/{model_id:path}/compatibility", response_model=MemoryCompatibilityResponse)
async def check_compatibility(
    model_id: str,
    available_memory_gb: Annotated[
        float | None, Query(description="Override available memory (GB)")
    ] = None,
    hf_service: HuggingFaceService = Depends(get_huggingface_service),
) -> MemoryCompatibilityResponse:
    """Check if a model is compatible with available system memory.

    Returns memory compatibility status and warnings if the model
    may not fit in available memory.
    """
    metadata = await hf_service.get_model_info(model_id)

    if metadata is None:
        raise HTTPException(status_code=404, detail=f"Model not found: {model_id}")

    result = hf_service.check_memory_compatibility(
        metadata, available_memory_gb=available_memory_gb
    )

    return MemoryCompatibilityResponse(**result)


@router.get("/models/{model_id:path}", response_model=ModelInfoResponse)
async def get_model_info(
    model_id: str,
    hf_service: HuggingFaceService = Depends(get_huggingface_service),
) -> ModelInfoResponse:
    """Get detailed information about a specific model.

    The model_id should be in the format "owner/model-name"
    (e.g., "mlx-community/Llama-3.2-3B-4bit").
    """
    metadata = await hf_service.get_model_info(model_id)

    if metadata is None:
        raise HTTPException(status_code=404, detail=f"Model not found: {model_id}")

    return _metadata_to_response(metadata)


@router.post("/models/{model_id:path}/download", response_model=DownloadStatusResponse)
async def start_download(
    model_id: str,
    background_tasks: BackgroundTasks,
    request: DownloadRequest | None = None,
    hf_service: HuggingFaceService = Depends(get_huggingface_service),
) -> DownloadStatusResponse:
    """Start downloading a model from HuggingFace.

    The download runs in the background. Use GET /download/{model_id}/status
    to check progress.
    """
    # Check if model exists
    metadata = await hf_service.get_model_info(model_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail=f"Model not found: {model_id}")

    # Check if already downloading
    if model_id in _download_status:
        status = _download_status[model_id]
        if status.status == "downloading":
            return status

    # Initialize download status
    status = DownloadStatusResponse(
        model_id=model_id,
        status="pending",
        total_bytes=metadata.total_size_bytes,
    )
    _download_status[model_id] = status

    # Start background download
    output_dir = request.output_dir if request else None

    async def download_task():
        try:
            _download_status[model_id].status = "downloading"

            path = await hf_service.download_model(
                model_id=model_id,
                output_dir=output_dir,
            )

            _download_status[model_id].status = "completed"
            _download_status[model_id].progress_percent = 100.0
            _download_status[model_id].downloaded_bytes = metadata.total_size_bytes
            _download_status[model_id].output_path = str(path)

        except ValueError as e:
            # Path validation or model ID validation error
            logger.error(f"Download validation failed for {model_id}: {e}")
            _download_status[model_id].status = "failed"
            _download_status[model_id].error = str(e)
        except Exception as e:
            logger.error(f"Download failed for {model_id}: {e}")
            _download_status[model_id].status = "failed"
            _download_status[model_id].error = str(e)

    # FastAPI's BackgroundTasks handles coroutines directly
    background_tasks.add_task(download_task)

    return status


@router.get("/download/{model_id:path}/status", response_model=DownloadStatusResponse)
async def get_download_status(model_id: str) -> DownloadStatusResponse:
    """Get the current download status for a model."""
    if model_id not in _download_status:
        raise HTTPException(
            status_code=404,
            detail=f"No download found for model: {model_id}",
        )

    return _download_status[model_id]


@router.delete("/download/{model_id:path}")
async def cancel_download(model_id: str) -> dict:
    """Cancel an ongoing download.

    Note: This marks the download as cancelled but may not immediately
    stop the underlying huggingface_hub download.
    """
    if model_id not in _download_status:
        raise HTTPException(
            status_code=404,
            detail=f"No download found for model: {model_id}",
        )

    status = _download_status[model_id]
    if status.status == "downloading":
        status.status = "cancelled"
        status.error = "Cancelled by user"

    return {"message": f"Download cancelled for {model_id}"}


@router.get("/popular", response_model=SearchResultResponse)
async def get_popular_models(
    limit: Annotated[int, Query(ge=1, le=50, description="Number of models")] = 10,
    hf_service: HuggingFaceService = Depends(get_huggingface_service),
) -> SearchResultResponse:
    """Get the most popular MLX models.

    Returns the top MLX models sorted by download count.
    """
    result = await hf_service.search_models(
        query="",
        page=1,
        page_size=limit,
        mlx_only=True,
        sort="downloads",
        direction="desc",
    )

    return SearchResultResponse(
        models=[_metadata_to_response(m) for m in result.models],
        total_count=result.total_count,
        page=1,
        page_size=limit,
    )


@router.get("/recent", response_model=SearchResultResponse)
async def get_recent_models(
    limit: Annotated[int, Query(ge=1, le=50, description="Number of models")] = 10,
    hf_service: HuggingFaceService = Depends(get_huggingface_service),
) -> SearchResultResponse:
    """Get recently updated MLX models.

    Returns the most recently modified MLX models.
    """
    result = await hf_service.search_models(
        query="",
        page=1,
        page_size=limit,
        mlx_only=True,
        sort="lastModified",
        direction="desc",
    )

    return SearchResultResponse(
        models=[_metadata_to_response(m) for m in result.models],
        total_count=result.total_count,
        page=1,
        page_size=limit,
    )
