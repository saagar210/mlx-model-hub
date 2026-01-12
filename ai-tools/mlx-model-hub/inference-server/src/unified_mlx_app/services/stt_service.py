"""Speech-to-text service."""

import logging
import os
import tempfile
from dataclasses import dataclass

from ..models import model_manager

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionResult:
    """Result from STT transcription."""
    text: str
    language: str | None = None
    duration_seconds: float | None = None


class STTService:
    """Service for speech-to-text using MLX Audio models."""

    def __init__(self):
        self._model = None

    def _ensure_model(self, model_path: str, force_reload: bool = False):
        """Ensure STT model is loaded."""
        self._model = model_manager.get_stt_model(model_path, force_reload=force_reload)

    def transcribe_file(
        self,
        file_path: str,
        model_path: str,
    ) -> TranscriptionResult:
        """Transcribe audio from a file path."""
        self._ensure_model(model_path)

        result = self._model.generate(file_path, verbose=False)

        return TranscriptionResult(
            text=result.text,
            language=getattr(result, "language", None),
            duration_seconds=getattr(result, "duration", None),
        )

    def transcribe_bytes(
        self,
        audio_data: bytes,
        model_path: str,
        file_suffix: str = ".wav",
    ) -> TranscriptionResult:
        """Transcribe audio from bytes."""
        # Save to temp file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_suffix)
        try:
            temp_file.write(audio_data)
            temp_file.close()

            return self.transcribe_file(temp_file.name, model_path)
        finally:
            # Clean up temp file
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)


# Singleton instance
stt_service = STTService()
