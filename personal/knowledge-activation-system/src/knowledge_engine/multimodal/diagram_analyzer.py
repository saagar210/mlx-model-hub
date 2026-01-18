"""Diagram analysis for understanding flowcharts, architecture diagrams, and visual content."""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class DiagramType(str, Enum):
    """Types of diagrams that can be analyzed."""

    FLOWCHART = "flowchart"
    ARCHITECTURE = "architecture"
    SEQUENCE = "sequence"
    ER_DIAGRAM = "er_diagram"
    CLASS_DIAGRAM = "class_diagram"
    NETWORK = "network"
    MINDMAP = "mindmap"
    ORG_CHART = "org_chart"
    GANTT = "gantt"
    UNKNOWN = "unknown"


@dataclass
class DiagramElement:
    """An element within a diagram."""

    id: str
    type: str  # node, edge, label, etc.
    text: str | None = None
    bbox: tuple[int, int, int, int] | None = None  # x, y, width, height
    properties: dict[str, Any] = field(default_factory=dict)
    connected_to: list[str] = field(default_factory=list)


@dataclass
class DiagramRelationship:
    """A relationship/edge between diagram elements."""

    source_id: str
    target_id: str
    label: str | None = None
    relationship_type: str = "connects"  # connects, inherits, uses, etc.
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class DiagramAnalysis:
    """Complete analysis of a diagram."""

    diagram_type: DiagramType
    title: str | None
    description: str
    elements: list[DiagramElement]
    relationships: list[DiagramRelationship]
    extracted_text: list[str]
    summary: str
    confidence: float
    processing_time_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def node_count(self) -> int:
        return len([e for e in self.elements if e.type == "node"])

    @property
    def edge_count(self) -> int:
        return len(self.relationships)

    def to_mermaid(self) -> str | None:
        """Convert diagram to Mermaid format if possible."""
        if self.diagram_type == DiagramType.FLOWCHART:
            return self._to_mermaid_flowchart()
        elif self.diagram_type == DiagramType.SEQUENCE:
            return self._to_mermaid_sequence()
        return None

    def _to_mermaid_flowchart(self) -> str:
        """Convert to Mermaid flowchart."""
        lines = ["flowchart TD"]

        # Add nodes
        for element in self.elements:
            if element.type == "node":
                text = element.text or element.id
                # Escape special characters
                text = text.replace('"', '\\"')
                lines.append(f'    {element.id}["{text}"]')

        # Add edges
        for rel in self.relationships:
            if rel.label:
                lines.append(f"    {rel.source_id} -->|{rel.label}| {rel.target_id}")
            else:
                lines.append(f"    {rel.source_id} --> {rel.target_id}")

        return "\n".join(lines)

    def _to_mermaid_sequence(self) -> str:
        """Convert to Mermaid sequence diagram."""
        lines = ["sequenceDiagram"]

        # Get participants
        participants = set()
        for rel in self.relationships:
            participants.add(rel.source_id)
            participants.add(rel.target_id)

        for p in participants:
            lines.append(f"    participant {p}")

        # Add messages
        for rel in self.relationships:
            label = rel.label or ""
            lines.append(f"    {rel.source_id}->>{rel.target_id}: {label}")

        return "\n".join(lines)

    def to_markdown(self) -> str:
        """Convert analysis to markdown format."""
        lines = [
            "# Diagram Analysis",
            "",
            f"**Type:** {self.diagram_type.value}",
            f"**Confidence:** {self.confidence:.1%}",
            "",
        ]

        if self.title:
            lines.append(f"**Title:** {self.title}")
            lines.append("")

        lines.append("## Summary")
        lines.append(self.summary)
        lines.append("")

        lines.append("## Description")
        lines.append(self.description)
        lines.append("")

        if self.elements:
            lines.append("## Elements")
            for elem in self.elements:
                text = f" - {elem.text}" if elem.text else ""
                lines.append(f"- **{elem.id}** ({elem.type}){text}")
            lines.append("")

        if self.relationships:
            lines.append("## Relationships")
            for rel in self.relationships:
                label = f": {rel.label}" if rel.label else ""
                lines.append(f"- {rel.source_id} → {rel.target_id}{label}")
            lines.append("")

        if self.extracted_text:
            lines.append("## Extracted Text")
            for text in self.extracted_text:
                lines.append(f"- {text}")

        return "\n".join(lines)


class DiagramAnalyzer:
    """Analyze diagrams using vision models and heuristics."""

    def __init__(
        self,
        vision_model: str = "llava",
        ollama_url: str = "http://localhost:11434",
        use_ocr_fallback: bool = True,
    ):
        """
        Initialize diagram analyzer.

        Args:
            vision_model: Vision model to use (llava, bakllava, etc.)
            ollama_url: URL of Ollama server for local models
            use_ocr_fallback: Whether to use OCR as fallback
        """
        self.vision_model = vision_model
        self.ollama_url = ollama_url
        self.use_ocr_fallback = use_ocr_fallback
        self._image_processor = None

    async def analyze_file(self, file_path: str | Path) -> DiagramAnalysis:
        """
        Analyze a diagram image file.

        Args:
            file_path: Path to the diagram image

        Returns:
            DiagramAnalysis with extracted information
        """
        import time

        start_time = time.time()
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")

        # Read image and encode as base64
        with open(path, "rb") as f:
            image_data = f.read()

        analysis = await self._analyze_image(image_data)
        analysis.processing_time_ms = (time.time() - start_time) * 1000
        return analysis

    async def analyze_bytes(self, image_data: bytes) -> DiagramAnalysis:
        """Analyze diagram from bytes."""
        import time

        start_time = time.time()
        analysis = await self._analyze_image(image_data)
        analysis.processing_time_ms = (time.time() - start_time) * 1000
        return analysis

    async def _analyze_image(self, image_data: bytes) -> DiagramAnalysis:
        """Internal image analysis."""
        # Try vision model first
        try:
            analysis = await self._analyze_with_vision_model(image_data)
            if analysis.confidence > 0.5:
                return analysis
        except Exception as e:
            logger.warning(f"Vision model analysis failed: {e}")

        # Fallback to OCR-based analysis
        if self.use_ocr_fallback:
            return await self._analyze_with_ocr(image_data)

        # Return empty analysis if all fails
        return DiagramAnalysis(
            diagram_type=DiagramType.UNKNOWN,
            title=None,
            description="Unable to analyze diagram",
            elements=[],
            relationships=[],
            extracted_text=[],
            summary="Analysis failed",
            confidence=0.0,
            processing_time_ms=0.0,
        )

    async def _analyze_with_vision_model(
        self, image_data: bytes
    ) -> DiagramAnalysis:
        """Analyze using a vision-language model."""
        import httpx

        base64_image = base64.b64encode(image_data).decode("utf-8")

        prompt = """Analyze this diagram image and provide a structured analysis.

Identify:
1. The type of diagram (flowchart, architecture, sequence, ER diagram, class diagram, network, mindmap, org chart, or unknown)
2. A brief title or name for the diagram
3. All text labels and elements visible in the diagram
4. The relationships between elements (arrows, connections, hierarchies)
5. A summary of what the diagram represents

Respond in the following JSON format:
{
    "diagram_type": "flowchart|architecture|sequence|er_diagram|class_diagram|network|mindmap|org_chart|unknown",
    "title": "string or null",
    "description": "detailed description of the diagram",
    "elements": [
        {"id": "unique_id", "type": "node|edge|label", "text": "visible text"}
    ],
    "relationships": [
        {"source": "element_id", "target": "element_id", "label": "relationship label or null"}
    ],
    "extracted_text": ["list of all text visible in diagram"],
    "summary": "brief summary of what the diagram shows"
}"""

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.vision_model,
                        "prompt": prompt,
                        "images": [base64_image],
                        "stream": False,
                        "format": "json",
                    },
                    timeout=60.0,
                )
                response.raise_for_status()

                result = response.json()
                analysis_text = result.get("response", "{}")

                # Parse JSON response
                import json

                try:
                    data = json.loads(analysis_text)
                except json.JSONDecodeError:
                    # Try to extract JSON from response
                    import re

                    json_match = re.search(r"\{.*\}", analysis_text, re.DOTALL)
                    if json_match:
                        data = json.loads(json_match.group())
                    else:
                        raise ValueError("Could not parse JSON from response") from None

                return self._parse_vision_response(data)

        except httpx.HTTPError as e:
            logger.warning(f"Vision model request failed: {e}")
            raise

    def _parse_vision_response(self, data: dict[str, Any]) -> DiagramAnalysis:
        """Parse vision model response into DiagramAnalysis."""
        # Parse diagram type
        diagram_type_str = data.get("diagram_type", "unknown").lower()
        try:
            diagram_type = DiagramType(diagram_type_str)
        except ValueError:
            diagram_type = DiagramType.UNKNOWN

        # Parse elements
        elements = []
        for elem_data in data.get("elements", []):
            elements.append(
                DiagramElement(
                    id=elem_data.get("id", f"elem_{len(elements)}"),
                    type=elem_data.get("type", "node"),
                    text=elem_data.get("text"),
                )
            )

        # Parse relationships
        relationships = []
        for rel_data in data.get("relationships", []):
            relationships.append(
                DiagramRelationship(
                    source_id=rel_data.get("source", ""),
                    target_id=rel_data.get("target", ""),
                    label=rel_data.get("label"),
                )
            )

        return DiagramAnalysis(
            diagram_type=diagram_type,
            title=data.get("title"),
            description=data.get("description", ""),
            elements=elements,
            relationships=relationships,
            extracted_text=data.get("extracted_text", []),
            summary=data.get("summary", ""),
            confidence=0.8,  # High confidence for vision model
            processing_time_ms=0.0,
        )

    async def _analyze_with_ocr(self, image_data: bytes) -> DiagramAnalysis:
        """Fallback analysis using OCR."""
        if self._image_processor is None:
            from knowledge_engine.multimodal.image_processor import ImageProcessor

            self._image_processor = ImageProcessor()

        # Run OCR
        ocr_result = await self._image_processor.process_bytes(image_data)

        # Extract text blocks
        extracted_text = [block.text for block in ocr_result.blocks if block.text]

        # Try to determine diagram type from text content
        diagram_type = self._infer_diagram_type(extracted_text)

        # Create simple elements from text blocks
        elements = []
        for i, block in enumerate(ocr_result.blocks):
            if block.text:
                elements.append(
                    DiagramElement(
                        id=f"text_{i}",
                        type="label",
                        text=block.text,
                        bbox=(
                            block.bbox.x,
                            block.bbox.y,
                            block.bbox.width,
                            block.bbox.height,
                        ),
                    )
                )

        return DiagramAnalysis(
            diagram_type=diagram_type,
            title=extracted_text[0] if extracted_text else None,
            description="Diagram analyzed using OCR (limited structural analysis)",
            elements=elements,
            relationships=[],  # Can't determine from OCR alone
            extracted_text=extracted_text,
            summary=f"Diagram containing: {', '.join(extracted_text[:5])}..."
            if extracted_text
            else "Unable to extract text",
            confidence=0.4,  # Lower confidence for OCR-only
            processing_time_ms=0.0,
        )

    def _infer_diagram_type(self, texts: list[str]) -> DiagramType:
        """Infer diagram type from extracted text."""
        text_lower = " ".join(texts).lower()

        # Keywords for different diagram types
        if any(kw in text_lower for kw in ["start", "end", "if", "yes", "no", "decision"]):
            return DiagramType.FLOWCHART
        elif any(kw in text_lower for kw in ["server", "database", "api", "client", "service"]):
            return DiagramType.ARCHITECTURE
        elif any(kw in text_lower for kw in ["class", "interface", "extends", "implements"]):
            return DiagramType.CLASS_DIAGRAM
        elif any(kw in text_lower for kw in ["entity", "relationship", "primary key", "foreign"]):
            return DiagramType.ER_DIAGRAM
        elif any(kw in text_lower for kw in ["router", "switch", "firewall", "subnet"]):
            return DiagramType.NETWORK

        return DiagramType.UNKNOWN

    def detect_shapes(self, image_data: bytes) -> list[dict[str, Any]]:
        """
        Detect geometric shapes in diagram using computer vision.

        Returns list of detected shapes with bounding boxes.
        """
        try:
            import cv2
            import numpy as np

            # Convert bytes to numpy array
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Apply threshold
            _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)

            # Find contours
            contours, _ = cv2.findContours(
                thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            shapes = []
            for contour in contours:
                # Filter small contours
                area = cv2.contourArea(contour)
                if area < 100:
                    continue

                # Approximate polygon
                peri = cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, 0.04 * peri, True)

                # Determine shape
                vertices = len(approx)
                if vertices == 3:
                    shape_type = "triangle"
                elif vertices == 4:
                    # Check if rectangle or diamond
                    x, y, w, h = cv2.boundingRect(approx)
                    aspect = w / float(h)
                    shape_type = "rectangle" if 0.8 <= aspect <= 1.2 else "rectangle"
                elif vertices > 6:
                    shape_type = "circle"
                else:
                    shape_type = "polygon"

                x, y, w, h = cv2.boundingRect(contour)
                shapes.append(
                    {
                        "type": shape_type,
                        "vertices": vertices,
                        "bbox": {"x": x, "y": y, "width": w, "height": h},
                        "area": area,
                    }
                )

            return shapes

        except ImportError:
            logger.warning("OpenCV not available for shape detection")
            return []
        except Exception as e:
            logger.warning(f"Shape detection failed: {e}")
            return []
