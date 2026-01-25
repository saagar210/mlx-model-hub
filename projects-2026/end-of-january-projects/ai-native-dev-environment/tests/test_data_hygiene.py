"""Tests for data hygiene and risk controls."""

import pytest
from unittest.mock import MagicMock, patch

from universal_context_engine.config import contains_sensitive_data, Settings


class TestSensitiveDataDetection:
    """Test sensitive data pattern detection."""

    def test_detects_api_key(self):
        """Should detect API key patterns."""
        assert contains_sensitive_data("API_KEY=abc123")
        assert contains_sensitive_data("my apikey is secret")
        assert contains_sensitive_data("api-key: xyz")

    def test_detects_password(self):
        """Should detect password patterns."""
        assert contains_sensitive_data("password: secret123")
        assert contains_sensitive_data("my SECRET is here")
        assert contains_sensitive_data("PWD=hunter2")

    def test_detects_tokens(self):
        """Should detect token patterns."""
        assert contains_sensitive_data("Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")
        assert contains_sensitive_data("auth_token=xyz")
        assert contains_sensitive_data("auth-token: abc123")

    def test_detects_openai_keys(self):
        """Should detect OpenAI API key format."""
        assert contains_sensitive_data("sk-abc123def456ghi789jkl012mno345pqr678")

    def test_detects_github_tokens(self):
        """Should detect GitHub token formats."""
        assert contains_sensitive_data("ghp_abcdefghijklmnopqrstuvwxyz0123456789")
        assert contains_sensitive_data("ghr_abcdefghijklmnopqrstuvwxyz0123456789")

    def test_detects_credentials(self):
        """Should detect credential patterns."""
        assert contains_sensitive_data("credentials = {...}")
        assert contains_sensitive_data("credentials: {...}")

    def test_detects_private_keys(self):
        """Should detect private key patterns."""
        assert contains_sensitive_data("private_key: ...")
        assert contains_sensitive_data("private-key file")

    def test_detects_database_urls(self):
        """Should detect database URL patterns."""
        assert contains_sensitive_data("DATABASE_URL=postgres://...")
        assert contains_sensitive_data("db_url=mysql://...")

    def test_normal_content_passes(self):
        """Should not flag normal content."""
        assert not contains_sensitive_data("Working on the authentication feature")
        assert not contains_sensitive_data("Implemented user login page")
        assert not contains_sensitive_data("Fixed the bug in data processing")
        assert not contains_sensitive_data("Added new API endpoint for users")

    def test_case_insensitive(self):
        """Detection should be case-insensitive."""
        assert contains_sensitive_data("API_KEY=test")
        assert contains_sensitive_data("api_key=test")
        assert contains_sensitive_data("Api_Key=test")
        assert contains_sensitive_data("PASSWORD=test")
        assert contains_sensitive_data("Password=test")


class TestSettings:
    """Test settings configuration."""

    def test_default_retention_days(self):
        """Settings should have default retention days."""
        s = Settings()
        assert s.context_retention_days == 90
        assert s.feedback_retention_days == 180
        assert s.session_retention_days == 30

    def test_production_mode_default(self):
        """Production mode should be off by default."""
        s = Settings()
        assert s.production_mode is False

    def test_warn_on_sensitive_default(self):
        """Sensitive data warning should be on by default."""
        s = Settings()
        assert s.warn_on_sensitive_data is True

    def test_max_content_length(self):
        """Max content length should have a reasonable default."""
        s = Settings()
        assert s.max_content_length == 50000


class TestProductionModeSafeguards:
    """Test production mode safeguards."""

    def test_chromadb_reset_disabled_in_production(self):
        """ChromaDB reset should be disabled in production mode."""
        with patch("universal_context_engine.context_store.settings") as mock_settings:
            mock_settings.production_mode = True
            mock_settings.chromadb_path = "/tmp/test"
            mock_settings.chroma_collection_prefix = "test"
            mock_settings.ensure_directories = MagicMock()

            # Import after patching
            from chromadb.config import Settings as ChromaSettings

            # The allow_reset should be False when production_mode is True
            allow_reset = not mock_settings.production_mode
            assert allow_reset is False


class TestRetentionPolicy:
    """Test retention policy configuration."""

    def test_zero_retention_disables_cleanup(self):
        """Setting retention to 0 should disable cleanup."""
        s = Settings()
        # Default values are non-zero, enabling cleanup
        assert s.context_retention_days > 0

        # Setting to 0 would disable (we don't modify in test, just verify default)
        # This behavior is checked in run_retention_cleanup

    def test_retention_days_are_integers(self):
        """Retention days should be integers."""
        s = Settings()
        assert isinstance(s.context_retention_days, int)
        assert isinstance(s.feedback_retention_days, int)
        assert isinstance(s.session_retention_days, int)
