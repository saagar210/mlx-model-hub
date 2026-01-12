"""Model export service for unified-mlx-app integration."""

import json
import logging
import shutil
from pathlib import Path
from typing import Any

import httpx

from mlx_hub.config import get_settings
from mlx_hub.db.models import Model, ModelVersion

logger = logging.getLogger(__name__)


async def create_export_bundle(
    model: Model,
    version: ModelVersion,
) -> Path:
    """Create a standardized bundle for unified-mlx-app.

    Bundle structure:
        exports/
          {model_name}/
            adapters.safetensors  # LoRA weights
            config.json           # Model config
            metadata.json         # Training metadata

    Args:
        model: Model database record.
        version: ModelVersion with trained adapter.

    Returns:
        Path to the export directory.

    Raises:
        ValueError: If adapter path doesn't exist.
    """
    settings = get_settings()

    # Create export directory
    export_dir = Path(settings.storage_models_path) / "exports" / model.name
    export_dir.mkdir(parents=True, exist_ok=True)

    # Verify adapter exists
    if not version.artifact_path:
        raise ValueError(f"Version {version.id} has no artifact path")

    adapter_src = Path(version.artifact_path)
    if not adapter_src.exists():
        raise ValueError(f"Adapter file not found: {adapter_src}")

    # Copy adapter weights
    adapter_dst = export_dir / "adapters.safetensors"
    logger.info(f"Copying adapter from {adapter_src} to {adapter_dst}")
    shutil.copy2(adapter_src, adapter_dst)

    # Write config
    config = {
        "base_model": model.base_model,
        "lora_rank": version.metrics.get("lora_rank", 16),
        "lora_alpha": version.metrics.get("lora_alpha", 32),
        "adapter_path": str(adapter_dst.absolute()),
        "model_type": "lora",
    }
    config_path = export_dir / "config.json"
    config_path.write_text(json.dumps(config, indent=2))
    logger.info(f"Wrote config to {config_path}")

    # Write metadata
    metadata = {
        "model_id": str(model.id),
        "version_id": str(version.id),
        "model_name": model.name,
        "created_at": version.created_at.isoformat() if version.created_at else None,
        "description": model.description,
        "training_metrics": {
            "final_loss": version.metrics.get("final_loss"),
            "total_steps": version.metrics.get("total_steps"),
            "epochs": version.metrics.get("epochs_completed"),
        },
    }
    metadata_path = export_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2))
    logger.info(f"Wrote metadata to {metadata_path}")

    logger.info(f"Export bundle created at {export_dir}")
    return export_dir


async def register_with_inference_server(
    export_path: Path,
    inference_url: str | None = None,
) -> dict[str, Any]:
    """Register the exported model with unified-mlx-app.

    Args:
        export_path: Path to the export bundle directory.
        inference_url: Optional inference server URL (defaults to settings).

    Returns:
        Registration response from inference server.

    Raises:
        httpx.HTTPError: If registration fails.
    """
    settings = get_settings()
    inference_url = inference_url or settings.inference_server_url

    # Load config
    config_path = export_path / "config.json"
    if not config_path.exists():
        raise ValueError(f"Config file not found: {config_path}")

    config = json.loads(config_path.read_text())
    metadata_path = export_path / "metadata.json"
    metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}

    # Prepare registration payload with traceability
    payload = {
        "name": export_path.name,
        "base_model": config["base_model"],
        "adapter_path": config["adapter_path"],
        "type": "lora",
        "config": {
            "lora_rank": config.get("lora_rank", 16),
            "lora_alpha": config.get("lora_alpha", 32),
        },
        "metadata": metadata,
        "registered_by": "mlx-model-hub",  # Track registration source
        "model_id": metadata.get("model_id"),  # Link to mlx-model-hub model
    }

    # Call unified-mlx-app admin API
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            logger.info(f"Registering model with inference server: {inference_url}/admin/models/register")
            response = await client.post(
                f"{inference_url}/admin/models/register",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"Successfully registered {export_path.name} with inference server")
            return result

        except httpx.ConnectError:
            error_msg = f"Could not connect to inference server at {inference_url}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == 409:
                # Model already registered - this is okay
                logger.info(f"Model {export_path.name} already registered with inference server")
                return {"status": "already_registered", "model": export_path.name}
            elif status == 404:
                error_msg = f"Inference server endpoint not found: {e.response.text}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            elif status == 400:
                error_msg = f"Invalid registration data: {e.response.text}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            else:
                error_msg = f"Registration failed with status {status}: {e.response.text}"
                logger.error(error_msg)
                raise ValueError(error_msg)


async def get_export_info(model_name: str) -> dict[str, Any] | None:
    """Get information about an exported model.

    Args:
        model_name: Name of the model.

    Returns:
        Export info dictionary or None if not found.
    """
    settings = get_settings()
    export_dir = Path(settings.storage_models_path) / "exports" / model_name

    if not export_dir.exists():
        return None

    # Load metadata
    metadata_path = export_dir / "metadata.json"
    config_path = export_dir / "config.json"

    if not metadata_path.exists() or not config_path.exists():
        return None

    metadata = json.loads(metadata_path.read_text())
    config = json.loads(config_path.read_text())

    return {
        "export_path": str(export_dir),
        "metadata": metadata,
        "config": config,
        "adapter_exists": (export_dir / "adapters.safetensors").exists(),
    }
