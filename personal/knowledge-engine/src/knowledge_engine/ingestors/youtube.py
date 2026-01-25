"""YouTube transcript ingestor."""

from __future__ import annotations

import logging
import re
from typing import Any

from youtube_transcript_api import YouTubeTranscriptApi

from knowledge_engine.ingestors.base import BaseIngestor, IngestResult

logger = logging.getLogger(__name__)

# Pattern to extract video ID from various YouTube URL formats
YOUTUBE_PATTERNS = [
    r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
    r'^([a-zA-Z0-9_-]{11})$',  # Direct video ID
]


class YouTubeIngestor(BaseIngestor):
    """
    Ingest transcripts from YouTube videos.

    Supports:
    - Full YouTube URLs (youtube.com/watch?v=...)
    - Short URLs (youtu.be/...)
    - Embed URLs (youtube.com/embed/...)
    - Direct video IDs

    Falls back to auto-generated captions if manual transcripts unavailable.
    """

    def __init__(self, preferred_languages: list[str] | None = None) -> None:
        """
        Initialize YouTube ingestor.

        Args:
            preferred_languages: Preferred transcript languages (default: ["en"])
        """
        self._preferred_languages = preferred_languages or ["en"]
        self._api = YouTubeTranscriptApi()

    def _extract_video_id(self, source: str) -> str | None:
        """Extract video ID from URL or direct ID."""
        for pattern in YOUTUBE_PATTERNS:
            match = re.search(pattern, source)
            if match:
                return match.group(1)
        return None

    def can_handle(self, source: str) -> bool:
        """Check if source is a valid YouTube URL or video ID."""
        return self._extract_video_id(source) is not None

    async def ingest(self, source: str) -> IngestResult:
        """
        Fetch transcript from a YouTube video.

        Tries manual transcripts first, then auto-generated.
        """
        video_id = self._extract_video_id(source)

        if not video_id:
            raise ValueError(f"Invalid YouTube URL or video ID: {source}")

        logger.info("Fetching YouTube transcript: %s", video_id)

        try:
            # Use the new API: fetch directly with language preferences
            transcript = self._api.fetch(video_id, languages=self._preferred_languages)

            # Convert to list of dicts
            entries = list(transcript)

            # Format transcript with timestamps
            content = self._format_transcript(entries)

            # Get metadata from transcript
            transcript_lang = self._preferred_languages[0]  # Assume first language worked

            # Try to get video title from metadata (not available via transcript API)
            title = f"YouTube Video: {video_id}"

            # Calculate duration
            duration = 0.0
            if entries:
                last_entry = entries[-1]
                if hasattr(last_entry, "start"):
                    duration = last_entry.start + (last_entry.duration or 0)
                else:
                    duration = last_entry.get("start", 0) + last_entry.get("duration", 0)

            return IngestResult(
                content=content,
                title=title,
                source=f"https://www.youtube.com/watch?v={video_id}",
                source_type="youtube",
                metadata={
                    "video_id": video_id,
                    "language": transcript_lang,
                    "segment_count": len(entries),
                    "duration_seconds": duration,
                }
            )

        except Exception as e:
            logger.error("Failed to fetch YouTube transcript: %s", e)
            raise ValueError(f"Failed to fetch transcript: {e}")

    def _format_transcript(self, entries: list[Any]) -> str:
        """
        Format transcript entries with timestamps.

        Groups segments into paragraphs for better readability.
        """
        if not entries:
            return ""

        paragraphs = []
        current_paragraph = []
        current_time = 0.0
        paragraph_interval = 60  # Group by minute

        for entry in entries:
            # Handle both dict and object entry types
            if hasattr(entry, "text"):
                text = entry.text.strip() if entry.text else ""
                start_time = entry.start
            else:
                text = entry.get("text", "").strip()
                start_time = entry.get("start", 0)

            if not text:
                continue

            # Start new paragraph at minute boundaries
            if start_time - current_time >= paragraph_interval and current_paragraph:
                timestamp = self._format_timestamp(current_time)
                paragraphs.append(f"[{timestamp}] {' '.join(current_paragraph)}")
                current_paragraph = []
                current_time = start_time

            if not current_paragraph:
                current_time = start_time

            current_paragraph.append(text)

        # Add final paragraph
        if current_paragraph:
            timestamp = self._format_timestamp(current_time)
            paragraphs.append(f"[{timestamp}] {' '.join(current_paragraph)}")

        return "\n\n".join(paragraphs)

    def _format_timestamp(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS or MM:SS."""
        seconds = int(seconds)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"
