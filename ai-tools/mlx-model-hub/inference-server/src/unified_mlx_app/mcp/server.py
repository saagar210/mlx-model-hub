"""MCP Server implementation for Unified MLX App.

Implements the Model Context Protocol for Claude Desktop/Code integration.
Supports both HTTP (FastAPI) and stdio modes.
"""

import logging
import os
import tempfile
import wave
from pathlib import Path
from typing import Any

import numpy as np

from ..config import settings
from ..models import model_manager
from .tools import TOOLS

logger = logging.getLogger(__name__)

# Allowed file extensions for security
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac"}


def validate_file_path(
    file_path: str, allowed_extensions: set[str] | None = None
) -> Path:
    """Validate and sanitize file paths to prevent directory traversal.

    Args:
        file_path: The file path to validate
        allowed_extensions: Set of allowed file extensions

    Returns:
        Resolved absolute Path object

    Raises:
        ValueError: If path is invalid or unsafe
    """
    if not file_path or not isinstance(file_path, str):
        raise ValueError("File path is required and must be a string")

    try:
        # Convert to Path and resolve to absolute path
        path = Path(file_path).resolve()

        # Check if file exists
        if not path.exists():
            raise ValueError(f"File not found: {file_path}")

        # Check if it's a file (not directory)
        if not path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")

        # Check extension if provided
        if allowed_extensions and path.suffix.lower() not in allowed_extensions:
            raise ValueError(
                f"Invalid file type '{path.suffix}'. Allowed: {allowed_extensions}"
            )

        return path
    except (OSError, RuntimeError) as e:
        raise ValueError(f"Invalid file path: {e}")


class MCPServer:
    """MCP Server that exposes MLX models as tools."""

    def __init__(self):
        self.tools = TOOLS

    def list_tools(self) -> list[dict]:
        """Return list of available tools."""
        return self.tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool and return the result."""
        handlers = {
            "generate_text": self._generate_text,
            "analyze_image": self._analyze_image,
            "speak_text": self._speak_text,
            "transcribe_audio": self._transcribe_audio,
            "get_model_status": self._get_model_status,
        }

        handler = handlers.get(name)
        if not handler:
            return {"error": f"Unknown tool: {name}"}

        try:
            result = await handler(arguments)
            return {"content": [{"type": "text", "text": str(result)}]}
        except Exception as e:
            logger.error(f"Tool {name} failed: {e}")
            return {"error": str(e), "isError": True}

    async def _generate_text(self, args: dict) -> str:
        """Generate text using mlx-lm."""
        from mlx_lm import generate
        from mlx_lm.generate import make_sampler

        prompt = args.get("prompt", "")
        system_prompt = args.get("system_prompt", "You are a helpful assistant.")
        max_tokens = args.get("max_tokens", 1024)
        temperature = args.get("temperature", 0.7)

        # Validate inputs
        if not prompt or not isinstance(prompt, str):
            return "Error: prompt is required and must be a string"
        if len(prompt) > 10000:
            return "Error: prompt exceeds maximum length of 10000 characters"
        if not isinstance(max_tokens, int) or max_tokens < 1 or max_tokens > 8192:
            return "Error: max_tokens must be between 1 and 8192"
        if not isinstance(temperature, (int, float)) or temperature < 0 or temperature > 2:
            return "Error: temperature must be between 0 and 2"

        model, tokenizer = model_manager.get_text_model()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        formatted_prompt = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        sampler = make_sampler(temp=temperature)
        result = generate(
            model,
            tokenizer,
            prompt=formatted_prompt,
            max_tokens=max_tokens,
            sampler=sampler,
            verbose=False,
        )

        return result.text if hasattr(result, "text") else str(result)

    async def _analyze_image(self, args: dict) -> str:
        """Analyze image using mlx-vlm."""
        from mlx_vlm import generate
        from mlx_vlm.prompt_utils import apply_chat_template
        from mlx_vlm.utils import load_config

        image_path = args.get("image_path", "")
        prompt = args.get("prompt", "Describe this image in detail.")
        max_tokens = args.get("max_tokens", 512)

        # Validate and sanitize the image path
        try:
            validated_path = validate_file_path(image_path, ALLOWED_IMAGE_EXTENSIONS)
        except ValueError as e:
            return f"Error: {e}"

        model, processor = model_manager.get_vision_model()
        config = load_config(settings.vision_model)

        formatted_prompt = apply_chat_template(
            processor, config, prompt, num_images=1
        )

        result = generate(
            model,
            processor,
            formatted_prompt,
            [str(validated_path)],
            max_tokens=max_tokens,
            verbose=False,
        )

        return result.text if hasattr(result, "text") else str(result)

    async def _speak_text(self, args: dict) -> str:
        """Convert text to speech using mlx-audio."""
        text = args.get("text", "")
        voice = args.get("voice", "a")
        speed = args.get("speed", 1.0)
        output_path = args.get("output_path")

        # Validate text input
        if not text or not isinstance(text, str):
            return "Error: text is required and must be a string"
        if len(text) > 5000:
            return "Error: text exceeds maximum length of 5000 characters"

        # Validate voice
        if voice not in ["a", "b"]:
            return "Error: voice must be 'a' (American) or 'b' (British)"

        # Validate speed
        if not isinstance(speed, (int, float)) or speed < 0.5 or speed > 2.0:
            return "Error: speed must be between 0.5 and 2.0"

        # Handle output path securely
        if output_path:
            # Only allow writing to temp directory for security
            try:
                requested_path = Path(output_path).resolve()
                temp_dir = Path(tempfile.gettempdir()).resolve()
                if not str(requested_path).startswith(str(temp_dir)):
                    return "Error: output_path must be in temporary directory for security"
                final_output_path = str(requested_path)
            except Exception as e:
                return f"Error: Invalid output path - {e}"
        else:
            temp_file = tempfile.NamedTemporaryFile(
                suffix=".wav", delete=False, prefix="mlx_tts_"
            )
            final_output_path = temp_file.name
            temp_file.close()

        model = model_manager.get_speech_model()

        results = model.generate(
            text=text,
            lang_code=voice,
            speed=speed,
            verbose=False,
        )

        audio_segments = []
        for result in results:
            audio_segments.append(np.array(result.audio))

        if not audio_segments:
            return "Error: No audio generated"

        audio_array = (
            np.concatenate(audio_segments)
            if len(audio_segments) > 1
            else audio_segments[0]
        )

        sample_rate = getattr(model, "sample_rate", 24000)
        with wave.open(final_output_path, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            audio_int16 = (audio_array * 32767).astype(np.int16)
            wav_file.writeframes(audio_int16.tobytes())

        return f"Audio saved to: {final_output_path}"

    async def _transcribe_audio(self, args: dict) -> str:
        """Transcribe audio using mlx-audio Whisper."""
        audio_path = args.get("audio_path", "")

        # Validate and sanitize the audio path
        try:
            validated_path = validate_file_path(audio_path, ALLOWED_AUDIO_EXTENSIONS)
        except ValueError as e:
            return f"Error: {e}"

        model = model_manager.get_stt_model()
        result = model.generate(str(validated_path), verbose=False)

        return result.text

    async def _get_model_status(self, args: dict) -> str:
        """Get status of loaded models."""
        import psutil

        status = model_manager.get_status()
        process = psutil.Process()
        mem_info = process.memory_info()

        output = ["=== Unified MLX Model Status ===", ""]
        output.append(f"Memory Usage: {mem_info.rss / (1024**3):.2f} GB")
        output.append("")

        for model_type, info in status.items():
            if info.get("loaded"):
                output.append(f"{model_type.upper()}: Loaded ({info.get('model_path', 'unknown')})")
            else:
                loading = "Loading..." if info.get("loading") else "Not loaded"
                output.append(f"{model_type.upper()}: {loading}")

        return "\n".join(output)


# Global MCP server instance
mcp_server = MCPServer()
