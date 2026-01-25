"""YouTube transcript extractor."""

from __future__ import annotations

import logging
import re
from typing import Any

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from knowledge_seeder.extractors.base import BaseExtractor, ExtractionResult
from knowledge_seeder.models import SourceType

logger = logging.getLogger(__name__)

# YouTube URL patterns to extract video ID
YOUTUBE_PATTERNS = [
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})"),
    re.compile(r"(?:https?://)?youtu\.be/([a-zA-Z0-9_-]{11})"),
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})"),
    re.compile(r"^([a-zA-Z0-9_-]{11})$"),  # Just the video ID
]


class YouTubeExtractor(BaseExtractor):
    """Extract transcripts from YouTube videos."""

    def can_handle(self, url: str) -> bool:
        """Check if this is a YouTube URL or video ID."""
        return self._extract_video_id(url) is not None

    def _extract_video_id(self, url: str) -> str | None:
        """Extract video ID from URL."""
        for pattern in YOUTUBE_PATTERNS:
            match = pattern.search(url)
            if match:
                return match.group(1)
        return None

    async def extract(self, url: str) -> ExtractionResult:
        """Extract transcript from YouTube video."""
        video_id = self._extract_video_id(url)
        if not video_id:
            raise ValueError(f"Could not extract video ID from: {url}")

        logger.info("Fetching transcript for video: %s", video_id)

        try:
            # New API (v1.x) uses instance methods
            api = YouTubeTranscriptApi()
            transcript = api.fetch(video_id, languages=["en", "en-US", "en-GB"])

            # Convert FetchedTranscript to list of dicts for formatting
            transcript_data = [
                {"text": snippet.text, "start": snippet.start, "duration": snippet.duration}
                for snippet in transcript
            ]

            # Format transcript with timestamps
            content = self._format_transcript(transcript_data)

            # Build metadata
            metadata = {
                "video_id": video_id,
                "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
                "language": "en",
            }

            return ExtractionResult(
                content=content,
                title=None,  # Would need YouTube API for title
                source_url=url,
                source_type=SourceType.YOUTUBE,
                metadata=metadata,
            )

        except VideoUnavailable:
            raise ValueError(f"Video unavailable: {video_id}")
        except TranscriptsDisabled:
            raise ValueError(f"Transcripts disabled for video: {video_id}")
        except NoTranscriptFound:
            raise ValueError(f"No transcript found for video: {video_id}")
        except Exception as e:
            logger.error("Error extracting transcript for %s: %s", video_id, e)
            raise ValueError(f"Failed to extract transcript: {e}") from e

    def _format_transcript(self, transcript_data: list[dict[str, Any]]) -> str:
        """Format transcript data into readable text with timestamps."""
        lines = []
        current_minute = -1

        for entry in transcript_data:
            # Get timestamp in minutes
            start_time = entry.get("start", 0)
            minute = int(start_time // 60)

            # Add minute marker if new minute
            if minute > current_minute:
                if lines:
                    lines.append("")  # Blank line between sections
                lines.append(f"[{minute:02d}:00]")
                current_minute = minute

            # Add text
            text = entry.get("text", "").strip()
            if text:
                lines.append(text)

        return "\n".join(lines)

    async def check_accessible(self, url: str) -> tuple[bool, str | None]:
        """Check if video has accessible transcript."""
        video_id = self._extract_video_id(url)
        if not video_id:
            return False, "Invalid YouTube URL"

        try:
            # New API (v1.x) uses instance methods
            api = YouTubeTranscriptApi()
            api.fetch(video_id, languages=["en", "en-US", "en-GB"])
            return True, None
        except VideoUnavailable:
            return False, "Video unavailable"
        except TranscriptsDisabled:
            return False, "Transcripts disabled"
        except NoTranscriptFound:
            return False, "No English transcript available"
        except Exception as e:
            return False, str(e)
