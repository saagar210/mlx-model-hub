"""File content ingestor for local files."""

from __future__ import annotations

import logging
import mimetypes
import os
from pathlib import Path

from pypdf import PdfReader

from knowledge_engine.ingestors.base import BaseIngestor, IngestResult

logger = logging.getLogger(__name__)

# Supported file extensions
SUPPORTED_EXTENSIONS = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".py": "text/x-python",
    ".js": "text/javascript",
    ".ts": "text/typescript",
    ".json": "application/json",
    ".yaml": "text/yaml",
    ".yml": "text/yaml",
    ".html": "text/html",
    ".htm": "text/html",
    ".xml": "text/xml",
    ".csv": "text/csv",
    ".pdf": "application/pdf",
}


class FileIngestor(BaseIngestor):
    """
    Ingest content from local files.

    Supports:
    - Text files (.txt, .md, .py, .js, etc.)
    - PDF files (.pdf)
    """

    def __init__(self, max_file_size: int = 10 * 1024 * 1024) -> None:
        """
        Initialize file ingestor.

        Args:
            max_file_size: Maximum file size in bytes (default 10MB)
        """
        self._max_file_size = max_file_size

    def can_handle(self, source: str) -> bool:
        """Check if source is a valid file path."""
        path = Path(source)
        if not path.exists():
            return False
        if not path.is_file():
            return False
        ext = path.suffix.lower()
        return ext in SUPPORTED_EXTENSIONS

    async def ingest(self, source: str) -> IngestResult:
        """
        Read and extract content from a file.
        """
        path = Path(source)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {source}")

        if not path.is_file():
            raise ValueError(f"Not a file: {source}")

        # Check file size
        file_size = path.stat().st_size
        if file_size > self._max_file_size:
            raise ValueError(f"File too large: {file_size} bytes (max {self._max_file_size})")

        ext = path.suffix.lower()
        mime_type = SUPPORTED_EXTENSIONS.get(ext) or mimetypes.guess_type(source)[0]

        logger.info("Reading file: %s (type: %s)", source, mime_type)

        if ext == ".pdf":
            content = self._extract_pdf(path)
        else:
            content = self._extract_text(path)

        return IngestResult(
            content=content,
            title=path.stem,  # Filename without extension
            source=str(path.absolute()),
            source_type="file",
            metadata={
                "filename": path.name,
                "extension": ext,
                "mime_type": mime_type,
                "file_size": file_size,
                "modified_at": path.stat().st_mtime,
            }
        )

    def _extract_text(self, path: Path) -> str:
        """Extract content from text files."""
        encodings = ["utf-8", "utf-16", "latin-1", "cp1252"]

        for encoding in encodings:
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue

        # Last resort: read as bytes and decode with errors='replace'
        return path.read_bytes().decode("utf-8", errors="replace")

    def _extract_pdf(self, path: Path) -> str:
        """Extract text content from PDF files."""
        try:
            reader = PdfReader(path)
            pages = []

            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    pages.append(f"[Page {i + 1}]\n{text}")

            return "\n\n".join(pages)

        except Exception as e:
            logger.error("Failed to extract PDF: %s", e)
            raise ValueError(f"Failed to extract PDF content: {e}")
