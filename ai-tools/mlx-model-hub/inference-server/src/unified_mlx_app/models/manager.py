"""Model Manager with lazy loading and memory tracking."""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)


class ModelType(Enum):
    """Types of models supported."""

    TEXT = "text"
    VISION = "vision"
    SPEECH = "speech"
    STT = "stt"


@dataclass
class LoadedModel:
    """Container for a loaded model with metadata."""

    model: Any
    tokenizer: Any = None
    processor: Any = None
    model_path: str = ""
    model_type: ModelType = ModelType.TEXT
    loaded_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    memory_mb: float = 0.0


class ModelManager:
    """Manages MLX model loading, caching, and memory."""

    def __init__(self):
        self._models: dict[ModelType, LoadedModel | None] = {
            ModelType.TEXT: None,
            ModelType.VISION: None,
            ModelType.SPEECH: None,
            ModelType.STT: None,
        }
        self._locks: dict[ModelType, Lock] = {
            ModelType.TEXT: Lock(),
            ModelType.VISION: Lock(),
            ModelType.SPEECH: Lock(),
            ModelType.STT: Lock(),
        }
        self._loading: dict[ModelType, bool] = {
            ModelType.TEXT: False,
            ModelType.VISION: False,
            ModelType.SPEECH: False,
            ModelType.STT: False,
        }

    def get_text_model(self, model_path: str | None = None, force_reload: bool = False):
        """Get or load the text generation model."""
        import gc
        from ..config import settings

        model_path = model_path or settings.text_model

        with self._locks[ModelType.TEXT]:
            if self._models[ModelType.TEXT] is not None:
                loaded = self._models[ModelType.TEXT]
                if loaded.model_path == model_path and not force_reload:
                    loaded.last_used = time.time()
                    return loaded.model, loaded.tokenizer
                # Different model or force reload - unload first
                self._models[ModelType.TEXT] = None
                gc.collect()

            self._loading[ModelType.TEXT] = True

        try:
            logger.info(f"Loading text model: {model_path}")
            from mlx_lm import load

            model, tokenizer = load(model_path)

            with self._locks[ModelType.TEXT]:
                self._models[ModelType.TEXT] = LoadedModel(
                    model=model,
                    tokenizer=tokenizer,
                    model_path=model_path,
                    model_type=ModelType.TEXT,
                )
                self._loading[ModelType.TEXT] = False

            logger.info(f"Text model loaded: {model_path}")
            return model, tokenizer

        except Exception as e:
            with self._locks[ModelType.TEXT]:
                self._loading[ModelType.TEXT] = False
            logger.error(f"Failed to load text model: {e}")
            raise

    def get_vision_model(self, model_path: str | None = None, force_reload: bool = False):
        """Get or load the vision-language model."""
        import gc
        from ..config import settings

        model_path = model_path or settings.vision_model

        with self._locks[ModelType.VISION]:
            if self._models[ModelType.VISION] is not None:
                loaded = self._models[ModelType.VISION]
                if loaded.model_path == model_path and not force_reload:
                    loaded.last_used = time.time()
                    return loaded.model, loaded.processor
                # Different model or force reload - unload first
                self._models[ModelType.VISION] = None
                gc.collect()

            self._loading[ModelType.VISION] = True

        try:
            logger.info(f"Loading vision model: {model_path}")
            from mlx_vlm import load

            model, processor = load(model_path)

            with self._locks[ModelType.VISION]:
                self._models[ModelType.VISION] = LoadedModel(
                    model=model,
                    processor=processor,
                    model_path=model_path,
                    model_type=ModelType.VISION,
                )
                self._loading[ModelType.VISION] = False

            logger.info(f"Vision model loaded: {model_path}")
            return model, processor

        except Exception as e:
            with self._locks[ModelType.VISION]:
                self._loading[ModelType.VISION] = False
            logger.error(f"Failed to load vision model: {e}")
            raise

    def get_speech_model(self, model_path: str | None = None, force_reload: bool = False):
        """Get or load the text-to-speech model."""
        import gc
        from ..config import settings

        model_path = model_path or settings.speech_model

        with self._locks[ModelType.SPEECH]:
            if self._models[ModelType.SPEECH] is not None:
                loaded = self._models[ModelType.SPEECH]
                if loaded.model_path == model_path and not force_reload:
                    loaded.last_used = time.time()
                    return loaded.model
                # Different model or force reload - unload first
                self._models[ModelType.SPEECH] = None
                gc.collect()

            self._loading[ModelType.SPEECH] = True

        try:
            logger.info(f"Loading speech model: {model_path}")

            # Suppress transformer warnings about missing PyTorch
            import warnings
            import os
            os.environ['TRANSFORMERS_NO_ADVISORY_WARNINGS'] = '1'
            warnings.filterwarnings('ignore', message='.*PyTorch.*')

            from mlx_audio.tts.utils import load_model

            model = load_model(model_path)

            with self._locks[ModelType.SPEECH]:
                self._models[ModelType.SPEECH] = LoadedModel(
                    model=model,
                    model_path=model_path,
                    model_type=ModelType.SPEECH,
                )
                self._loading[ModelType.SPEECH] = False

            logger.info(f"Speech model loaded: {model_path}")
            return model

        except Exception as e:
            with self._locks[ModelType.SPEECH]:
                self._loading[ModelType.SPEECH] = False
            logger.error(f"Failed to load speech model: {e}")
            logger.exception("Full traceback:")
            raise

    def get_stt_model(self, model_path: str | None = None, force_reload: bool = False):
        """Get or load the speech-to-text model."""
        import gc
        from ..config import settings

        model_path = model_path or settings.stt_model

        with self._locks[ModelType.STT]:
            if self._models[ModelType.STT] is not None:
                loaded = self._models[ModelType.STT]
                if loaded.model_path == model_path and not force_reload:
                    loaded.last_used = time.time()
                    return loaded.model
                # Different model or force reload - unload first
                self._models[ModelType.STT] = None
                gc.collect()

            self._loading[ModelType.STT] = True

        try:
            logger.info(f"Loading STT model: {model_path}")
            from mlx_audio.stt.utils import load_model

            model = load_model(model_path)

            with self._locks[ModelType.STT]:
                self._models[ModelType.STT] = LoadedModel(
                    model=model,
                    model_path=model_path,
                    model_type=ModelType.STT,
                )
                self._loading[ModelType.STT] = False

            logger.info(f"STT model loaded: {model_path}")
            return model

        except Exception as e:
            with self._locks[ModelType.STT]:
                self._loading[ModelType.STT] = False
            logger.error(f"Failed to load STT model: {e}")
            raise

    def unload_model(self, model_type: ModelType) -> bool:
        """Unload a model to free memory."""
        import gc

        with self._locks[model_type]:
            if self._models[model_type] is None:
                return False

            model_path = self._models[model_type].model_path
            self._models[model_type] = None
            gc.collect()

            logger.info(f"Unloaded {model_type.value} model: {model_path}")
            return True

    def get_status(self) -> dict:
        """Get status of all models."""
        status = {}
        for model_type in ModelType:
            with self._locks[model_type]:
                loaded = self._models[model_type]
                if loaded:
                    status[model_type.value] = {
                        "loaded": True,
                        "model_path": loaded.model_path,
                        "loaded_at": loaded.loaded_at,
                        "last_used": loaded.last_used,
                    }
                else:
                    status[model_type.value] = {
                        "loaded": False,
                        "loading": self._loading[model_type],
                    }
        return status

    def is_model_loaded(self, model_type: ModelType) -> bool:
        """Check if a model is loaded."""
        with self._locks[model_type]:
            return self._models[model_type] is not None


# Global singleton
model_manager = ModelManager()
