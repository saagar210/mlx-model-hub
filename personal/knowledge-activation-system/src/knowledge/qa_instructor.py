"""Q&A with structured confidence scoring using Instructor.

This module provides structured Q&A capabilities with:
- Confidence scores (0.0-1.0) with automatic level classification
- Citation tracking to source chunks
- Reasoning explanation for transparency
- Graceful handling of unanswerable questions
"""

from __future__ import annotations

import os
from typing import Literal

import instructor
from pydantic import BaseModel, Field, model_validator

from knowledge.search import SearchResult


class Citation(BaseModel):
    """A citation to a source chunk."""

    content_id: str = Field(description="UUID of the source content")
    title: str = Field(description="Title of the source content")
    chunk_text: str = Field(description="Relevant text excerpt", max_length=500)
    relevance_score: float = Field(
        ge=0.0, le=1.0,
        description="How relevant this citation is to the answer"
    )


class QAResponse(BaseModel):
    """Structured Q&A response with confidence scoring."""

    answer: str = Field(
        min_length=1,
        description="The answer to the question based on retrieved context"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence score from 0.0 (no confidence) to 1.0 (certain)"
    )
    confidence_level: Literal["low", "medium", "high"] = Field(
        description="Categorical confidence level"
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description="Sources used to generate the answer"
    )
    reasoning: str = Field(
        description="Explanation of how the answer was derived"
    )
    unanswerable: bool = Field(
        default=False,
        description="True if the question cannot be answered from the context"
    )

    @model_validator(mode="after")
    def validate_confidence_consistency(self) -> "QAResponse":
        """Ensure confidence_level matches confidence score."""
        if self.confidence < 0.3:
            expected_level = "low"
        elif self.confidence < 0.7:
            expected_level = "medium"
        else:
            expected_level = "high"

        if self.confidence_level != expected_level:
            self.confidence_level = expected_level

        return self


class SimpleAnswer(BaseModel):
    """Simplified answer for quick responses."""

    answer: str = Field(description="Direct answer to the question")
    confidence: float = Field(ge=0.0, le=1.0)


def get_instructor_client(
    model: str = "ollama/qwen2.5:7b",
    base_url: str | None = None,
) -> instructor.Instructor:
    """Get an Instructor client configured for the specified model.

    Args:
        model: Model identifier (e.g., "ollama/qwen2.5:7b", "ollama/deepseek-r1:14b")
        base_url: Optional base URL for the API

    Returns:
        Configured Instructor client
    """
    # Use environment variable or default
    if base_url is None:
        base_url = os.environ.get("KNOWLEDGE_OLLAMA_URL", "http://localhost:11434")

    # Create client using from_provider for Ollama
    client = instructor.from_provider(
        model,
        mode=instructor.Mode.JSON,
    )

    return client


def format_context(search_results: list[SearchResult], max_chunks: int = 5) -> str:
    """Format search results into context for the LLM.

    Args:
        search_results: List of SearchResult from hybrid search
        max_chunks: Maximum number of chunks to include

    Returns:
        Formatted context string
    """
    context_parts = []

    for i, result in enumerate(search_results[:max_chunks]):
        chunk_text = result.chunk_text or "(No excerpt available)"
        context_parts.append(
            f"[Source {i+1}: {result.title} (score: {result.score:.3f})]\n"
            f"{chunk_text}\n"
        )

    return "\n---\n".join(context_parts)


async def answer_question(
    question: str,
    search_results: list[SearchResult],
    model: str = "ollama/qwen2.5:7b",
    max_context_chunks: int = 5,
) -> QAResponse:
    """Answer a question using retrieved context with confidence scoring.

    Args:
        question: The user's question
        search_results: Results from hybrid search
        model: LLM model to use
        max_context_chunks: Maximum chunks to include in context

    Returns:
        QAResponse with answer, confidence, citations, and reasoning
    """
    client = get_instructor_client(model)

    # Format context from search results
    context = format_context(search_results, max_context_chunks)

    # Build prompt
    system_prompt = """You are a helpful assistant that answers questions based on provided context.

Your task is to:
1. Answer the question using ONLY the provided context
2. Provide a confidence score (0.0-1.0) based on how well the context supports your answer
3. List citations from the context you used
4. Explain your reasoning
5. If the context doesn't contain relevant information, set unanswerable=true

Confidence scoring guide:
- 0.0-0.3 (low): Context barely mentions the topic or answer is speculative
- 0.3-0.7 (medium): Context provides partial information or indirect support
- 0.7-1.0 (high): Context directly and clearly answers the question"""

    user_prompt = f"""Context:
{context}

Question: {question}

Provide a structured response with your answer, confidence score, citations, and reasoning."""

    # Get structured response
    response = client.chat.completions.create(
        model=model.split("/")[-1],  # Extract model name for Ollama
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_model=QAResponse,
        max_retries=2,
    )

    return response


async def quick_answer(
    question: str,
    search_results: list[SearchResult],
    model: str = "ollama/qwen2.5:7b",
) -> SimpleAnswer:
    """Get a quick answer without full citation tracking.

    Args:
        question: The user's question
        search_results: Results from hybrid search
        model: LLM model to use

    Returns:
        SimpleAnswer with just answer and confidence
    """
    client = get_instructor_client(model)

    context = format_context(search_results, max_chunks=3)

    response = client.chat.completions.create(
        model=model.split("/")[-1],
        messages=[
            {
                "role": "system",
                "content": "Answer the question based on the context. "
                          "Provide confidence 0.0-1.0 based on context support.",
            },
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {question}",
            },
        ],
        response_model=SimpleAnswer,
        max_retries=2,
    )

    return response


def should_show_warning(response: QAResponse | SimpleAnswer) -> bool:
    """Check if a low confidence warning should be shown.

    Args:
        response: QA response to check

    Returns:
        True if confidence is below threshold (0.3)
    """
    return response.confidence < 0.3


def format_response_with_warning(response: QAResponse) -> str:
    """Format a QA response with optional low confidence warning.

    Args:
        response: QA response to format

    Returns:
        Formatted string with answer and optional warning
    """
    output_parts = []

    # Add warning banner if low confidence
    if should_show_warning(response):
        output_parts.append(
            "⚠️  LOW CONFIDENCE WARNING\n"
            "The retrieved context may not fully support this answer.\n"
            "Consider searching with different terms or verifying independently.\n"
        )

    # Add answer
    output_parts.append(f"**Answer:** {response.answer}\n")

    # Add confidence
    confidence_emoji = "🟢" if response.confidence >= 0.7 else "🟡" if response.confidence >= 0.3 else "🔴"
    output_parts.append(
        f"**Confidence:** {confidence_emoji} {response.confidence:.0%} ({response.confidence_level})\n"
    )

    # Add reasoning
    output_parts.append(f"**Reasoning:** {response.reasoning}\n")

    # Add citations
    if response.citations:
        output_parts.append("\n**Sources:**")
        for i, citation in enumerate(response.citations, 1):
            output_parts.append(
                f"\n{i}. {citation.title} (relevance: {citation.relevance_score:.0%})\n"
                f"   \"{citation.chunk_text[:100]}...\""
            )

    return "\n".join(output_parts)
