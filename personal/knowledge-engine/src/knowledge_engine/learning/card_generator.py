"""Generate review cards from knowledge base content.

This module automatically creates review cards from:
- Document chunks (key concepts, facts)
- Memories (stored facts and preferences)
- Entities (named entities and their relations)

Card generation uses LLM to create meaningful questions/prompts
from source content.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from knowledge_engine.config import get_settings
from knowledge_engine.core.llm import LLMClient
from knowledge_engine.learning.fsrs_scheduler import ReviewCard, ReviewState
from knowledge_engine.logging_config import get_logger

logger = get_logger(__name__)


def _utc_now() -> datetime:
    """Return current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


class CardType(str, Enum):
    """Types of review cards."""

    CONCEPT = "concept"  # Key concept from content
    FACT = "fact"  # Factual information
    DEFINITION = "definition"  # Term definition
    PROCEDURE = "procedure"  # How-to steps
    COMPARISON = "comparison"  # Compare/contrast
    CLOZE = "cloze"  # Fill-in-the-blank


@dataclass
class CardTemplate:
    """Template for generating a specific card type."""

    card_type: CardType
    prompt_template: str
    min_content_length: int = 50
    max_cards_per_source: int = 3


# Default templates for each card type
CARD_TEMPLATES = {
    CardType.CONCEPT: CardTemplate(
        card_type=CardType.CONCEPT,
        prompt_template="""Generate a review question about a key concept from this text.

Text:
{content}

Generate a single question that tests understanding of a key concept.
The question should be specific and answerable from the text.

Format your response as:
QUESTION: [Your question here]
ANSWER: [The answer from the text]
CONTEXT: [Brief context or explanation]""",
        min_content_length=100,
        max_cards_per_source=3,
    ),
    CardType.FACT: CardTemplate(
        card_type=CardType.FACT,
        prompt_template="""Extract a factual review question from this text.

Text:
{content}

Generate a question about a specific fact, date, number, or detail.
The answer should be directly stated in the text.

Format your response as:
QUESTION: [Your factual question]
ANSWER: [The specific answer]
CONTEXT: [Source context]""",
        min_content_length=50,
        max_cards_per_source=2,
    ),
    CardType.DEFINITION: CardTemplate(
        card_type=CardType.DEFINITION,
        prompt_template="""Create a definition review card from this text.

Text:
{content}

If the text contains any defined terms, create a "What is...?" question.
If no clear definitions exist, respond with "NO_DEFINITION".

Format your response as:
QUESTION: What is [term]?
ANSWER: [Definition from text]
CONTEXT: [How it's used]""",
        min_content_length=30,
        max_cards_per_source=2,
    ),
    CardType.PROCEDURE: CardTemplate(
        card_type=CardType.PROCEDURE,
        prompt_template="""Create a procedural review question from this text.

Text:
{content}

If the text describes a process, method, or steps, create a "How do you...?" question.
If no procedure exists, respond with "NO_PROCEDURE".

Format your response as:
QUESTION: How do you [action]?
ANSWER: [Steps or method]
CONTEXT: [When to use this]""",
        min_content_length=100,
        max_cards_per_source=1,
    ),
}


class CardGenerator:
    """Generate review cards from various content sources."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        """Initialize card generator.

        Args:
            llm_client: LLM client for generating questions (creates one if not provided)
        """
        self._llm_client = llm_client
        self._settings = get_settings()

    async def _get_llm(self) -> LLMClient:
        """Get or create LLM client."""
        if self._llm_client is None:
            self._llm_client = LLMClient(self._settings)
        return self._llm_client

    async def generate_from_chunk(
        self,
        chunk_id: str,
        content: str,
        document_id: str,
        document_title: str,
        namespace: str = "default",
        card_types: list[CardType] | None = None,
        tags: list[str] | None = None,
    ) -> list[ReviewCard]:
        """Generate review cards from a document chunk.

        Args:
            chunk_id: ID of the source chunk
            content: Text content of the chunk
            document_id: Parent document ID
            document_title: Document title for context
            namespace: Namespace for the cards
            card_types: Which card types to generate (defaults to CONCEPT and FACT)
            tags: Tags to add to generated cards

        Returns:
            List of generated review cards
        """
        card_types = card_types or [CardType.CONCEPT, CardType.FACT]
        tags = tags or []
        cards: list[ReviewCard] = []

        llm = await self._get_llm()

        for card_type in card_types:
            template = CARD_TEMPLATES.get(card_type)
            if not template:
                continue

            # Skip if content too short
            if len(content) < template.min_content_length:
                continue

            try:
                # Generate card using LLM
                prompt = template.prompt_template.format(content=content)
                response = await llm.generate(prompt, max_tokens=500)

                # Parse response
                parsed = self._parse_card_response(response)
                if parsed:
                    card = ReviewCard(
                        id=uuid4(),
                        front=parsed["question"],
                        back=parsed["answer"],
                        context=parsed.get("context", ""),
                        source_type="chunk",
                        source_id=chunk_id,
                        document_id=document_id,
                        namespace=namespace,
                        state=ReviewState.NEW,
                        tags=[card_type.value, f"doc:{document_title[:50]}"] + tags,
                        created_at=_utc_now(),
                        updated_at=_utc_now(),
                    )
                    cards.append(card)

                    logger.debug(
                        "Generated %s card from chunk %s",
                        card_type.value,
                        chunk_id,
                    )

            except Exception as e:
                logger.warning(
                    "Failed to generate %s card from chunk %s: %s",
                    card_type.value,
                    chunk_id,
                    str(e),
                )

        return cards

    async def generate_from_memory(
        self,
        memory_id: str,
        content: str,
        memory_type: str,
        namespace: str = "default",
        tags: list[str] | None = None,
    ) -> list[ReviewCard]:
        """Generate review cards from a memory.

        Args:
            memory_id: ID of the source memory
            content: Memory content
            memory_type: Type of memory (fact, preference, etc.)
            namespace: Namespace for the cards
            tags: Tags to add to generated cards

        Returns:
            List of generated review cards
        """
        tags = tags or []
        cards: list[ReviewCard] = []

        # Memory cards are simpler - often direct recall
        if memory_type == "fact":
            # Create a direct recall card
            card = ReviewCard(
                id=uuid4(),
                front=f"What do you know about: {content[:100]}...?" if len(content) > 100 else f"Recall this fact:",
                back=content,
                context=f"Memory type: {memory_type}",
                source_type="memory",
                source_id=memory_id,
                namespace=namespace,
                state=ReviewState.NEW,
                tags=["memory", memory_type] + tags,
                created_at=_utc_now(),
                updated_at=_utc_now(),
            )
            cards.append(card)

        elif memory_type == "procedure":
            # Create a procedural card
            card = ReviewCard(
                id=uuid4(),
                front="How do you perform this procedure?",
                back=content,
                context=f"Memory type: {memory_type}",
                source_type="memory",
                source_id=memory_id,
                namespace=namespace,
                state=ReviewState.NEW,
                tags=["memory", memory_type] + tags,
                created_at=_utc_now(),
                updated_at=_utc_now(),
            )
            cards.append(card)

        return cards

    async def generate_from_entity(
        self,
        entity_id: str,
        entity_name: str,
        entity_type: str,
        description: str | None = None,
        relations: list[dict[str, str]] | None = None,
        namespace: str = "default",
        tags: list[str] | None = None,
    ) -> list[ReviewCard]:
        """Generate review cards from an entity.

        Args:
            entity_id: Entity ID
            entity_name: Name of the entity
            entity_type: Type (person, place, concept, etc.)
            description: Optional entity description
            relations: Related entities [{type, name}, ...]
            namespace: Namespace for the cards
            tags: Tags to add

        Returns:
            List of generated review cards
        """
        tags = tags or []
        cards: list[ReviewCard] = []

        # Card for entity definition
        if description:
            card = ReviewCard(
                id=uuid4(),
                front=f"What is {entity_name}?",
                back=description,
                context=f"Entity type: {entity_type}",
                source_type="entity",
                source_id=entity_id,
                namespace=namespace,
                state=ReviewState.NEW,
                tags=["entity", entity_type] + tags,
                created_at=_utc_now(),
                updated_at=_utc_now(),
            )
            cards.append(card)

        # Card for relations
        if relations and len(relations) > 0:
            relation_text = "\n".join(
                f"- {r['type']}: {r['name']}" for r in relations[:5]
            )
            card = ReviewCard(
                id=uuid4(),
                front=f"What are the key relationships of {entity_name}?",
                back=relation_text,
                context=f"Entity type: {entity_type}",
                source_type="entity",
                source_id=entity_id,
                namespace=namespace,
                state=ReviewState.NEW,
                tags=["entity", "relations", entity_type] + tags,
                created_at=_utc_now(),
                updated_at=_utc_now(),
            )
            cards.append(card)

        return cards

    def _parse_card_response(self, response: str) -> dict[str, str] | None:
        """Parse LLM response into card components.

        Args:
            response: Raw LLM response

        Returns:
            Dict with question, answer, context or None if parsing fails
        """
        # Check for "no content" responses
        if any(marker in response.upper() for marker in ["NO_DEFINITION", "NO_PROCEDURE", "NO_FACT"]):
            return None

        result: dict[str, str] = {}

        # Parse QUESTION:, ANSWER:, CONTEXT: format
        lines = response.strip().split("\n")
        current_key = None
        current_value: list[str] = []

        for line in lines:
            line = line.strip()
            if line.upper().startswith("QUESTION:"):
                if current_key and current_value:
                    result[current_key] = " ".join(current_value).strip()
                current_key = "question"
                current_value = [line[9:].strip()]
            elif line.upper().startswith("ANSWER:"):
                if current_key and current_value:
                    result[current_key] = " ".join(current_value).strip()
                current_key = "answer"
                current_value = [line[7:].strip()]
            elif line.upper().startswith("CONTEXT:"):
                if current_key and current_value:
                    result[current_key] = " ".join(current_value).strip()
                current_key = "context"
                current_value = [line[8:].strip()]
            elif current_key and line:
                current_value.append(line)

        # Save last section
        if current_key and current_value:
            result[current_key] = " ".join(current_value).strip()

        # Validate required fields
        if "question" in result and "answer" in result:
            return result

        return None

    async def batch_generate(
        self,
        items: list[dict[str, Any]],
        card_types: list[CardType] | None = None,
    ) -> list[ReviewCard]:
        """Generate cards from multiple items in batch.

        Args:
            items: List of dicts with source info
            card_types: Card types to generate

        Returns:
            All generated cards
        """
        all_cards: list[ReviewCard] = []

        for item in items:
            source_type = item.get("source_type", "chunk")

            if source_type == "chunk":
                cards = await self.generate_from_chunk(
                    chunk_id=item["id"],
                    content=item["content"],
                    document_id=item.get("document_id", ""),
                    document_title=item.get("document_title", ""),
                    namespace=item.get("namespace", "default"),
                    card_types=card_types,
                    tags=item.get("tags", []),
                )
            elif source_type == "memory":
                cards = await self.generate_from_memory(
                    memory_id=item["id"],
                    content=item["content"],
                    memory_type=item.get("memory_type", "fact"),
                    namespace=item.get("namespace", "default"),
                    tags=item.get("tags", []),
                )
            elif source_type == "entity":
                cards = await self.generate_from_entity(
                    entity_id=item["id"],
                    entity_name=item["name"],
                    entity_type=item.get("entity_type", "concept"),
                    description=item.get("description"),
                    relations=item.get("relations", []),
                    namespace=item.get("namespace", "default"),
                    tags=item.get("tags", []),
                )
            else:
                logger.warning("Unknown source type: %s", source_type)
                continue

            all_cards.extend(cards)

        logger.info("Generated %d cards from %d items", len(all_cards), len(items))
        return all_cards
