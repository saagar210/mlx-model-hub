"""Vision service for image analysis."""

import base64
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ..models import model_manager

logger = logging.getLogger(__name__)


@dataclass
class VisionResult:
    """Result from vision analysis."""
    text: str
    prompt_tokens: int = 0
    generation_tokens: int = 0


class VisionService:
    """Service for vision/image analysis using MLX VLM models."""

    def __init__(self):
        self._model = None
        self._processor = None

    def _ensure_model(self, model_path: str, force_reload: bool = False):
        """Ensure vision model is loaded."""
        self._model, self._processor = model_manager.get_vision_model(
            model_path, force_reload=force_reload
        )

    def analyze_image(
        self,
        image_path: str | Path,
        prompt: str,
        model_path: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> VisionResult:
        """Analyze an image with a text prompt."""
        from mlx_vlm import generate

        self._ensure_model(model_path)

        # Build chat message with image
        messages = [
            {'role': 'user', 'content': [
                {'type': 'image'},
                {'type': 'text', 'text': prompt}
            ]}
        ]

        formatted_prompt = self._processor.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        result = generate(
            self._model,
            self._processor,
            prompt=formatted_prompt,
            image=str(image_path),
            max_tokens=max_tokens,
            temp=temperature,
            verbose=False,
        )

        return VisionResult(
            text=result.text,
            prompt_tokens=result.prompt_tokens,
            generation_tokens=result.generation_tokens,
        )

    def analyze_image_base64(
        self,
        image_base64: str,
        prompt: str,
        model_path: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> VisionResult:
        """Analyze a base64-encoded image."""
        # Decode and save to temp file
        image_data = base64.b64decode(image_base64)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as f:
            f.write(image_data)
            temp_path = f.name

        try:
            return self.analyze_image(
                temp_path, prompt, model_path, max_tokens, temperature
            )
        finally:
            Path(temp_path).unlink(missing_ok=True)


# Singleton instance
vision_service = VisionService()
