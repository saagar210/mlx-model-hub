"""Content validation for ingestion (P16: Input Validation Enhancement)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from knowledge.exceptions import (
    InvalidFilepathError,
    InvalidNamespaceError,
    InvalidQueryError,
    InvalidURLError,
)

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


# =============================================================================
# URL Validation (P16)
# =============================================================================


# Patterns that indicate local/private networks
BLOCKED_URL_PATTERNS = [
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "192.168.",
    "10.",
    "172.16.", "172.17.", "172.18.", "172.19.",
    "172.20.", "172.21.", "172.22.", "172.23.",
    "172.24.", "172.25.", "172.26.", "172.27.",
    "172.28.", "172.29.", "172.30.", "172.31.",
    "169.254.",  # Link-local
    "[::1]",  # IPv6 localhost
    "[::]",  # IPv6 any
]

# Allowed URL schemes
ALLOWED_SCHEMES = {"http", "https"}


def validate_url(url: str, allow_private: bool = False, raise_on_error: bool = False) -> str | None:
    """
    Validate and sanitize a URL.

    Args:
        url: The URL to validate
        allow_private: Whether to allow private/local URLs (default False)
        raise_on_error: If True, raise InvalidURLError; if False, return None

    Returns:
        The validated URL, or None if invalid (when raise_on_error=False)

    Raises:
        InvalidURLError: If the URL is invalid or unsafe (only when raise_on_error=True)
    """
    def _fail(msg: str, details: dict | None = None) -> str | None:
        if raise_on_error:
            raise InvalidURLError(msg, details=details)
        return None

    if not url:
        return _fail("URL cannot be empty")

    url = url.strip()

    # Basic protocol check
    if not url.startswith(("http://", "https://")):
        return _fail("URL must start with http:// or https://")

    try:
        parsed = urlparse(url)
    except Exception as e:
        return _fail(f"Invalid URL format: {e}")

    # Validate scheme
    if parsed.scheme not in ALLOWED_SCHEMES:
        return _fail(f"Invalid URL scheme: {parsed.scheme}")

    # Validate host
    if not parsed.netloc:
        return _fail("URL must have a host")

    # Check for blocked patterns (SSRF protection)
    if not allow_private:
        host_lower = parsed.netloc.lower()
        for pattern in BLOCKED_URL_PATTERNS:
            if pattern in host_lower:
                return _fail(
                    "Local/private URLs not allowed",
                    details={"blocked_pattern": pattern},
                )

    # Check for suspicious characters
    if any(c in url for c in ["\x00", "\r", "\n", "\t"]):
        return _fail("URL contains invalid characters")

    return url


def is_url_safe(url: str) -> bool:
    """
    Check if URL is safe to fetch without raising exceptions.

    Args:
        url: The URL to check

    Returns:
        True if safe, False otherwise
    """
    try:
        validate_url(url)
        return True
    except InvalidURLError:
        return False


# =============================================================================
# Filepath Validation (P16)
# =============================================================================


# Characters not allowed in paths
FORBIDDEN_PATH_CHARS = set('\x00<>"|?*')


def validate_filepath(
    filepath: str,
    base_dir: Path | None = None,
    allow_absolute: bool = False,
    raise_on_error: bool = False,
) -> Path | None:
    """
    Validate and normalize a filepath.

    Args:
        filepath: The path to validate
        base_dir: Optional base directory for relative path resolution
        allow_absolute: Whether to allow absolute paths (default False)
        raise_on_error: If True, raise InvalidFilepathError; if False, return None

    Returns:
        The validated Path object, or None if invalid (when raise_on_error=False)

    Raises:
        InvalidFilepathError: If the path is invalid or unsafe (only when raise_on_error=True)
    """
    def _fail(msg: str) -> Path | None:
        if raise_on_error:
            raise InvalidFilepathError(msg)
        return None

    if not filepath:
        return _fail("Filepath cannot be empty")

    filepath = filepath.strip()

    # Check for URL-encoded traversal patterns
    if "%2e" in filepath.lower() or "%2f" in filepath.lower():
        return _fail("URL-encoded path characters not allowed")

    # Check for forbidden characters
    if any(c in filepath for c in FORBIDDEN_PATH_CHARS):
        return _fail("Filepath contains invalid characters")

    # Check for null bytes
    if "\x00" in filepath:
        return _fail("Filepath contains null byte")

    # Check for file:// protocol
    if filepath.lower().startswith("file:"):
        return _fail("file:// protocol not allowed")

    # Check for UNC paths (Windows network paths)
    if filepath.startswith("\\\\"):
        return _fail("UNC paths not allowed")

    path = Path(filepath)

    # Check for absolute paths
    if path.is_absolute() and not allow_absolute:
        return _fail("Absolute paths not allowed")

    # Check for path traversal (including normalized paths)
    normalized = str(path)
    if ".." in normalized:
        return _fail("Path traversal not allowed")

    # If base_dir specified, ensure path stays within it
    if base_dir:
        base_resolved = base_dir.resolve()
        try:
            full_path = (base_dir / path).resolve()
            if not str(full_path).startswith(str(base_resolved)):
                return _fail("Path escapes base directory")
        except Exception as e:
            return _fail(f"Invalid path resolution: {e}")

    return path


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize a filename by removing dangerous characters.

    Args:
        filename: The filename to sanitize
        max_length: Maximum length for the filename

    Returns:
        Sanitized filename
    """
    if not filename:
        return "unnamed"

    # Remove path separators
    filename = filename.replace("/", "_").replace("\\", "_")

    # Remove dangerous characters
    filename = re.sub(r'[<>:"|?*\x00-\x1f]', "", filename)

    # Remove leading/trailing dots and spaces
    filename = filename.strip(". ")

    # Truncate if too long
    if len(filename) > max_length:
        # Preserve extension
        parts = filename.rsplit(".", 1)
        if len(parts) == 2 and len(parts[1]) < 10:
            name, ext = parts
            filename = name[: max_length - len(ext) - 1] + "." + ext
        else:
            filename = filename[:max_length]

    return filename or "unnamed"


# =============================================================================
# Namespace Validation (P16)
# =============================================================================


# Valid namespace pattern: alphanumeric, dash, underscore, asterisk for wildcard
NAMESPACE_PATTERN = re.compile(r"^[\w\-*]{1,100}$")


def validate_namespace(namespace: str | None, raise_on_error: bool = False) -> str | None:
    """
    Validate a namespace string.

    Args:
        namespace: The namespace to validate (can be None)
        raise_on_error: If True, raise InvalidNamespaceError; if False, return None

    Returns:
        The validated namespace or None

    Raises:
        InvalidNamespaceError: If the namespace format is invalid (only when raise_on_error=True)
    """
    if namespace is None:
        return None

    namespace = namespace.strip()

    if not namespace:
        return None

    # Check for null bytes
    if "\x00" in namespace:
        if raise_on_error:
            raise InvalidNamespaceError("Namespace contains null byte")
        return None

    # Check for path traversal
    if ".." in namespace:
        if raise_on_error:
            raise InvalidNamespaceError("Path traversal not allowed in namespace")
        return None

    # Check for dangerous patterns (SQL injection, XSS)
    dangerous_patterns = ["<", ">", ";", "'", '"', "DROP", "SELECT", "DELETE", "UPDATE", "INSERT"]
    namespace_upper = namespace.upper()
    for pattern in dangerous_patterns:
        if pattern in namespace or pattern in namespace_upper:
            if raise_on_error:
                raise InvalidNamespaceError("Namespace contains dangerous characters")
            return None

    # Check length
    if len(namespace) > 100:
        if raise_on_error:
            raise InvalidNamespaceError("Namespace too long (max 100 characters)")
        return None

    if not NAMESPACE_PATTERN.match(namespace):
        if raise_on_error:
            raise InvalidNamespaceError(
                "Invalid namespace format - use alphanumeric, dash, underscore, or wildcard (*)",
                details={"namespace": namespace[:50]},
            )
        return None

    return namespace


# =============================================================================
# Query Validation (P16)
# =============================================================================


def validate_search_query(
    query: str,
    min_length: int = 1,
    max_length: int = 1000,
) -> str:
    """
    Validate and sanitize a search query.

    Args:
        query: The search query to validate
        min_length: Minimum query length
        max_length: Maximum query length

    Returns:
        The validated and sanitized query

    Raises:
        InvalidQueryError: If the query is invalid
    """
    if not query:
        raise InvalidQueryError("Query cannot be empty")

    # Normalize whitespace
    query = " ".join(query.split())

    if len(query) < min_length:
        raise InvalidQueryError(
            f"Query too short (minimum {min_length} characters)",
            details={"length": len(query), "min_length": min_length},
        )

    if len(query) > max_length:
        raise InvalidQueryError(
            f"Query too long (maximum {max_length} characters)",
            details={"length": len(query), "max_length": max_length},
        )

    return query


def sanitize_query(query: str, max_length: int = 1000) -> str:
    """
    Sanitize a search query for safe database usage.

    This function always returns a sanitized string (never raises).
    For validation with errors, use validate_search_query instead.

    Args:
        query: The search query to sanitize
        max_length: Maximum query length (excess truncated)

    Returns:
        A sanitized query string
    """
    if not query:
        return ""

    # Normalize whitespace
    query = " ".join(query.split())

    # Truncate if too long
    if len(query) > max_length:
        query = query[:max_length]

    # Remove null bytes
    query = query.replace("\x00", "")

    return query


# =============================================================================
# Tag Validation (P16)
# =============================================================================


TAG_PATTERN = re.compile(r"^[\w\-]{1,50}$")


def validate_tag(tag: str) -> str:
    """
    Validate and sanitize a single tag.

    Args:
        tag: The tag to validate

    Returns:
        The sanitized tag

    Raises:
        ValueError: If the tag is invalid
    """
    tag = tag.strip().lower()

    if not tag:
        raise ValueError("Tag cannot be empty")

    # Remove invalid characters
    sanitized = re.sub(r"[^\w\-]", "", tag)

    # Truncate if too long
    sanitized = sanitized[:50]

    if not sanitized:
        raise ValueError("Tag contains no valid characters")

    return sanitized


def validate_tags(
    tags: list[str],
    max_count: int = 50,
) -> list[str]:
    """
    Validate and sanitize a list of tags.

    Args:
        tags: The list of tags to validate
        max_count: Maximum number of tags allowed

    Returns:
        List of sanitized, unique tags
    """
    validated = []
    seen = set()

    for tag in tags:
        try:
            sanitized = validate_tag(tag)
            if sanitized not in seen:
                validated.append(sanitized)
                seen.add(sanitized)
        except ValueError:
            # Skip invalid tags silently
            continue

        if len(validated) >= max_count:
            break

    return validated


# =============================================================================
# Content Size Validation (P16)
# =============================================================================


def validate_content_size(
    content: str | bytes,
    max_size: int,
    name: str = "content",
) -> None:
    """
    Validate that content doesn't exceed size limit.

    Args:
        content: The content to check
        max_size: Maximum allowed size in bytes
        name: Name for error messages

    Raises:
        ValueError: If content exceeds size limit
    """
    if isinstance(content, str):
        size = len(content.encode("utf-8"))
    else:
        size = len(content)

    if size > max_size:
        raise ValueError(
            f"{name} exceeds maximum size ({size:,} bytes > {max_size:,} bytes)"
        )
