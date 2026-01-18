"""Audio processing with Whisper transcription and speaker diarization."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TranscriptionModel(str, Enum):
    """Available Whisper model sizes."""

    TINY = "tiny"
    BASE = "base"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    LARGE_V2 = "large-v2"
    LARGE_V3 = "large-v3"


@dataclass
class TranscriptionSegment:
    """A segment of transcribed audio."""

    start: float  # Start time in seconds
    end: float  # End time in seconds
    text: str
    confidence: float = 0.0
    speaker: str | None = None  # For diarization
    words: list[dict[str, Any]] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.end - self.start

    def format_timestamp(self, time: float) -> str:
        """Format time as HH:MM:SS."""
        hours = int(time // 3600)
        minutes = int((time % 3600) // 60)
        seconds = int(time % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    @property
    def start_timestamp(self) -> str:
        return self.format_timestamp(self.start)

    @property
    def end_timestamp(self) -> str:
        return self.format_timestamp(self.end)


@dataclass
class TranscriptionResult:
    """Result of audio transcription."""

    full_text: str
    segments: list[TranscriptionSegment]
    language: str
    language_probability: float
    duration_seconds: float
    processing_time_ms: float
    model_used: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def word_count(self) -> int:
        return len(self.full_text.split())

    def to_srt(self) -> str:
        """Convert to SRT subtitle format."""
        lines = []
        for i, seg in enumerate(self.segments, 1):
            start_ts = self._format_srt_time(seg.start)
            end_ts = self._format_srt_time(seg.end)
            lines.append(f"{i}")
            lines.append(f"{start_ts} --> {end_ts}")
            lines.append(seg.text.strip())
            lines.append("")
        return "\n".join(lines)

    def to_vtt(self) -> str:
        """Convert to WebVTT subtitle format."""
        lines = ["WEBVTT", ""]
        for i, seg in enumerate(self.segments, 1):
            start_ts = self._format_vtt_time(seg.start)
            end_ts = self._format_vtt_time(seg.end)
            lines.append(f"{i}")
            lines.append(f"{start_ts} --> {end_ts}")
            lines.append(seg.text.strip())
            lines.append("")
        return "\n".join(lines)

    def to_timestamped_text(self) -> str:
        """Convert to timestamped text format."""
        lines = []
        for seg in self.segments:
            timestamp = seg.start_timestamp
            speaker = f"[{seg.speaker}] " if seg.speaker else ""
            lines.append(f"[{timestamp}] {speaker}{seg.text.strip()}")
        return "\n".join(lines)

    def _format_srt_time(self, seconds: float) -> str:
        """Format time for SRT (HH:MM:SS,mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def _format_vtt_time(self, seconds: float) -> str:
        """Format time for VTT (HH:MM:SS.mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

    def iter_chunks(
        self,
        max_duration: float = 60.0,
        max_chars: int = 1000,
    ) -> Iterator[tuple[str, dict[str, Any]]]:
        """
        Iterate over chunks suitable for embedding.

        Args:
            max_duration: Maximum duration per chunk in seconds
            max_chars: Maximum characters per chunk

        Yields:
            Tuples of (chunk_text, metadata)
        """
        current_text = []
        current_start = None
        current_end = 0.0
        current_chars = 0

        for seg in self.segments:
            if current_start is None:
                current_start = seg.start

            # Check if we need to start a new chunk
            duration = seg.end - current_start
            new_chars = current_chars + len(seg.text)

            if duration > max_duration or new_chars > max_chars:
                if current_text:
                    yield (
                        " ".join(current_text),
                        {
                            "start_time": current_start,
                            "end_time": current_end,
                            "duration": current_end - current_start,
                        },
                    )
                current_text = [seg.text]
                current_start = seg.start
                current_chars = len(seg.text)
            else:
                current_text.append(seg.text)
                current_chars = new_chars

            current_end = seg.end

        # Yield remaining text
        if current_text and current_start is not None:
            yield (
                " ".join(current_text),
                {
                    "start_time": current_start,
                    "end_time": current_end,
                    "duration": current_end - current_start,
                },
            )


class AudioProcessor:
    """Process audio files for transcription and analysis."""

    def __init__(
        self,
        model: str | TranscriptionModel = TranscriptionModel.BASE,
        device: str = "auto",
        compute_type: str = "auto",
        language: str | None = None,
    ):
        """
        Initialize audio processor.

        Args:
            model: Whisper model size or custom model name
            device: Device to use (auto, cpu, cuda, mps)
            compute_type: Compute type (auto, float16, float32, int8)
            language: Language code (None for auto-detect)
        """
        self.model_name = model.value if isinstance(model, TranscriptionModel) else model
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self._model = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy initialization of transcription model."""
        if self._initialized:
            return

        # Try faster-whisper first (CTranslate2 backend)
        try:
            from faster_whisper import WhisperModel

            device = self.device
            if device == "auto":
                import torch

                device = "cuda" if torch.cuda.is_available() else "cpu"
                if device == "cpu" and hasattr(torch.backends, "mps"):
                    if torch.backends.mps.is_available():
                        device = "cpu"  # faster-whisper doesn't support MPS directly

            compute_type = self.compute_type
            if compute_type == "auto":
                compute_type = "float16" if device == "cuda" else "float32"

            self._model = WhisperModel(
                self.model_name,
                device=device,
                compute_type=compute_type,
            )
            self._backend = "faster-whisper"
            logger.info(f"Initialized faster-whisper with {self.model_name} on {device}")

        except ImportError:
            # Fallback to openai-whisper
            try:
                import whisper

                self._model = whisper.load_model(self.model_name)
                self._backend = "openai-whisper"
                logger.info(f"Initialized openai-whisper with {self.model_name}")
            except ImportError:
                logger.error(
                    "No Whisper library available. Install with: "
                    "pip install faster-whisper or pip install openai-whisper"
                )
                raise

        self._initialized = True

    async def transcribe_file(
        self,
        file_path: str | Path,
        word_timestamps: bool = True,
        vad_filter: bool = True,
    ) -> TranscriptionResult:
        """
        Transcribe an audio file.

        Args:
            file_path: Path to audio file
            word_timestamps: Whether to include word-level timestamps
            vad_filter: Whether to use VAD for better segment detection

        Returns:
            TranscriptionResult with transcription and segments
        """
        import time

        start_time = time.time()
        self._ensure_initialized()

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {path}")

        if self._backend == "faster-whisper":
            result = await self._transcribe_faster_whisper(
                str(path), word_timestamps, vad_filter
            )
        else:
            result = await self._transcribe_openai_whisper(str(path), word_timestamps)

        result.processing_time_ms = (time.time() - start_time) * 1000
        result.model_used = self.model_name
        return result

    async def transcribe_bytes(
        self,
        audio_data: bytes,
        format: str = "wav",
        word_timestamps: bool = True,
    ) -> TranscriptionResult:
        """Transcribe audio from bytes."""
        import tempfile
        from pathlib import Path

        # Write to temp file
        with tempfile.NamedTemporaryFile(
            suffix=f".{format}", delete=False
        ) as f:
            f.write(audio_data)
            temp_path = f.name

        try:
            result = await self.transcribe_file(temp_path, word_timestamps)
            return result
        finally:
            Path(temp_path).unlink(missing_ok=True)

    async def _transcribe_faster_whisper(
        self,
        file_path: str,
        word_timestamps: bool,
        vad_filter: bool,
    ) -> TranscriptionResult:
        """Transcribe using faster-whisper."""
        segments_iter, info = self._model.transcribe(
            file_path,
            language=self.language,
            word_timestamps=word_timestamps,
            vad_filter=vad_filter,
        )

        segments = []
        full_text_parts = []

        for seg in segments_iter:
            segment = TranscriptionSegment(
                start=seg.start,
                end=seg.end,
                text=seg.text,
                confidence=seg.avg_logprob if hasattr(seg, "avg_logprob") else 0.0,
            )

            if word_timestamps and hasattr(seg, "words") and seg.words:
                segment.words = [
                    {
                        "word": w.word,
                        "start": w.start,
                        "end": w.end,
                        "probability": w.probability,
                    }
                    for w in seg.words
                ]

            segments.append(segment)
            full_text_parts.append(seg.text)

        return TranscriptionResult(
            full_text=" ".join(full_text_parts),
            segments=segments,
            language=info.language,
            language_probability=info.language_probability,
            duration_seconds=info.duration,
            processing_time_ms=0.0,  # Set by caller
            model_used=self.model_name,
        )

    async def _transcribe_openai_whisper(
        self,
        file_path: str,
        word_timestamps: bool,
    ) -> TranscriptionResult:
        """Transcribe using openai-whisper."""
        options = {"language": self.language} if self.language else {}

        result = self._model.transcribe(
            file_path,
            word_timestamps=word_timestamps,
            **options,
        )

        segments = []
        for seg in result.get("segments", []):
            segment = TranscriptionSegment(
                start=seg["start"],
                end=seg["end"],
                text=seg["text"],
            )

            if word_timestamps and "words" in seg:
                segment.words = seg["words"]

            segments.append(segment)

        # Get duration from last segment
        duration = segments[-1].end if segments else 0.0

        return TranscriptionResult(
            full_text=result.get("text", ""),
            segments=segments,
            language=result.get("language", "en"),
            language_probability=0.0,  # Not available in openai-whisper
            duration_seconds=duration,
            processing_time_ms=0.0,  # Set by caller
            model_used=self.model_name,
        )

    def get_audio_duration(self, file_path: str | Path) -> float:
        """Get duration of audio file in seconds."""
        try:
            import librosa

            duration = librosa.get_duration(path=str(file_path))
            return duration
        except ImportError:
            try:
                from pydub import AudioSegment

                audio = AudioSegment.from_file(str(file_path))
                return audio.duration_seconds
            except ImportError:
                logger.warning("No audio library available for duration check")
                return 0.0

    def extract_audio_from_video(
        self,
        video_path: str | Path,
        output_path: str | Path | None = None,
        format: str = "wav",
    ) -> Path:
        """
        Extract audio track from video file.

        Args:
            video_path: Path to video file
            output_path: Output path for audio (auto-generated if None)
            format: Output audio format

        Returns:
            Path to extracted audio file
        """
        import subprocess
        import tempfile

        video_path = Path(video_path)
        if output_path is None:
            output_path = Path(tempfile.mktemp(suffix=f".{format}"))
        else:
            output_path = Path(output_path)

        # Use ffmpeg for extraction
        cmd = [
            "ffmpeg",
            "-i",
            str(video_path),
            "-vn",  # No video
            "-acodec",
            "pcm_s16le" if format == "wav" else "libmp3lame",
            "-ar",
            "16000",  # 16kHz sample rate (good for Whisper)
            "-ac",
            "1",  # Mono
            "-y",  # Overwrite
            str(output_path),
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg extraction failed: {e.stderr.decode()}")
            raise
        except FileNotFoundError as err:
            raise RuntimeError(
                "FFmpeg not found. Install with: brew install ffmpeg (macOS) "
                "or apt install ffmpeg (Linux)"
            ) from err
