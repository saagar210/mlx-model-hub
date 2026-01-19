"""Entity extraction using LLM for knowledge graph construction."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

import httpx

from knowledge.ai import AIProvider
from knowledge.logging import get_logger

logger = get_logger(__name__)

# Ollama configuration for local fallback
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:14b")


@dataclass
class Entity:
    """Extracted entity."""

    name: str
    entity_type: str  # technology, concept, person, organization, tool, framework
    confidence: float = 1.0


@dataclass
class Relationship:
    """Relationship between entities."""

    from_entity: str
    to_entity: str
    relation_type: str  # uses, mentions, depends_on, related_to, implements
    confidence: float = 1.0


@dataclass
class ExtractionResult:
    """Result of entity extraction."""

    entities: list[Entity]
    relationships: list[Relationship]
    success: bool = True
    error: str | None = None


ENTITY_PROMPT = """Extract entities and relationships from this technical content.

Entity types:
- technology: Programming languages, databases, protocols (Python, PostgreSQL, HTTP)
- concept: Abstract ideas, patterns, methodologies (microservices, caching, REST)
- tool: Software tools and utilities (Docker, Git, Webpack)
- framework: Libraries and frameworks (FastAPI, React, TensorFlow)
- organization: Companies, projects, communities (Google, OpenAI, Linux Foundation)
- person: Named individuals mentioned

Relationship types:
- uses: Entity A uses Entity B
- depends_on: Entity A depends on Entity B
- implements: Entity A implements Entity B
- related_to: Entity A is related to Entity B

Return valid JSON only:
{{
  "entities": [
    {{"name": "PostgreSQL", "type": "technology"}},
    {{"name": "vector search", "type": "concept"}}
  ],
  "relationships": [
    {{"from": "KAS", "to": "PostgreSQL", "type": "uses"}}
  ]
}}

Content:
Title: {title}
Text: {content}

JSON:"""


async def _extract_with_ollama(prompt: str) -> str | None:
    """Extract entities using local Ollama model.

    Args:
        prompt: The extraction prompt

    Returns:
        Response content or None if failed
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.2},
                },
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("response", "")
            else:
                logger.warning(
                    "ollama_extraction_failed",
                    status_code=response.status_code,
                )
                return None
    except Exception as e:
        logger.warning("ollama_connection_failed", error=str(e))
        return None


async def extract_entities(
    title: str,
    content: str,
    ai: AIProvider | None = None,
    use_ollama: bool = False,
) -> ExtractionResult:
    """
    Extract entities and relationships from content using LLM.

    Args:
        title: Content title
        content: Content text (first 3000 chars will be used)
        ai: Optional AI provider instance
        use_ollama: Force use of local Ollama instead of OpenRouter

    Returns:
        ExtractionResult with entities and relationships
    """
    prompt = ENTITY_PROMPT.format(
        title=title,
        content=content[:3000],
    )

    raw_content = None

    # If AI provider is explicitly passed, use it (allows mocking in tests)
    if ai is not None:
        try:
            response = await ai.generate(
                prompt=prompt,
                temperature=0.2,
                max_tokens=500,
            )

            if response.success:
                raw_content = response.content.strip()
            else:
                logger.warning(
                    "entity_extraction_failed",
                    error=response.error,
                    title=title[:50],
                )
                return ExtractionResult(
                    entities=[],
                    relationships=[],
                    success=False,
                    error=response.error,
                )
        except Exception as e:
            logger.warning("ai_provider_extraction_failed", error=str(e))

    # Try Ollama if no AI provider or if explicitly requested
    if raw_content is None and (use_ollama or not os.environ.get("OPENROUTER_API_KEY")):
        logger.debug("using_ollama_for_extraction", title=title[:50])
        raw_content = await _extract_with_ollama(prompt)

        if raw_content:
            logger.debug("ollama_extraction_success", title=title[:50])
        else:
            logger.warning("ollama_extraction_failed_fallback", title=title[:50])

    # Fall back to OpenRouter if nothing else worked and API key is available
    if raw_content is None and os.environ.get("OPENROUTER_API_KEY"):
        ai = AIProvider()

        try:
            response = await ai.generate(
                prompt=prompt,
                temperature=0.2,
                max_tokens=500,
            )

            if response.success:
                raw_content = response.content.strip()
            else:
                logger.warning(
                    "entity_extraction_failed",
                    error=response.error,
                    title=title[:50],
                )
                return ExtractionResult(
                    entities=[],
                    relationships=[],
                    success=False,
                    error=response.error,
                )
        except Exception as e:
            logger.warning("openrouter_extraction_failed", error=str(e))

    # If neither worked, return error
    if raw_content is None:
        return ExtractionResult(
            entities=[],
            relationships=[],
            success=False,
            error="No LLM available. Set OPENROUTER_API_KEY or ensure Ollama is running.",
        )

    try:
        # Try to extract JSON from response (handle markdown code blocks)
        json_match = re.search(r'\{[\s\S]*\}', raw_content)
        if not json_match:
            return ExtractionResult(
                entities=[],
                relationships=[],
                success=False,
                error="No JSON found in response",
            )

        json_str = json_match.group(0)

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            return ExtractionResult(
                entities=[],
                relationships=[],
                success=False,
                error=f"Invalid JSON: {e}",
            )

        # Parse entities
        entities = []
        for e in data.get("entities", []):
            if isinstance(e, dict) and "name" in e and "type" in e:
                entities.append(
                    Entity(
                        name=e["name"][:100],  # Limit name length
                        entity_type=e["type"],
                        confidence=e.get("confidence", 1.0),
                    )
                )

        # Parse relationships
        relationships = []
        for r in data.get("relationships", []):
            if isinstance(r, dict) and "from" in r and "to" in r and "type" in r:
                relationships.append(
                    Relationship(
                        from_entity=r["from"][:100],
                        to_entity=r["to"][:100],
                        relation_type=r["type"],
                        confidence=r.get("confidence", 1.0),
                    )
                )

        logger.debug(
            "entity_extraction_success",
            title=title[:50],
            entity_count=len(entities),
            relationship_count=len(relationships),
        )

        return ExtractionResult(
            entities=entities,
            relationships=relationships,
            success=True,
        )

    except Exception as e:
        logger.error(
            "entity_extraction_error",
            error=str(e),
            error_type=type(e).__name__,
            title=title[:50],
        )
        return ExtractionResult(
            entities=[],
            relationships=[],
            success=False,
            error=str(e),
        )


def merge_entities(results: list[ExtractionResult]) -> ExtractionResult:
    """
    Merge multiple extraction results, deduplicating entities.

    Args:
        results: List of extraction results to merge

    Returns:
        Merged ExtractionResult
    """
    seen_entities: dict[str, Entity] = {}
    seen_relationships: set[tuple[str, str, str]] = set()
    relationships: list[Relationship] = []

    for result in results:
        if not result.success:
            continue

        # Deduplicate entities by name (case-insensitive)
        for entity in result.entities:
            key = entity.name.lower()
            if key not in seen_entities:
                seen_entities[key] = entity

        # Deduplicate relationships
        for rel in result.relationships:
            key = (rel.from_entity.lower(), rel.to_entity.lower(), rel.relation_type)
            if key not in seen_relationships:
                seen_relationships.add(key)
                relationships.append(rel)

    return ExtractionResult(
        entities=list(seen_entities.values()),
        relationships=relationships,
        success=True,
    )
