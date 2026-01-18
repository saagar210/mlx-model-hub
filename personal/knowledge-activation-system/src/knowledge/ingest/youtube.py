"""YouTube video ingestion."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from youtube_transcript_api import YouTubeTranscriptApi

from knowledge.chunking import ChunkingStrategy, chunk_content
from knowledge.config import Settings, get_settings
from knowledge.db import get_db
from knowledge.embeddings import embed_batch
from knowledge.ingest import IngestResult
from knowledge.obsidian import create_note, get_relative_path
from knowledge.validation import validate_content


@dataclass
class YouTubeVideo:
    """YouTube video metadata and transcript."""

    video_id: str
    title: str
    channel: str | None = None
    duration: int | None = None  # seconds
    transcript: str = ""
    language: str = "en"
    published_at: datetime | None = None


def extract_video_id(url_or_id: str) -> str | None:
    """
    Extract video ID from YouTube URL or return ID if already valid.

    Handles:
    - youtube.com/watch?v=VIDEO_ID
    - youtu.be/VIDEO_ID
    - youtube.com/embed/VIDEO_ID
    - Just VIDEO_ID

    Args:
        url_or_id: URL or video ID

    Returns:
        Video ID or None if invalid
    """
    # Check if already a video ID (11 chars, alphanumeric with - and _)
    if re.match(r"^[a-zA-Z0-9_-]{11}$", url_or_id):
        return url_or_id

    # Try to extract from URL
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
        r"(?:youtube\.com/v/)([a-zA-Z0-9_-]{11})",
    ]

    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)

    return None


def get_youtube_url(video_id: str) -> str:
    """Get full YouTube URL from video ID."""
    return f"https://www.youtube.com/watch?v={video_id}"


async def fetch_transcript(
    video_id: str,
    languages: list[str] | None = None,
) -> tuple[str, str]:
    """
    Fetch transcript from YouTube.

    Args:
        video_id: YouTube video ID
        languages: Preferred languages (default: ["en"])

    Returns:
        Tuple of (transcript_text, language_code)

    Raises:
        ValueError: If transcript unavailable
    """
    languages = languages or ["en"]

    try:
        ytt_api = YouTubeTranscriptApi()
        transcript_list = ytt_api.list(video_id)

        # Try to get transcript in preferred language
        transcript = None
        try:
            transcript = transcript_list.find_transcript(languages)
        except Exception:
            pass

        # Fall back to generated transcript
        if transcript is None:
            try:
                transcript = transcript_list.find_generated_transcript(languages)
            except Exception:
                pass

        # Fall back to any available transcript
        if transcript is None:
            for t in transcript_list:
                transcript = t
                break

        if transcript is None:
            raise ValueError(f"No transcript available for video {video_id}")

        # Fetch transcript data
        transcript_data = transcript.fetch()

        # Format with timestamps
        formatted_lines = []
        for entry in transcript_data:
            # Handle both dict-style and object-style access
            start = entry.start if hasattr(entry, "start") else entry["start"]  # type: ignore[index]
            text = entry.text if hasattr(entry, "text") else entry["text"]  # type: ignore[index]
            timestamp = format_timestamp(start)
            text = text.strip()
            if text:
                formatted_lines.append(f"[{timestamp}] {text}")

        transcript_text = "\n".join(formatted_lines)
        return transcript_text, transcript.language_code

    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Failed to fetch transcript: {e}") from e


def format_timestamp(seconds: float) -> str:
    """Format seconds as MM:SS or HH:MM:SS."""
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def estimate_duration_from_transcript(transcript: str) -> int | None:
    """
    Estimate video duration from last timestamp in transcript.

    Args:
        transcript: Transcript with timestamps

    Returns:
        Estimated duration in seconds or None
    """
    # Find all timestamps
    timestamps = re.findall(r"\[(\d+:\d{2}(?::\d{2})?)\]", transcript)
    if not timestamps:
        return None

    # Parse last timestamp
    last = timestamps[-1]
    parts = last.split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    elif len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    return None


async def ingest_youtube(
    url_or_id: str,
    title: str | None = None,
    tags: list[str] | None = None,
    settings: Settings | None = None,
) -> IngestResult:
    """
    Ingest a YouTube video.

    1. Extract video ID
    2. Fetch transcript (with timestamps)
    3. Validate content
    4. Chunk by timestamps
    5. Generate embeddings
    6. Create Obsidian note
    7. Store in database

    Args:
        url_or_id: YouTube URL or video ID
        title: Optional title override
        tags: Optional tags
        settings: Optional settings override

    Returns:
        IngestResult with success/failure info
    """
    settings = settings or get_settings()

    # Extract video ID
    video_id = extract_video_id(url_or_id)
    if not video_id:
        return IngestResult(
            success=False,
            error=f"Invalid YouTube URL or video ID: {url_or_id}",
        )

    url = get_youtube_url(video_id)

    try:
        # Fetch transcript
        transcript, language = await fetch_transcript(video_id)

        # Validate content
        validation = validate_content(transcript, min_length=100)
        if not validation.valid:
            return IngestResult(
                success=False,
                error=f"Content validation failed: {validation.error.value if validation.error else 'Unknown'}",
            )

        # Use provided title or generate from video ID
        final_title = title or f"YouTube Video {video_id}"

        # Estimate duration
        duration = estimate_duration_from_transcript(transcript)

        # Chunk transcript
        chunks = chunk_content(transcript, strategy=ChunkingStrategy.YOUTUBE)

        if not chunks:
            return IngestResult(
                success=False,
                error="No chunks generated from transcript",
            )

        # Generate embeddings for all chunks
        chunk_texts = [chunk.text for chunk in chunks]
        embeddings = await embed_batch(chunk_texts)

        # Create Obsidian note
        metadata: dict[str, str | int] = {
            "video_id": video_id,
            "language": language,
        }
        if duration:
            metadata["duration"] = duration

        note_path = create_note(
            content_type="youtube",
            title=final_title,
            content=transcript,
            url=url,
            tags=tags,
            metadata=metadata,
            settings=settings,
        )

        # Store in database
        db = await get_db()
        relative_path = get_relative_path(note_path, settings)

        # Check if already exists
        if await db.content_exists(relative_path):
            return IngestResult(
                success=False,
                error=f"Content already exists: {relative_path}",
            )

        # Insert content
        content_id = await db.insert_content(
            filepath=relative_path,
            content_type="youtube",
            title=final_title,
            content_for_hash=transcript,
            url=url,
            tags=tags,
            metadata=metadata,
        )

        # Insert chunks with embeddings
        chunk_records = [
            {
                "chunk_index": chunk.index,
                "chunk_text": chunk.text,
                "embedding": embeddings[i],
                "source_ref": chunk.source_ref,
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
            }
            for i, chunk in enumerate(chunks)
        ]
        await db.insert_chunks(content_id, chunk_records)

        return IngestResult(
            success=True,
            content_id=content_id,
            filepath=note_path,
            title=final_title,
            chunks_created=len(chunks),
        )

    except ValueError as e:
        return IngestResult(
            success=False,
            error=str(e),
        )
    except Exception as e:
        return IngestResult(
            success=False,
            error=f"Unexpected error: {e}",
        )


async def ingest_youtube_batch(
    video_ids: list[str],
    tags: list[str] | None = None,
    settings: Settings | None = None,
) -> list[IngestResult]:
    """
    Ingest multiple YouTube videos.

    Args:
        video_ids: List of video IDs or URLs
        tags: Optional tags to apply to all
        settings: Optional settings override

    Returns:
        List of IngestResult for each video
    """
    results = []
    for video_id in video_ids:
        result = await ingest_youtube(video_id, tags=tags, settings=settings)
        results.append(result)
    return results
