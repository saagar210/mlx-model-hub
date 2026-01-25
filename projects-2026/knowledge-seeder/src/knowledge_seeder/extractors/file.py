"""Local file content extractor."""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path

from knowledge_seeder.config import get_settings
from knowledge_seeder.extractors.base import BaseExtractor, ExtractionResult
from knowledge_seeder.models import SourceType

logger = logging.getLogger(__name__)

# Supported file extensions
TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".rst",
    ".text",
}

CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".sh",
    ".bash",
    ".zsh",
    ".fish",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".scala",
    ".rb",
    ".php",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".swift",
    ".m",
    ".mm",
    ".r",
    ".R",
    ".sql",
    ".graphql",
    ".css",
    ".scss",
    ".sass",
    ".less",
    ".html",
    ".htm",
    ".xml",
    ".svg",
}

ALL_SUPPORTED = TEXT_EXTENSIONS | CODE_EXTENSIONS


class FileExtractor(BaseExtractor):
    """Extract content from local files."""

    def __init__(self) -> None:
        """Initialize file extractor."""
        settings = get_settings()
        self._max_length = settings.max_content_length

    def can_handle(self, path: str) -> bool:
        """Check if this is a local file path we can handle."""
        # Expand user home directory
        if path.startswith("~"):
            path = str(Path(path).expanduser())

        # Check if it looks like a file path
        if not (path.startswith("/") or path.startswith(".")):
            return False

        # Check extension
        file_path = Path(path)
        return file_path.suffix.lower() in ALL_SUPPORTED

    async def extract(self, path: str) -> ExtractionResult:
        """Extract content from a local file."""
        # Expand path
        file_path = Path(path).expanduser().resolve()

        if not file_path.exists():
            raise ValueError(f"File not found: {file_path}")

        if not file_path.is_file():
            raise ValueError(f"Not a file: {file_path}")

        if file_path.suffix.lower() not in ALL_SUPPORTED:
            raise ValueError(f"Unsupported file type: {file_path.suffix}")

        logger.info("Reading file: %s", file_path)

        # Read file content
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Try with fallback encoding
            try:
                content = file_path.read_text(encoding="latin-1")
            except Exception as e:
                raise ValueError(f"Failed to read file: {e}") from e

        # Truncate if too long
        if len(content) > self._max_length:
            content = content[: self._max_length]
            logger.warning("Content truncated to %d chars for %s", self._max_length, file_path)

        # Determine content type
        extension = file_path.suffix.lower()
        is_code = extension in CODE_EXTENSIONS

        # Build metadata
        metadata = {
            "filename": file_path.name,
            "extension": extension,
            "size_bytes": file_path.stat().st_size,
            "is_code": is_code,
            "mime_type": mimetypes.guess_type(str(file_path))[0],
        }

        return ExtractionResult(
            content=content,
            title=file_path.stem,  # Use filename without extension as title
            source_url=str(file_path),
            source_type=SourceType.FILE,
            metadata=metadata,
        )

    async def check_accessible(self, path: str) -> tuple[bool, str | None]:
        """Check if file exists and is readable."""
        file_path = Path(path).expanduser().resolve()

        if not file_path.exists():
            return False, "File not found"

        if not file_path.is_file():
            return False, "Not a file"

        if file_path.suffix.lower() not in ALL_SUPPORTED:
            return False, f"Unsupported file type: {file_path.suffix}"

        # Try to read a small portion to verify access
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                f.read(100)
            return True, None
        except PermissionError:
            return False, "Permission denied"
        except Exception as e:
            return False, str(e)
