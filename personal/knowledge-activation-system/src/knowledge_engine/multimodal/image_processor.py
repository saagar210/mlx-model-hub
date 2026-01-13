"""Image processing with OCR, object detection, and content extraction."""

from __future__ import annotations

import base64
import hashlib
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ImageFormat(str, Enum):
    """Supported image formats."""

    PNG = "png"
    JPEG = "jpeg"
    WEBP = "webp"
    GIF = "gif"
    BMP = "bmp"
    TIFF = "tiff"


@dataclass
class BoundingBox:
    """Bounding box for detected regions."""

    x: int
    y: int
    width: int
    height: int

    @property
    def area(self) -> int:
        return self.width * self.height

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)

    def to_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}


@dataclass
class TextBlock:
    """A block of text extracted from an image."""

    text: str
    confidence: float
    bbox: BoundingBox
    language: str = "en"
    block_type: str = "paragraph"  # paragraph, heading, caption, etc.


@dataclass
class OCRResult:
    """Result of OCR processing."""

    full_text: str
    blocks: list[TextBlock]
    confidence: float  # Average confidence
    language: str
    processing_time_ms: float
    image_dimensions: tuple[int, int]
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def word_count(self) -> int:
        return len(self.full_text.split())

    def get_high_confidence_text(self, threshold: float = 0.8) -> str:
        """Get text from blocks with confidence above threshold."""
        return " ".join(
            block.text for block in self.blocks if block.confidence >= threshold
        )


@dataclass
class ImageMetadata:
    """Metadata extracted from an image."""

    width: int
    height: int
    format: ImageFormat
    file_size: int
    color_mode: str  # RGB, RGBA, L, etc.
    has_transparency: bool
    dominant_colors: list[str]
    hash: str


class ImageProcessor:
    """Process images for OCR, object detection, and content extraction."""

    def __init__(
        self,
        ocr_engine: str = "tesseract",
        language: str = "eng",
        enable_preprocessing: bool = True,
    ):
        """
        Initialize image processor.

        Args:
            ocr_engine: OCR engine to use (tesseract, easyocr, paddleocr)
            language: Default OCR language
            enable_preprocessing: Whether to preprocess images for better OCR
        """
        self.ocr_engine = ocr_engine
        self.language = language
        self.enable_preprocessing = enable_preprocessing
        self._ocr = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy initialization of OCR engine."""
        if self._initialized:
            return

        if self.ocr_engine == "tesseract":
            try:
                import pytesseract

                pytesseract.get_tesseract_version()
                self._ocr = pytesseract
                logger.info("Initialized Tesseract OCR engine")
            except Exception as e:
                logger.warning(f"Tesseract not available: {e}")
                self._ocr = None

        elif self.ocr_engine == "easyocr":
            try:
                import easyocr

                self._ocr = easyocr.Reader([self.language[:2]])
                logger.info("Initialized EasyOCR engine")
            except Exception as e:
                logger.warning(f"EasyOCR not available: {e}")
                self._ocr = None

        self._initialized = True

    async def process_file(self, file_path: str | Path) -> OCRResult:
        """
        Process an image file.

        Args:
            file_path: Path to the image file

        Returns:
            OCRResult with extracted text and metadata
        """
        import time

        start_time = time.time()
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")

        # Load image
        try:
            from PIL import Image

            image = Image.open(path)
        except ImportError:
            logger.error("Pillow not installed. Install with: pip install pillow")
            raise

        return await self._process_image(image, start_time)

    async def process_bytes(
        self, image_data: bytes, format_hint: str | None = None
    ) -> OCRResult:
        """
        Process image from bytes.

        Args:
            image_data: Raw image bytes
            format_hint: Optional format hint (png, jpeg, etc.)

        Returns:
            OCRResult with extracted text and metadata
        """
        import io
        import time

        start_time = time.time()

        try:
            from PIL import Image

            image = Image.open(io.BytesIO(image_data))
        except ImportError:
            logger.error("Pillow not installed")
            raise

        return await self._process_image(image, start_time)

    async def process_base64(self, base64_data: str) -> OCRResult:
        """Process base64-encoded image."""
        # Remove data URL prefix if present
        if "," in base64_data:
            base64_data = base64_data.split(",", 1)[1]

        image_bytes = base64.b64decode(base64_data)
        return await self.process_bytes(image_bytes)

    async def _process_image(self, image: Any, start_time: float) -> OCRResult:
        """Internal image processing."""
        import time

        self._ensure_initialized()

        width, height = image.size
        blocks: list[TextBlock] = []
        full_text = ""
        confidence = 0.0

        # Preprocess if enabled
        if self.enable_preprocessing:
            image = self._preprocess_image(image)

        # Run OCR
        if self._ocr is not None:
            if self.ocr_engine == "tesseract":
                blocks, full_text, confidence = self._run_tesseract(image)
            elif self.ocr_engine == "easyocr":
                blocks, full_text, confidence = self._run_easyocr(image)
        else:
            logger.warning("No OCR engine available, returning empty result")

        processing_time = (time.time() - start_time) * 1000

        return OCRResult(
            full_text=full_text,
            blocks=blocks,
            confidence=confidence,
            language=self.language,
            processing_time_ms=processing_time,
            image_dimensions=(width, height),
        )

    def _preprocess_image(self, image: Any) -> Any:
        """Preprocess image for better OCR results."""
        try:
            from PIL import ImageEnhance, ImageFilter

            # Convert to RGB if necessary
            if image.mode not in ("L", "RGB"):
                image = image.convert("RGB")

            # Convert to grayscale for OCR
            gray = image.convert("L")

            # Enhance contrast
            enhancer = ImageEnhance.Contrast(gray)
            gray = enhancer.enhance(1.5)

            # Apply slight sharpening
            gray = gray.filter(ImageFilter.SHARPEN)

            return gray
        except Exception as e:
            logger.warning(f"Image preprocessing failed: {e}")
            return image

    def _run_tesseract(self, image: Any) -> tuple[list[TextBlock], str, float]:
        """Run Tesseract OCR."""
        import pytesseract

        blocks: list[TextBlock] = []

        # Get detailed data
        data = pytesseract.image_to_data(
            image, lang=self.language, output_type=pytesseract.Output.DICT
        )

        # Get full text
        full_text = pytesseract.image_to_string(image, lang=self.language)

        # Process blocks
        total_conf = 0.0
        valid_blocks = 0

        current_text = []
        current_bbox = None

        for i, text in enumerate(data["text"]):
            conf = float(data["conf"][i]) / 100.0 if data["conf"][i] != -1 else 0.0

            if text.strip():
                if conf > 0:
                    total_conf += conf
                    valid_blocks += 1

                current_text.append(text)
                bbox = BoundingBox(
                    x=data["left"][i],
                    y=data["top"][i],
                    width=data["width"][i],
                    height=data["height"][i],
                )
                if current_bbox is None:
                    current_bbox = bbox
            elif current_text and current_bbox:
                # End of block
                blocks.append(
                    TextBlock(
                        text=" ".join(current_text),
                        confidence=conf,
                        bbox=current_bbox,
                        language=self.language,
                    )
                )
                current_text = []
                current_bbox = None

        avg_confidence = total_conf / valid_blocks if valid_blocks > 0 else 0.0

        return blocks, full_text.strip(), avg_confidence

    def _run_easyocr(self, image: Any) -> tuple[list[TextBlock], str, float]:
        """Run EasyOCR."""
        import numpy as np

        blocks: list[TextBlock] = []

        # Convert PIL to numpy array
        image_np = np.array(image)

        # Run OCR
        results = self._ocr.readtext(image_np)

        texts = []
        total_conf = 0.0

        for bbox_points, text, conf in results:
            texts.append(text)
            total_conf += conf

            # Convert bbox points to BoundingBox
            x_coords = [p[0] for p in bbox_points]
            y_coords = [p[1] for p in bbox_points]
            bbox = BoundingBox(
                x=int(min(x_coords)),
                y=int(min(y_coords)),
                width=int(max(x_coords) - min(x_coords)),
                height=int(max(y_coords) - min(y_coords)),
            )

            blocks.append(
                TextBlock(
                    text=text,
                    confidence=conf,
                    bbox=bbox,
                    language=self.language,
                )
            )

        full_text = " ".join(texts)
        avg_confidence = total_conf / len(results) if results else 0.0

        return blocks, full_text, avg_confidence

    def extract_metadata(self, image_path: str | Path) -> ImageMetadata:
        """Extract metadata from an image file."""
        from PIL import Image

        path = Path(image_path)
        image = Image.open(path)

        # Get dominant colors
        dominant_colors = self._get_dominant_colors(image)

        # Calculate hash
        image_hash = self._calculate_image_hash(image)

        return ImageMetadata(
            width=image.width,
            height=image.height,
            format=ImageFormat(image.format.lower()) if image.format else ImageFormat.PNG,
            file_size=path.stat().st_size,
            color_mode=image.mode,
            has_transparency=image.mode in ("RGBA", "LA", "PA"),
            dominant_colors=dominant_colors,
            hash=image_hash,
        )

    def _get_dominant_colors(self, image: Any, num_colors: int = 5) -> list[str]:
        """Extract dominant colors from image."""
        try:
            # Resize for faster processing
            small = image.resize((100, 100))
            if small.mode != "RGB":
                small = small.convert("RGB")

            # Get colors
            colors = small.getcolors(maxcolors=10000)
            if not colors:
                return []

            # Sort by frequency
            sorted_colors = sorted(colors, key=lambda x: x[0], reverse=True)

            # Convert to hex
            hex_colors = []
            for count, rgb in sorted_colors[:num_colors]:
                hex_color = "#{:02x}{:02x}{:02x}".format(*rgb)
                hex_colors.append(hex_color)

            return hex_colors
        except Exception:
            return []

    def _calculate_image_hash(self, image: Any) -> str:
        """Calculate perceptual hash of image."""
        try:
            # Resize to small size
            small = image.resize((8, 8)).convert("L")

            # Get pixels
            pixels = list(small.getdata())

            # Calculate average
            avg = sum(pixels) / len(pixels)

            # Generate hash
            bits = "".join("1" if p >= avg else "0" for p in pixels)
            hash_int = int(bits, 2)

            return f"{hash_int:016x}"
        except Exception:
            # Fallback to MD5 of raw data
            import io

            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            return hashlib.md5(buffer.getvalue()).hexdigest()
