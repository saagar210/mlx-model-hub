"""PDF processing with text extraction, OCR fallback, and structure analysis."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

logger = logging.getLogger(__name__)


@dataclass
class PDFImage:
    """An image extracted from a PDF."""

    page_num: int
    image_index: int
    width: int
    height: int
    data: bytes
    format: str = "png"
    ocr_text: str | None = None


@dataclass
class PDFTable:
    """A table extracted from a PDF."""

    page_num: int
    table_index: int
    headers: list[str]
    rows: list[list[str]]
    bbox: tuple[float, float, float, float] | None = None

    @property
    def num_rows(self) -> int:
        return len(self.rows)

    @property
    def num_columns(self) -> int:
        return len(self.headers) if self.headers else 0

    def to_markdown(self) -> str:
        """Convert table to markdown format."""
        if not self.headers:
            return ""

        lines = []
        lines.append("| " + " | ".join(self.headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(self.headers)) + " |")

        for row in self.rows:
            # Pad row if needed
            padded = row + [""] * (len(self.headers) - len(row))
            lines.append("| " + " | ".join(padded[: len(self.headers)]) + " |")

        return "\n".join(lines)


@dataclass
class PDFPage:
    """A single page from a PDF."""

    page_num: int
    text: str
    width: float
    height: float
    images: list[PDFImage] = field(default_factory=list)
    tables: list[PDFTable] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    is_ocr: bool = False

    @property
    def word_count(self) -> int:
        return len(self.text.split())

    @property
    def has_images(self) -> bool:
        return len(self.images) > 0

    @property
    def has_tables(self) -> bool:
        return len(self.tables) > 0

    def get_full_content(self, include_tables: bool = True) -> str:
        """Get full page content including tables in markdown."""
        content = [self.text]

        if include_tables and self.tables:
            content.append("\n\n## Tables\n")
            for table in self.tables:
                content.append(f"\n### Table {table.table_index + 1}\n")
                content.append(table.to_markdown())

        return "\n".join(content)


@dataclass
class PDFDocument:
    """A processed PDF document."""

    title: str
    author: str
    pages: list[PDFPage]
    total_pages: int
    metadata: dict[str, Any] = field(default_factory=dict)
    processing_time_ms: float = 0.0

    @property
    def full_text(self) -> str:
        """Get all text from all pages."""
        return "\n\n".join(
            f"[Page {page.page_num}]\n{page.text}" for page in self.pages
        )

    @property
    def word_count(self) -> int:
        return sum(page.word_count for page in self.pages)

    @property
    def all_images(self) -> list[PDFImage]:
        """Get all images from all pages."""
        return [img for page in self.pages for img in page.images]

    @property
    def all_tables(self) -> list[PDFTable]:
        """Get all tables from all pages."""
        return [table for page in self.pages for table in page.tables]

    def get_page(self, page_num: int) -> PDFPage | None:
        """Get a specific page by number (1-indexed)."""
        for page in self.pages:
            if page.page_num == page_num:
                return page
        return None

    def iter_chunks(
        self, chunk_size: int = 1000, overlap: int = 200
    ) -> Iterator[tuple[str, dict[str, Any]]]:
        """
        Iterate over text chunks with metadata.

        Args:
            chunk_size: Target size of each chunk in characters
            overlap: Overlap between chunks

        Yields:
            Tuples of (chunk_text, metadata)
        """
        for page in self.pages:
            text = page.text
            start = 0

            while start < len(text):
                end = min(start + chunk_size, len(text))

                # Try to end at sentence boundary
                if end < len(text):
                    for sep in [". ", ".\n", "\n\n", "\n"]:
                        last_sep = text.rfind(sep, start, end)
                        if last_sep > start + chunk_size // 2:
                            end = last_sep + len(sep)
                            break

                chunk = text[start:end].strip()
                if chunk:
                    metadata = {
                        "page_num": page.page_num,
                        "is_ocr": page.is_ocr,
                        "start_char": start,
                        "end_char": end,
                    }
                    yield chunk, metadata

                start = end - overlap if end < len(text) else end


class PDFProcessor:
    """Process PDF documents for text extraction and analysis."""

    def __init__(
        self,
        extract_images: bool = True,
        extract_tables: bool = True,
        ocr_fallback: bool = True,
        ocr_language: str = "eng",
    ):
        """
        Initialize PDF processor.

        Args:
            extract_images: Whether to extract images from PDFs
            extract_tables: Whether to extract tables from PDFs
            ocr_fallback: Whether to use OCR for image-based PDFs
            ocr_language: Language for OCR
        """
        self.extract_images = extract_images
        self.extract_tables = extract_tables
        self.ocr_fallback = ocr_fallback
        self.ocr_language = ocr_language
        self._image_processor = None

    async def process_file(
        self,
        file_path: str | Path,
        page_range: tuple[int, int] | None = None,
    ) -> PDFDocument:
        """
        Process a PDF file.

        Args:
            file_path: Path to the PDF file
            page_range: Optional (start, end) page range (1-indexed, inclusive)

        Returns:
            PDFDocument with extracted content
        """
        import time

        start_time = time.time()
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {path}")

        # Try different PDF libraries
        try:
            doc = await self._process_with_pymupdf(path, page_range)
        except ImportError:
            try:
                doc = await self._process_with_pypdf(path, page_range)
            except ImportError:
                raise ImportError(
                    "No PDF library available. Install pymupdf or pypdf: "
                    "pip install pymupdf pypdf"
                )

        doc.processing_time_ms = (time.time() - start_time) * 1000
        return doc

    async def process_bytes(
        self,
        pdf_data: bytes,
        title: str = "Untitled",
        page_range: tuple[int, int] | None = None,
    ) -> PDFDocument:
        """Process PDF from bytes."""
        import io
        import tempfile
        import time

        start_time = time.time()

        # Write to temp file for processing
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_data)
            temp_path = f.name

        try:
            doc = await self.process_file(temp_path, page_range)
            doc.title = title
            doc.processing_time_ms = (time.time() - start_time) * 1000
            return doc
        finally:
            Path(temp_path).unlink(missing_ok=True)

    async def _process_with_pymupdf(
        self,
        path: Path,
        page_range: tuple[int, int] | None,
    ) -> PDFDocument:
        """Process PDF using PyMuPDF (fitz)."""
        import fitz

        doc = fitz.open(path)
        metadata = doc.metadata or {}

        title = metadata.get("title", path.stem)
        author = metadata.get("author", "")

        pages: list[PDFPage] = []
        start_page = (page_range[0] - 1) if page_range else 0
        end_page = page_range[1] if page_range else doc.page_count

        for page_num in range(start_page, min(end_page, doc.page_count)):
            page = doc[page_num]
            text = page.get_text()

            # Check if page needs OCR
            is_ocr = False
            if len(text.strip()) < 50 and self.ocr_fallback:
                text = await self._ocr_page(page)
                is_ocr = True

            # Extract images
            images: list[PDFImage] = []
            if self.extract_images:
                images = self._extract_images_pymupdf(page, page_num + 1)

            # Extract tables (basic extraction)
            tables: list[PDFTable] = []
            if self.extract_tables:
                tables = self._extract_tables_pymupdf(page, page_num + 1)

            # Extract links
            links = [
                link["uri"]
                for link in page.get_links()
                if link.get("uri", "").startswith("http")
            ]

            pages.append(
                PDFPage(
                    page_num=page_num + 1,
                    text=text,
                    width=page.rect.width,
                    height=page.rect.height,
                    images=images,
                    tables=tables,
                    links=links,
                    is_ocr=is_ocr,
                )
            )

        doc.close()

        return PDFDocument(
            title=title,
            author=author,
            pages=pages,
            total_pages=len(pages),
            metadata=dict(metadata),
        )

    async def _process_with_pypdf(
        self,
        path: Path,
        page_range: tuple[int, int] | None,
    ) -> PDFDocument:
        """Process PDF using pypdf."""
        from pypdf import PdfReader

        reader = PdfReader(path)
        metadata = reader.metadata or {}

        title = metadata.get("/Title", path.stem) or path.stem
        author = metadata.get("/Author", "") or ""

        pages: list[PDFPage] = []
        start_page = (page_range[0] - 1) if page_range else 0
        end_page = page_range[1] if page_range else len(reader.pages)

        for page_num in range(start_page, min(end_page, len(reader.pages))):
            page = reader.pages[page_num]
            text = page.extract_text() or ""

            # Check if page needs OCR
            is_ocr = False
            if len(text.strip()) < 50 and self.ocr_fallback:
                # pypdf doesn't have easy image rendering, skip OCR for now
                pass

            # Get page dimensions
            mediabox = page.mediabox
            width = float(mediabox.width)
            height = float(mediabox.height)

            pages.append(
                PDFPage(
                    page_num=page_num + 1,
                    text=text,
                    width=width,
                    height=height,
                    is_ocr=is_ocr,
                )
            )

        return PDFDocument(
            title=str(title),
            author=str(author),
            pages=pages,
            total_pages=len(pages),
            metadata={k: str(v) for k, v in (metadata or {}).items()},
        )

    async def _ocr_page(self, page: Any) -> str:
        """OCR a page that has no extractable text."""
        if self._image_processor is None:
            from knowledge_engine.multimodal.image_processor import ImageProcessor

            self._image_processor = ImageProcessor(
                ocr_engine="tesseract",
                language=self.ocr_language,
            )

        try:
            # Render page to image
            pix = page.get_pixmap(matrix=page.matrix)
            image_data = pix.tobytes("png")

            result = await self._image_processor.process_bytes(image_data)
            return result.full_text
        except Exception as e:
            logger.warning(f"OCR failed for page: {e}")
            return ""

    def _extract_images_pymupdf(
        self, page: Any, page_num: int
    ) -> list[PDFImage]:
        """Extract images from a PyMuPDF page."""
        images: list[PDFImage] = []

        try:
            image_list = page.get_images()

            for img_index, img in enumerate(image_list):
                try:
                    xref = img[0]
                    base_image = page.parent.extract_image(xref)

                    images.append(
                        PDFImage(
                            page_num=page_num,
                            image_index=img_index,
                            width=base_image["width"],
                            height=base_image["height"],
                            data=base_image["image"],
                            format=base_image["ext"],
                        )
                    )
                except Exception as e:
                    logger.warning(f"Failed to extract image {img_index}: {e}")
        except Exception as e:
            logger.warning(f"Failed to get images from page: {e}")

        return images

    def _extract_tables_pymupdf(
        self, page: Any, page_num: int
    ) -> list[PDFTable]:
        """
        Extract tables from a PyMuPDF page.

        Note: This is a basic implementation. For better table extraction,
        consider using tabula-py or camelot.
        """
        tables: list[PDFTable] = []

        try:
            # PyMuPDF 1.23.0+ has find_tables()
            if hasattr(page, "find_tables"):
                found_tables = page.find_tables()

                for idx, table in enumerate(found_tables.tables):
                    try:
                        extracted = table.extract()
                        if extracted and len(extracted) > 0:
                            headers = [str(h) for h in extracted[0]]
                            rows = [[str(cell) for cell in row] for row in extracted[1:]]

                            tables.append(
                                PDFTable(
                                    page_num=page_num,
                                    table_index=idx,
                                    headers=headers,
                                    rows=rows,
                                )
                            )
                    except Exception as e:
                        logger.warning(f"Failed to extract table {idx}: {e}")
        except Exception as e:
            logger.debug(f"Table extraction not available: {e}")

        return tables

    def get_toc(self, file_path: str | Path) -> list[tuple[int, str, int]]:
        """
        Get table of contents from PDF.

        Returns:
            List of (level, title, page_num) tuples
        """
        try:
            import fitz

            doc = fitz.open(file_path)
            toc = doc.get_toc()
            doc.close()
            return toc
        except ImportError:
            return []
        except Exception as e:
            logger.warning(f"Failed to get TOC: {e}")
            return []
