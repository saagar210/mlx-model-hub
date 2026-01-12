"""Content validation for ingestion."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

import yaml


# Regex to match YAML frontmatter at the start of content
YAML_FRONTMATTER_PATTERN = re.compile(r'^---\n(.*?)\n---\n?', re.DOTALL)


class ValidationError(Enum):
    """Types of validation errors."""

    TOO_SHORT = "Content too short (minimum 100 characters)"
    EMPTY = "Content is empty"
    ERROR_PAGE = "Content appears to be an error page"
    PAYWALL = "Content appears to be behind a paywall"
    LOGIN_REQUIRED = "Content requires login"
    CAPTCHA = "Content blocked by CAPTCHA"


@dataclass
class ValidationResult:
    """Result of content validation."""

    valid: bool
    content: str
    error: ValidationError | None = None
    warning: str | None = None

    @property
    def cleaned_content(self) -> str:
        """Return cleaned content for valid results."""
        return self.content if self.valid else ""


# Patterns that indicate error/blocked pages
ERROR_PATTERNS = [
    r"404\s*(not\s*found|error|page)",
    r"403\s*(forbidden|access\s*denied)",
    r"500\s*(internal\s*server\s*error)",
    r"error\s*500",
    r"internal\s*server\s*error",
    r"page\s*(not\s*found|does\s*not\s*exist)",
    r"this\s*page\s*(is\s*not|isn.?t)\s*available",
    r"error\s*loading\s*(page|content)",
    r"something\s*went\s*wrong",
    r"we.?re\s*sorry.{0,50}(error|problem|issue)",
]

PAYWALL_PATTERNS = [
    r"subscribe\s*(to|now|today)\s*(continue|read|access)",
    r"premium\s*(content|access|member)",
    r"(this|full)\s*(article|content)\s*is\s*(for|available\s*to)\s*(subscribers|members)",
    r"sign\s*up\s*to\s*(read|continue|access)",
    r"free\s*trial",
    r"unlock\s*(this|full)\s*(article|content)",
]

LOGIN_PATTERNS = [
    r"(please\s*)?(log\s*in|sign\s*in)\s*to\s*(continue|view|access)",
    r"you\s*(must|need\s*to)\s*(be\s*)?(logged\s*in|sign\s*in)",
    r"create\s*an?\s*account\s*to\s*(continue|access)",
    r"authentication\s*required",
]

CAPTCHA_PATTERNS = [
    r"(are\s*you\s*a\s*)?robot",
    r"captcha",
    r"verify\s*(you.?re|that\s*you.?re)\s*(human|not\s*a\s*robot)",
    r"security\s*check",
    r"unusual\s*traffic",
]

# Compile patterns for efficiency
_error_regex = re.compile("|".join(ERROR_PATTERNS), re.IGNORECASE)
_paywall_regex = re.compile("|".join(PAYWALL_PATTERNS), re.IGNORECASE)
_login_regex = re.compile("|".join(LOGIN_PATTERNS), re.IGNORECASE)
_captcha_regex = re.compile("|".join(CAPTCHA_PATTERNS), re.IGNORECASE)


def validate_content(
    content: str,
    min_length: int = 100,
    url: str | None = None,
) -> ValidationResult:
    """
    Validate content for ingestion.

    Args:
        content: Raw content text to validate
        min_length: Minimum acceptable content length (default 100 chars)
        url: Optional URL for context in warnings

    Returns:
        ValidationResult with validation status and cleaned content
    """
    # Check for empty content
    if not content or not content.strip():
        return ValidationResult(
            valid=False,
            content="",
            error=ValidationError.EMPTY,
        )

    # Clean whitespace
    cleaned = clean_content(content)

    # Check minimum length
    if len(cleaned) < min_length:
        return ValidationResult(
            valid=False,
            content=cleaned,
            error=ValidationError.TOO_SHORT,
        )

    # Check for error pages (only check first 2000 chars for efficiency)
    check_text = cleaned[:2000].lower()

    if _captcha_regex.search(check_text):
        return ValidationResult(
            valid=False,
            content=cleaned,
            error=ValidationError.CAPTCHA,
        )

    if _error_regex.search(check_text):
        return ValidationResult(
            valid=False,
            content=cleaned,
            error=ValidationError.ERROR_PAGE,
        )

    if _login_regex.search(check_text):
        return ValidationResult(
            valid=False,
            content=cleaned,
            error=ValidationError.LOGIN_REQUIRED,
        )

    # Paywall is a warning, not a hard failure
    warning = None
    if _paywall_regex.search(check_text):
        # Still allow but warn - might have partial content
        warning = "Content may be partially blocked by paywall"

    return ValidationResult(
        valid=True,
        content=cleaned,
        warning=warning,
    )


def clean_content(content: str, strip_frontmatter: bool = True) -> str:
    """
    Clean content text.

    - Strips YAML frontmatter (optional, default True)
    - Normalizes whitespace
    - Removes excessive blank lines
    - Strips leading/trailing whitespace

    Args:
        content: Raw content text
        strip_frontmatter: Whether to strip YAML frontmatter (default True)

    Returns:
        Cleaned content text
    """
    # Strip YAML frontmatter if present
    if strip_frontmatter:
        content = strip_yaml_frontmatter(content)

    # Normalize line endings
    content = content.replace("\r\n", "\n").replace("\r", "\n")

    # Remove excessive blank lines (more than 2 consecutive)
    content = re.sub(r"\n{3,}", "\n\n", content)

    # Normalize whitespace within lines (but preserve single spaces)
    content = re.sub(r"[ \t]+", " ", content)

    # Strip lines
    lines = [line.strip() for line in content.split("\n")]
    content = "\n".join(lines)

    # Strip overall
    return content.strip()


def estimate_reading_time(content: str, words_per_minute: int = 200) -> int:
    """
    Estimate reading time in minutes.

    Args:
        content: Content text
        words_per_minute: Average reading speed (default 200)

    Returns:
        Estimated reading time in minutes
    """
    word_count = len(content.split())
    return max(1, round(word_count / words_per_minute))


def parse_yaml_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """
    Parse YAML frontmatter from content.

    YAML frontmatter is delimited by --- at the start of the file.
    Example:
        ---
        title: My Document
        tags: [a, b, c]
        ---

        Content here...

    Args:
        content: Raw content that may contain YAML frontmatter

    Returns:
        Tuple of (frontmatter_dict, content_without_frontmatter)
    """
    match = YAML_FRONTMATTER_PATTERN.match(content)
    if not match:
        return {}, content

    try:
        yaml_str = match.group(1)
        frontmatter = yaml.safe_load(yaml_str) or {}
        body = content[match.end():]
        return frontmatter, body.lstrip()
    except yaml.YAMLError:
        # If YAML parsing fails, return content as-is
        return {}, content


def strip_yaml_frontmatter(content: str) -> str:
    """
    Strip YAML frontmatter from content, returning only the body.

    Args:
        content: Content that may contain YAML frontmatter

    Returns:
        Content without frontmatter
    """
    _, body = parse_yaml_frontmatter(content)
    return body


def extract_title_from_content(content: str, max_length: int = 100) -> str | None:
    """
    Try to extract a title from content.

    Looks for (in order):
    1. YAML frontmatter 'title' field
    2. First markdown heading
    3. First line if it looks like a title

    Args:
        content: Content text
        max_length: Maximum title length

    Returns:
        Extracted title or None
    """
    # First try YAML frontmatter
    frontmatter, body = parse_yaml_frontmatter(content)
    if frontmatter.get('title'):
        title = str(frontmatter['title'])
        return title[:max_length]

    # Use body without frontmatter for heading search
    lines = body.split("\n")

    for line in lines[:10]:  # Check first 10 lines
        line = line.strip()
        if not line:
            continue

        # Check for markdown heading
        if line.startswith("#"):
            title = line.lstrip("#").strip()
            if title:
                return title[:max_length]

        # First non-empty line might be a title if it's short
        if len(line) <= max_length and not line.endswith((".", ":", ",", ";")):
            return line

    return None
