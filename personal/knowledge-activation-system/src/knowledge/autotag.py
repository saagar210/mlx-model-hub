"""Auto-tagging using LLM extraction."""

from __future__ import annotations

import re

from knowledge.ai import AIProvider
from knowledge.logging import get_logger

logger = get_logger(__name__)


TAGGING_PROMPT = """Extract 3-7 relevant tags from this content.

Requirements:
- Tags should be lowercase
- Multi-word tags should be hyphenated (e.g., "machine-learning")
- Each tag max 25 characters
- Return only comma-separated tags, nothing else
- Focus on: technologies, concepts, frameworks, languages, tools

Title: {title}
Content (first 2000 chars):
{content}

Tags:"""


async def extract_tags(
    title: str,
    content: str,
    ai: AIProvider | None = None,
) -> list[str]:
    """
    Extract tags from content using LLM.

    Args:
        title: Content title
        content: Content text (first 2000 chars will be used)
        ai: Optional AI provider instance

    Returns:
        List of 3-7 extracted tags, or empty list on failure
    """
    if ai is None:
        ai = AIProvider()

    prompt = TAGGING_PROMPT.format(
        title=title,
        content=content[:2000],
    )

    try:
        response = await ai.generate(
            prompt=prompt,
            temperature=0.3,  # Lower temperature for consistent tagging
            max_tokens=100,
        )

        if not response.success:
            logger.warning(
                "autotag_extraction_failed",
                error=response.error,
                title=title[:50],
            )
            return []

        # Parse comma-separated tags
        raw_tags = response.content.strip()
        tags = []

        for tag in raw_tags.split(","):
            # Clean up tag
            tag = tag.strip().lower()
            # Remove any quotes or brackets
            tag = re.sub(r'["\'\[\]()]', '', tag)
            # Replace spaces with hyphens
            tag = re.sub(r'\s+', '-', tag)
            # Remove any non-alphanumeric characters except hyphens
            tag = re.sub(r'[^a-z0-9-]', '', tag)
            # Truncate to 25 chars
            tag = tag[:25]
            # Remove leading/trailing hyphens
            tag = tag.strip('-')

            if tag and len(tag) >= 2:
                tags.append(tag)

        # Return 3-7 tags
        unique_tags = list(dict.fromkeys(tags))  # Preserve order, remove duplicates
        result = unique_tags[:7]

        logger.debug(
            "autotag_extraction_success",
            title=title[:50],
            tags=result,
        )

        return result

    except Exception as e:
        logger.error(
            "autotag_extraction_error",
            error=str(e),
            error_type=type(e).__name__,
            title=title[:50],
        )
        return []


async def suggest_tags(
    title: str,
    content: str,
    existing_tags: list[str] | None = None,
    ai: AIProvider | None = None,
) -> list[str]:
    """
    Suggest additional tags for content that already has some tags.

    Args:
        title: Content title
        content: Content text
        existing_tags: Tags already assigned to content
        ai: Optional AI provider instance

    Returns:
        List of suggested additional tags
    """
    existing = existing_tags or []

    # Extract all potential tags
    all_tags = await extract_tags(title, content, ai)

    # Return only tags not already assigned
    new_tags = [t for t in all_tags if t not in existing]

    return new_tags
