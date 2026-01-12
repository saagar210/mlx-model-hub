"""Model registry for managing base and LoRA models."""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default exports directory from mlx-model-hub
DEFAULT_EXPORTS_DIR = "/Users/d/claude-code/ai-tools/mlx-model-hub/exports"


@dataclass
class RegisteredModel:
    """A registered model (base or LoRA)."""
    name: str
    base_model: str
    model_type: str = "base"  # "base" or "lora"
    adapter_path: Optional[str] = None
    config: dict = field(default_factory=dict)
    loaded: bool = False
    source: str = "builtin"  # "builtin", "registered", "scanned"
    registered_by: Optional[str] = None  # e.g., "mlx-model-hub"
    model_id: Optional[str] = None  # Original model ID for traceability


class ModelRegistry:
    """Central registry for all available models.

    Manages:
    - Built-in MLX models
    - Registered LoRA adapters from mlx-model-hub
    - Auto-scanned models from CUSTOM_MODELS_DIR
    """

    def __init__(self):
        self._models: dict[str, RegisteredModel] = {}
        self._loaded_adapters: dict[str, tuple] = {}  # name -> (model, tokenizer)

        # Initialize built-in models
        self._register_builtin_models()

        # Scan custom models directory if configured
        custom_dir = os.environ.get("CUSTOM_MODELS_DIR", DEFAULT_EXPORTS_DIR)
        if custom_dir and Path(custom_dir).exists():
            self.scan_models_directory(custom_dir)

    def _register_builtin_models(self):
        """Register the default built-in models."""
        from ..config import settings

        builtins = [
            RegisteredModel(
                name=settings.text_model,
                base_model=settings.text_model,
                model_type="base",
                source="builtin",
            ),
            RegisteredModel(
                name=settings.vision_model,
                base_model=settings.vision_model,
                model_type="vision",
                source="builtin",
            ),
        ]

        for model in builtins:
            self._models[model.name] = model

    def register_model(
        self,
        name: str,
        base_model: str,
        model_type: str = "lora",
        adapter_path: Optional[str] = None,
        config: Optional[dict] = None,
        source: str = "registered",
        registered_by: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> RegisteredModel:
        """Register a new model (typically a LoRA adapter).

        Args:
            name: Unique name for this model
            base_model: HuggingFace model ID for the base model
            model_type: "base", "lora", or "vision"
            adapter_path: Path to LoRA adapter weights
            config: Model configuration (lora_rank, lora_alpha, etc.)
            source: Where this model came from
            registered_by: Client that registered this model (e.g., "mlx-model-hub")
            model_id: Original model ID for traceability

        Returns:
            The registered model

        Raises:
            ValueError: If model already exists or validation fails
        """
        # Check for duplicate registration
        if name in self._models:
            existing = self._models[name]
            if existing.source != "builtin":
                raise ValueError(f"Model already registered: {name}")

        if model_type == "lora" and not adapter_path:
            raise ValueError("LoRA models require adapter_path")

        if adapter_path and not Path(adapter_path).exists():
            # Try as directory
            adapter_dir = Path(adapter_path)
            if adapter_dir.is_dir():
                # Look for adapters.safetensors
                safetensors = adapter_dir / "adapters.safetensors"
                if safetensors.exists():
                    adapter_path = str(safetensors)
                else:
                    raise ValueError(f"Adapter path not found: {adapter_path}")
            else:
                raise ValueError(f"Adapter path not found: {adapter_path}")

        model = RegisteredModel(
            name=name,
            base_model=base_model,
            model_type=model_type,
            adapter_path=adapter_path,
            config=config or {},
            source=source,
            registered_by=registered_by,
            model_id=model_id,
        )

        self._models[name] = model
        logger.info(f"Registered model: {name} (type={model_type}, base={base_model}, by={registered_by})")

        return model

    def unregister_model(self, name: str) -> bool:
        """Unregister a model."""
        if name in self._models:
            model = self._models[name]
            if model.source == "builtin":
                raise ValueError("Cannot unregister built-in models")

            # Unload if loaded
            if name in self._loaded_adapters:
                del self._loaded_adapters[name]

            del self._models[name]
            logger.info(f"Unregistered model: {name}")
            return True
        return False

    def get_model(self, name: str) -> Optional[RegisteredModel]:
        """Get a registered model by name."""
        return self._models.get(name)

    def list_models(self) -> list[RegisteredModel]:
        """List all registered models."""
        return list(self._models.values())

    def scan_models_directory(self, directory: str):
        """Scan a directory for exported models.

        Expected structure:
        directory/
            model-name-1/
                adapters.safetensors
                config.json
                metadata.json (optional)
            model-name-2/
                ...
        """
        base_path = Path(directory)
        if not base_path.exists():
            logger.warning(f"Models directory not found: {directory}")
            return

        for model_dir in base_path.iterdir():
            if not model_dir.is_dir():
                continue

            config_path = model_dir / "config.json"
            adapter_path = model_dir / "adapters.safetensors"

            if not config_path.exists():
                continue

            try:
                with open(config_path) as f:
                    config = json.load(f)

                # Read metadata if available
                metadata = {}
                metadata_path = model_dir / "metadata.json"
                if metadata_path.exists():
                    with open(metadata_path) as f:
                        metadata = json.load(f)

                model_name = model_dir.name
                base_model = config.get("base_model", "")

                if not base_model:
                    logger.warning(f"Skipping {model_name}: no base_model in config")
                    continue

                self.register_model(
                    name=model_name,
                    base_model=base_model,
                    model_type="lora" if adapter_path.exists() else "base",
                    adapter_path=str(adapter_path) if adapter_path.exists() else None,
                    config={
                        **config,
                        "metadata": metadata,
                    },
                    source="scanned",
                )

            except Exception as e:
                logger.error(f"Error scanning model {model_dir.name}: {e}")

    def load_model(self, name: str):
        """Load a model into memory.

        Returns (model, tokenizer) tuple.
        For LoRA models, applies the adapter to the base model.
        """
        model_info = self.get_model(name)
        if not model_info:
            raise ValueError(f"Model not found: {name}")

        # Check cache
        if name in self._loaded_adapters:
            return self._loaded_adapters[name]

        from mlx_lm import load

        if model_info.model_type == "lora" and model_info.adapter_path:
            # Load base model with adapter
            logger.info(f"Loading LoRA model: {name} (base={model_info.base_model})")
            model, tokenizer = load(
                model_info.base_model,
                adapter_path=model_info.adapter_path,
            )
        else:
            # Load base model
            logger.info(f"Loading base model: {name}")
            model, tokenizer = load(model_info.base_model)

        # Cache
        self._loaded_adapters[name] = (model, tokenizer)
        model_info.loaded = True

        return model, tokenizer

    def unload_model(self, name: str) -> bool:
        """Unload a model from memory."""
        if name in self._loaded_adapters:
            del self._loaded_adapters[name]
            if name in self._models:
                self._models[name].loaded = False
            logger.info(f"Unloaded model: {name}")
            return True
        return False

    def get_status(self, registered_by: Optional[str] = None) -> dict:
        """Get registry status.

        Args:
            registered_by: Filter by registering client (e.g., "mlx-model-hub")
        """
        models = self._models.items()
        if registered_by:
            models = [(n, m) for n, m in models if m.registered_by == registered_by]
        else:
            models = list(models)

        return {
            "total_models": len(models),
            "loaded_models": sum(1 for _, m in models if m.loaded),
            "models": {
                name: {
                    "type": m.model_type,
                    "base": m.base_model,
                    "loaded": m.loaded,
                    "source": m.source,
                    "registered_by": m.registered_by,
                    "model_id": m.model_id,
                }
                for name, m in models
            },
        }

    def get_model_status(self, name: str) -> Optional[dict]:
        """Get status for a specific model.

        Returns:
            Status dict or None if model not found
        """
        model = self._models.get(name)
        if not model:
            return None

        return {
            "registered": True,
            "loaded": model.loaded,
            "base_model": model.base_model,
            "type": model.model_type,
            "adapter_path": model.adapter_path,
            "source": model.source,
            "registered_by": model.registered_by,
            "model_id": model.model_id,
        }


# Singleton instance
model_registry = ModelRegistry()
