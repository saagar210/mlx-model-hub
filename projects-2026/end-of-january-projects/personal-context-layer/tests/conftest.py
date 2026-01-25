"""Pytest configuration and fixtures."""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_vault(tmp_path: Path) -> Path:
    """Create a temporary Obsidian vault for testing."""
    vault = tmp_path / "TestVault"
    vault.mkdir()

    # Create some test notes
    knowledge = vault / "Knowledge"
    knowledge.mkdir()

    notes = knowledge / "Notes"
    notes.mkdir()

    # Note 1: With frontmatter
    (notes / "authentication.md").write_text(
        """---
title: Authentication Approaches
tags: [security, auth]
---

# Authentication Approaches

This note covers different authentication methods.

## OAuth 2.0

OAuth is a delegated authorization framework.

## JWT Tokens

JSON Web Tokens are used for stateless authentication.

See also: [[session-management]]
"""
    )

    # Note 2: Simple note
    (notes / "session-management.md").write_text(
        """---
title: Session Management
tags: [security]
---

# Session Management

How to manage user sessions securely.

Links back to [[authentication]]
"""
    )

    # Note 3: Project note
    projects = knowledge / "Projects"
    projects.mkdir()

    (projects / "personal-context-layer.md").write_text(
        """---
title: Personal Context Layer
tags: [project, mcp]
created: 2025-01-20
---

# Personal Context Layer Project

Building a unified MCP server for personal knowledge.

## Goals

- Search across Obsidian, Git, KAS
- Aggregate tools for cross-source queries
"""
    )

    return vault
