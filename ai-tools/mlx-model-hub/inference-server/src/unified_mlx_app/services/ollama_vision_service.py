"""Ollama-based vision service using llama3.2-vision."""

import base64
import logging
import httpx
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_VISION_MODEL = "llama3.2-vision:11b"


@dataclass
class OllamaVisionResult:
    """Result from Ollama vision analysis."""
    text: str
    model: str
    total_duration: Optional[int] = None  # nanoseconds
    eval_count: Optional[int] = None  # tokens generated


class OllamaVisionService:
    """Vision service using Ollama's llama3.2-vision model.

    This provides an alternative to MLX-based vision when:
    - PyTorch dependencies are blocked
    - You want to use Ollama's model management
    - You need a more stable/tested vision model
    """

    def __init__(self, base_url: str = OLLAMA_BASE_URL):
        self.base_url = base_url
        self._client = httpx.Client(timeout=300.0)  # 5 minutes for long generations

    def _encode_image(self, image_path: str | Path) -> str:
        """Encode image to base64."""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def analyze_image(
        self,
        image_path: str | Path,
        prompt: str,
        model: str = DEFAULT_VISION_MODEL,
        stream: bool = False,
    ) -> OllamaVisionResult:
        """Analyze an image with a text prompt using Ollama vision.

        Args:
            image_path: Path to the image file
            prompt: Text prompt describing what to analyze
            model: Ollama model name (default: llama3.2-vision:11b)
            stream: Whether to stream the response

        Returns:
            OllamaVisionResult with the analysis text
        """
        image_b64 = self._encode_image(image_path)

        payload = {
            "model": model,
            "prompt": prompt,
            "images": [image_b64],
            "stream": stream,
        }

        try:
            response = self._client.post(
                f"{self.base_url}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            return OllamaVisionResult(
                text=data.get("response", ""),
                model=data.get("model", model),
                total_duration=data.get("total_duration"),
                eval_count=data.get("eval_count"),
            )

        except httpx.HTTPError as e:
            logger.error(f"Ollama API error: {e}")
            raise

    def analyze_image_base64(
        self,
        image_base64: str,
        prompt: str,
        model: str = DEFAULT_VISION_MODEL,
    ) -> OllamaVisionResult:
        """Analyze a base64-encoded image."""
        payload = {
            "model": model,
            "prompt": prompt,
            "images": [image_base64],
            "stream": False,
        }

        try:
            response = self._client.post(
                f"{self.base_url}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            return OllamaVisionResult(
                text=data.get("response", ""),
                model=data.get("model", model),
                total_duration=data.get("total_duration"),
                eval_count=data.get("eval_count"),
            )

        except httpx.HTTPError as e:
            logger.error(f"Ollama API error: {e}")
            raise

    def batch_analyze(
        self,
        image_paths: list[str | Path],
        prompt: str,
        model: str = DEFAULT_VISION_MODEL,
    ) -> list[OllamaVisionResult]:
        """Analyze multiple images with the same prompt.

        Useful for LoRA dataset preparation - batch caption generation.
        """
        results = []
        for path in image_paths:
            try:
                result = self.analyze_image(path, prompt, model)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to analyze {path}: {e}")
                results.append(OllamaVisionResult(
                    text=f"Error: {str(e)}",
                    model=model,
                ))
        return results

    def generate_lora_caption(
        self,
        image_path: str | Path,
        trigger_word: str = "",
        style: str = "detailed",
        model: str = DEFAULT_VISION_MODEL,
    ) -> OllamaVisionResult:
        """Generate a caption suitable for LoRA training.

        Args:
            image_path: Path to the image
            trigger_word: Trigger word to prepend (e.g., "sks person")
            style: Caption style - "detailed", "tags", "booru"
            model: Vision model to use

        Returns:
            Caption formatted for LoRA training
        """
        prompts = {
            "detailed": (
                "Describe this image in detail for AI training. "
                "Include: subject, pose, expression, clothing, background, "
                "lighting, camera angle, and style. Be specific and descriptive."
            ),
            "tags": (
                "Generate comma-separated tags for this image. "
                "Include: subject type, clothing, pose, expression, background, "
                "colors, style, quality descriptors. Format as: tag1, tag2, tag3"
            ),
            "booru": (
                "Generate booru-style tags for this image. "
                "Use underscores for multi-word tags. Include quality tags. "
                "Format: 1girl, long_hair, blue_eyes, standing, outdoors, etc."
            ),
        }

        prompt = prompts.get(style, prompts["detailed"])
        result = self.analyze_image(image_path, prompt, model)

        # Prepend trigger word if provided
        if trigger_word:
            result.text = f"{trigger_word}, {result.text}"

        return result

    def is_available(self) -> bool:
        """Check if Ollama server is running and vision model is available."""
        try:
            response = self._client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            models = response.json().get("models", [])
            return any("vision" in m.get("name", "").lower() for m in models)
        except Exception:
            return False


# Singleton instance
ollama_vision_service = OllamaVisionService()
