"""Text-to-speech service."""

import io
import logging
import wave
from dataclasses import dataclass

import numpy as np

from ..models import model_manager

logger = logging.getLogger(__name__)


@dataclass
class TTSResult:
    """Result from TTS generation."""
    audio_data: bytes
    sample_rate: int
    duration_seconds: float


class TTSService:
    """Service for text-to-speech using MLX Audio models."""

    def __init__(self):
        self._model = None

    def _ensure_model(self, model_path: str, force_reload: bool = False):
        """Ensure TTS model is loaded."""
        self._model = model_manager.get_speech_model(model_path, force_reload=force_reload)

    def generate(
        self,
        text: str,
        model_path: str,
        voice: str = "en-us",
        speed: float = 1.0,
    ) -> TTSResult:
        """Generate speech from text."""
        self._ensure_model(model_path)

        # Generate audio segments
        results = self._model.generate(
            text=text,
            lang_code=voice,
            speed=speed,
            verbose=False,
        )

        # Collect audio from results generator
        audio_segments = []
        for result in results:
            audio_segments.append(np.array(result.audio))

        if not audio_segments:
            raise ValueError("No audio generated")

        # Concatenate all segments
        audio_array = (
            np.concatenate(audio_segments)
            if len(audio_segments) > 1
            else audio_segments[0]
        )

        # Get sample rate from model
        sample_rate = getattr(self._model, "sample_rate", 24000)

        # Convert to WAV format
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            # Convert float32 to int16
            audio_int16 = (audio_array * 32767).astype(np.int16)
            wav_file.writeframes(audio_int16.tobytes())

        buffer.seek(0)
        audio_data = buffer.read()

        # Calculate duration
        duration = len(audio_array) / sample_rate

        return TTSResult(
            audio_data=audio_data,
            sample_rate=sample_rate,
            duration_seconds=duration,
        )


# Singleton instance
tts_service = TTSService()
