"""Intent classification for natural language routing."""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from ..embedding import generate_client


class IntentType(str, Enum):
    """Types of intents that can be classified."""

    RESEARCH = "research"
    RECALL = "recall"
    KNOWLEDGE = "knowledge"
    DECOMPOSE = "decompose"
    DEBUG = "debug"
    SAVE = "save"
    UNKNOWN = "unknown"


@dataclass
class Intent:
    """Classified intent from user text."""

    type: IntentType
    confidence: float
    extracted_topic: str | None = None
    extracted_params: dict[str, Any] | None = None
    reasoning: str | None = None


# Pattern-based classification rules
INTENT_PATTERNS: dict[IntentType, list[str]] = {
    IntentType.RESEARCH: [
        "research",
        "learn about",
        "find out",
        "explore",
        "investigate",
        "look into",
        "what is",
        "how does",
        "explain",
    ],
    IntentType.RECALL: [
        "what was i",
        "yesterday",
        "last time",
        "previous session",
        "what did i",
        "remind me",
        "what happened",
        "last session",
        "continue",
        "pick up where",
    ],
    IntentType.KNOWLEDGE: [
        "search",
        "find",
        "look up",
        "where is",
        "how to",
        "documentation",
        "docs",
        "reference",
    ],
    IntentType.DECOMPOSE: [
        "break down",
        "decompose",
        "plan",
        "steps to",
        "how should i",
        "subtasks",
        "breakdown",
        "divide",
        "split into",
    ],
    IntentType.DEBUG: [
        "error",
        "not working",
        "fix",
        "bug",
        "issue",
        "problem",
        "failing",
        "broken",
        "crash",
        "exception",
    ],
    IntentType.SAVE: [
        "remember",
        "save",
        "store",
        "keep track",
        "note",
        "record",
        "capture",
    ],
}


class IntentClassifier:
    """Classifies natural language text into intents."""

    def __init__(self):
        self._generate_client = generate_client

    def classify_by_patterns(self, text: str) -> Intent | None:
        """Classify intent using pattern matching.

        Args:
            text: The input text to classify.

        Returns:
            Intent if a pattern matches with high confidence, None otherwise.
        """
        text_lower = text.lower()

        for intent_type, patterns in INTENT_PATTERNS.items():
            for pattern in patterns:
                if pattern in text_lower:
                    # Extract potential topic (text after the pattern)
                    idx = text_lower.find(pattern)
                    topic = text[idx + len(pattern):].strip()
                    # Clean up common prefixes
                    for prefix in ["about ", "for ", "the ", "a ", "an "]:
                        if topic.lower().startswith(prefix):
                            topic = topic[len(prefix):]

                    return Intent(
                        type=intent_type,
                        confidence=0.85,
                        extracted_topic=topic if topic else None,
                        reasoning=f"Pattern match: '{pattern}'",
                    )

        return None

    async def classify_by_llm(self, text: str) -> Intent:
        """Classify intent using LLM for ambiguous cases.

        Args:
            text: The input text to classify.

        Returns:
            Classified Intent.
        """
        prompt = f"""Classify this request into one of these intent categories:
- RESEARCH: User wants to learn about or investigate a topic
- RECALL: User wants to remember what they worked on previously
- KNOWLEDGE: User wants to search for information or documentation
- DECOMPOSE: User wants to break down a task into steps
- DEBUG: User is dealing with an error or bug
- SAVE: User wants to save or record information
- UNKNOWN: Request doesn't fit any category

Request: "{text}"

Respond with JSON:
{{"intent": "CATEGORY", "topic": "extracted topic or null", "confidence": 0.0-1.0, "reasoning": "brief explanation"}}"""

        try:
            response = await self._generate_client.generate(
                prompt,
                system="You classify user requests into intent categories. Respond only with valid JSON.",
            )

            # Try to parse JSON response
            import json
            # Clean up response - find JSON
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]

            data = json.loads(response)

            intent_str = data.get("intent", "UNKNOWN").upper()
            try:
                intent_type = IntentType(intent_str.lower())
            except ValueError:
                intent_type = IntentType.UNKNOWN

            return Intent(
                type=intent_type,
                confidence=float(data.get("confidence", 0.5)),
                extracted_topic=data.get("topic"),
                reasoning=data.get("reasoning"),
            )
        except Exception as e:
            # Fallback to unknown
            return Intent(
                type=IntentType.UNKNOWN,
                confidence=0.3,
                reasoning=f"LLM classification failed: {e}",
            )

    async def classify(self, text: str) -> Intent:
        """Classify intent using patterns first, then LLM fallback.

        Args:
            text: The input text to classify.

        Returns:
            Classified Intent.
        """
        # Try pattern matching first
        pattern_intent = self.classify_by_patterns(text)
        if pattern_intent and pattern_intent.confidence >= 0.8:
            return pattern_intent

        # Fall back to LLM for ambiguous cases
        return await self.classify_by_llm(text)


# Default classifier instance
_classifier = IntentClassifier()


async def classify_intent(text: str) -> Intent:
    """Classify the intent of a natural language request.

    Args:
        text: The request text to classify.

    Returns:
        Classified Intent with type, confidence, and extracted parameters.
    """
    return await _classifier.classify(text)
