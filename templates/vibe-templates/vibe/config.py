"""Configuration and template definitions."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TemplateConfig:
    """Configuration for a project template."""

    name: str
    description: str
    destination: str  # Relative to ~/claude-code/
    stack: list[str]
    commands: list[str] = field(default_factory=list)
    optional_features: list[str] = field(default_factory=list)


TEMPLATES: dict[str, TemplateConfig] = {
    "python-api": TemplateConfig(
        name="python-api",
        description="FastAPI backend with uvicorn and pydantic",
        destination="personal",
        stack=["fastapi", "uvicorn", "pydantic", "pydantic-settings"],
        commands=["run", "add-endpoint"],
        optional_features=["docker", "tests", "ci"],
    ),
    "python-ml": TemplateConfig(
        name="python-ml",
        description="MLX + Gradio app for Apple Silicon ML",
        destination="ai-tools",
        stack=["mlx", "mlx-lm", "gradio"],
        commands=["run", "add-model"],
        optional_features=["docker", "tests"],
    ),
    "nextjs": TemplateConfig(
        name="nextjs",
        description="Next.js 14+ with App Router and TypeScript",
        destination="personal",
        stack=["next", "react", "typescript", "tailwindcss"],
        commands=["dev", "add-page"],
        optional_features=["docker", "tests", "ci"],
    ),
    "fullstack": TemplateConfig(
        name="fullstack",
        description="Python API backend + Next.js frontend",
        destination="personal",
        stack=["fastapi", "next", "docker-compose"],
        commands=["dev", "add-endpoint", "add-page"],
        optional_features=["docker", "tests", "ci"],
    ),
}


def get_claude_code_root() -> Path:
    """Get the claude-code root directory."""
    return Path.home() / "claude-code"


def get_template_dir() -> Path:
    """Get the templates directory."""
    return Path(__file__).parent / "templates"
