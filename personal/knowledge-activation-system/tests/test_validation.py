"""Tests for content validation."""

import pytest

from knowledge.validation import (
    ValidationError,
    ValidationResult,
    clean_content,
    estimate_reading_time,
    extract_title_from_content,
    validate_content,
)


class TestValidateContent:
    """Tests for validate_content function."""

    def test_valid_content(self):
        """Test validation of valid content."""
        content = "This is a valid piece of content. " * 10
        result = validate_content(content)

        assert result.valid is True
        assert result.error is None
        assert len(result.content) > 0

    def test_empty_content(self):
        """Test validation of empty content."""
        result = validate_content("")

        assert result.valid is False
        assert result.error == ValidationError.EMPTY

    def test_whitespace_only_content(self):
        """Test validation of whitespace-only content."""
        result = validate_content("   \n\t\n   ")

        assert result.valid is False
        assert result.error == ValidationError.EMPTY

    def test_too_short_content(self):
        """Test validation of too-short content."""
        result = validate_content("Short text")

        assert result.valid is False
        assert result.error == ValidationError.TOO_SHORT

    def test_custom_min_length(self):
        """Test validation with custom minimum length."""
        content = "This is a short but acceptable text."
        result = validate_content(content, min_length=10)

        assert result.valid is True

    def test_error_page_detection(self):
        """Test detection of error pages."""
        error_contents = [
            "404 Not Found - The page you requested could not be found.",
            "Error 500 - Internal Server Error occurred.",
            "We're sorry, something went wrong with your request.",
            "This page is not available. Please try again later.",
        ]

        for content in error_contents:
            # Make content long enough to pass length check
            padded = content + " Additional text. " * 10
            result = validate_content(padded)
            assert result.valid is False, f"Should detect error page: {content[:50]}"
            assert result.error == ValidationError.ERROR_PAGE

    def test_captcha_detection(self):
        """Test detection of CAPTCHA pages."""
        captcha_contents = [
            "Please verify that you're not a robot to continue.",
            "Unusual traffic detected. Complete the CAPTCHA below.",
            "Are you a robot? Please verify to access this page.",
        ]

        for content in captcha_contents:
            padded = content + " More content here. " * 10
            result = validate_content(padded)
            assert result.valid is False, f"Should detect CAPTCHA: {content[:50]}"
            assert result.error == ValidationError.CAPTCHA

    def test_login_required_detection(self):
        """Test detection of login-required pages."""
        login_contents = [
            "Please log in to continue reading this article.",
            "You must be logged in to view this content.",
            "Create an account to access this feature.",
        ]

        for content in login_contents:
            padded = content + " More content here. " * 10
            result = validate_content(padded)
            assert result.valid is False, f"Should detect login page: {content[:50]}"
            assert result.error == ValidationError.LOGIN_REQUIRED

    def test_paywall_warning(self):
        """Test paywall detection (warning, not error)."""
        paywall_content = (
            "Subscribe to continue reading this premium content. "
            "Our premium members get unlimited access. " * 10
        )

        result = validate_content(paywall_content)

        # Paywall is a warning, content should still be valid
        assert result.valid is True
        assert result.warning is not None
        assert "paywall" in result.warning.lower()


class TestCleanContent:
    """Tests for clean_content function."""

    def test_normalizes_line_endings(self):
        """Test that line endings are normalized."""
        content = "Line 1\r\nLine 2\rLine 3\nLine 4"
        cleaned = clean_content(content)

        assert "\r" not in cleaned
        assert cleaned.count("\n") == 3

    def test_removes_excessive_blank_lines(self):
        """Test that excessive blank lines are reduced."""
        content = "Line 1\n\n\n\n\nLine 2"
        cleaned = clean_content(content)

        assert "\n\n\n" not in cleaned
        assert "\n\n" in cleaned

    def test_normalizes_whitespace(self):
        """Test that whitespace is normalized."""
        content = "Multiple   spaces\tand\ttabs  here"
        cleaned = clean_content(content)

        assert "  " not in cleaned  # No double spaces
        assert "\t" not in cleaned  # No tabs

    def test_strips_content(self):
        """Test that content is stripped."""
        content = "  \n  Content here  \n  "
        cleaned = clean_content(content)

        assert cleaned == "Content here"


class TestEstimateReadingTime:
    """Tests for estimate_reading_time function."""

    def test_short_content(self):
        """Test reading time for short content."""
        content = "Word " * 100  # 100 words
        time = estimate_reading_time(content)

        assert time == 1  # Minimum 1 minute

    def test_medium_content(self):
        """Test reading time for medium content."""
        content = "Word " * 400  # 400 words
        time = estimate_reading_time(content)

        assert time == 2  # 400 / 200 = 2 minutes

    def test_long_content(self):
        """Test reading time for long content."""
        content = "Word " * 1000  # 1000 words
        time = estimate_reading_time(content)

        assert time == 5  # 1000 / 200 = 5 minutes

    def test_custom_wpm(self):
        """Test reading time with custom WPM."""
        content = "Word " * 400
        time = estimate_reading_time(content, words_per_minute=100)

        assert time == 4  # 400 / 100 = 4 minutes


class TestExtractTitleFromContent:
    """Tests for extract_title_from_content function."""

    def test_extract_markdown_heading(self):
        """Test extraction of markdown heading."""
        content = "# This is the Title\n\nSome content here."
        title = extract_title_from_content(content)

        assert title == "This is the Title"

    def test_extract_h2_heading(self):
        """Test extraction of h2 heading."""
        content = "## Secondary Title\n\nContent."
        title = extract_title_from_content(content)

        assert title == "Secondary Title"

    def test_extract_first_line_as_title(self):
        """Test extraction of first line as title."""
        content = "Short Title Line\n\nSome content follows."
        title = extract_title_from_content(content)

        assert title == "Short Title Line"

    def test_no_title_found(self):
        """Test when no title can be extracted."""
        content = "This is a very long sentence that continues on and on and would not make a good title because it exceeds the maximum length allowed."
        title = extract_title_from_content(content, max_length=50)

        # Should still return something
        assert title is None or len(title) <= 50

    def test_skip_empty_lines(self):
        """Test that empty lines are skipped."""
        content = "\n\n\n# Real Title\n\nContent."
        title = extract_title_from_content(content)

        assert title == "Real Title"


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_cleaned_content_for_valid(self):
        """Test cleaned_content property for valid result."""
        result = ValidationResult(valid=True, content="Some content")
        assert result.cleaned_content == "Some content"

    def test_cleaned_content_for_invalid(self):
        """Test cleaned_content property for invalid result."""
        result = ValidationResult(valid=False, content="Some content", error=ValidationError.TOO_SHORT)
        assert result.cleaned_content == ""
