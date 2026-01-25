"""LLM-based summarization for session context using Ollama."""

from .config import settings
from .embedding import generate_client
from .models import SessionCapture


async def summarize_session(capture: SessionCapture) -> str:
    """Summarize a development session using local LLM.

    Args:
        capture: The session capture data to summarize.

    Returns:
        A 2-3 sentence summary of the session.
    """
    # Build a concise prompt for summarization
    files_str = ", ".join(capture.files_modified[:10]) if capture.files_modified else "none"
    decisions_str = "\n".join(f"- {d}" for d in capture.key_decisions[:5]) if capture.key_decisions else "none"
    errors_str = "\n".join(f"- {e}" for e in capture.errors_encountered[:3]) if capture.errors_encountered else "none"

    prompt = f"""Summarize this development session in 2-3 concise sentences. Focus on what was accomplished and any important decisions or blockers.

Project: {capture.project_path or "Unknown"}
Branch: {capture.git_branch or "Unknown"}
Files Modified: {files_str}
Key Decisions:
{decisions_str}
Errors Encountered:
{errors_str}

Conversation Excerpt:
{capture.conversation_excerpt[:2000] if capture.conversation_excerpt else "No conversation recorded"}

Summary:"""

    system = "You are a helpful assistant that creates brief, accurate summaries of development sessions. Be concise and focus on the key accomplishments, decisions, and any blockers."

    try:
        summary = await generate_client.generate(prompt, system=system)
        return summary.strip()
    except Exception as e:
        # Fallback to a simple summary if LLM fails
        parts = []
        if capture.files_modified:
            parts.append(f"Modified {len(capture.files_modified)} files")
        if capture.key_decisions:
            parts.append(f"made {len(capture.key_decisions)} decisions")
        if capture.errors_encountered:
            parts.append(f"encountered {len(capture.errors_encountered)} errors")

        if parts:
            return f"Session on {capture.project_path or 'project'}: {', '.join(parts)}."
        return f"Development session on {capture.project_path or 'project'} (summary generation failed: {e})"


async def extract_decisions(conversation: str) -> list[str]:
    """Extract key decisions from a conversation excerpt.

    Args:
        conversation: The conversation text to analyze.

    Returns:
        List of extracted decisions.
    """
    if not conversation or len(conversation) < 50:
        return []

    prompt = f"""Extract any architectural or technical decisions made in this conversation.
Return each decision on a new line, starting with "- ".
If no clear decisions were made, return "NONE".

Conversation:
{conversation[:3000]}

Decisions:"""

    system = "You extract clear, actionable technical decisions from conversations. Be concise - one line per decision."

    try:
        response = await generate_client.generate(prompt, system=system)
        if "NONE" in response.upper():
            return []

        decisions = []
        for line in response.strip().split("\n"):
            line = line.strip()
            if line.startswith("- "):
                decisions.append(line[2:])
            elif line and not line.startswith("#"):
                decisions.append(line)
        return decisions[:10]  # Limit to 10 decisions
    except Exception:
        return []


async def generate_blocker_summary(blocker: str, context: str | None = None) -> str:
    """Generate a clear summary of a blocker for later reference.

    Args:
        blocker: Description of the blocker.
        context: Optional additional context.

    Returns:
        A clear, actionable summary of the blocker.
    """
    if len(blocker) < 20:
        return blocker

    prompt = f"""Rewrite this blocker description to be clear, specific, and actionable.
Keep it to 1-2 sentences.

Blocker: {blocker}
{f"Context: {context}" if context else ""}

Clear summary:"""

    system = "You help developers by creating clear, actionable descriptions of blockers and issues."

    try:
        summary = await generate_client.generate(prompt, system=system)
        return summary.strip()
    except Exception:
        return blocker
