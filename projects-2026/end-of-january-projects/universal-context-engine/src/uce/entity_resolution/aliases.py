"""
Entity alias registry.

Maps alternative names to canonical entity names.
"""

from typing import ClassVar


class AliasRegistry:
    """
    Registry for entity aliases.

    Provides bidirectional mapping between aliases and canonical names.
    """

    # Built-in technology aliases
    _builtin_aliases: ClassVar[dict[str, str]] = {
        # Knowledge Engine variants
        "ke": "knowledge_engine",
        "kas": "knowledge_activation_system",
        "knowledge-engine": "knowledge_engine",
        "knowledge engine": "knowledge_engine",
        "knowledge-activation-system": "knowledge_activation_system",
        "knowledge activation system": "knowledge_activation_system",

        # Authentication
        "oauth2": "oauth",
        "oauth 2.0": "oauth",
        "oauth2.0": "oauth",
        "jwt": "jwt",
        "json web token": "jwt",
        "json web tokens": "jwt",
        "bearer token": "bearer_token",

        # Tools
        "cc": "claude_code",
        "claude-code": "claude_code",
        "claude code": "claude_code",

        # Databases
        "pg": "postgresql",
        "postgres": "postgresql",
        "postgresql": "postgresql",
        "psql": "postgresql",
        "neo4j": "neo4j",
        "qdrant": "qdrant",
        "mongo": "mongodb",
        "mongodb": "mongodb",
        "redis": "redis",
        "sqlite": "sqlite",
        "sqlite3": "sqlite",

        # Frameworks & Libraries
        "fastapi": "fastapi",
        "fast-api": "fastapi",
        "nextjs": "nextjs",
        "next.js": "nextjs",
        "next js": "nextjs",
        "crewai": "crewai",
        "crew-ai": "crewai",
        "crew ai": "crewai",
        "langchain": "langchain",
        "lang-chain": "langchain",
        "llamaindex": "llamaindex",
        "llama-index": "llamaindex",
        "llama index": "llamaindex",
        "react": "react",
        "reactjs": "react",
        "react.js": "react",
        "vue": "vue",
        "vuejs": "vue",
        "vue.js": "vue",
        "angular": "angular",
        "angularjs": "angular",
        "svelte": "svelte",
        "django": "django",
        "flask": "flask",
        "express": "express",
        "expressjs": "express",
        "express.js": "express",

        # Languages
        "ts": "typescript",
        "typescript": "typescript",
        "js": "javascript",
        "javascript": "javascript",
        "py": "python",
        "python": "python",
        "python3": "python",
        "rs": "rust",
        "rust": "rust",
        "go": "go",
        "golang": "go",

        # AI/ML
        "openai": "openai",
        "open-ai": "openai",
        "open ai": "openai",
        "anthropic": "anthropic",
        "claude": "claude",
        "gpt": "gpt",
        "gpt-4": "gpt4",
        "gpt4": "gpt4",
        "gpt-3.5": "gpt35",
        "llm": "llm",
        "llms": "llm",
        "rag": "rag",
        "graphrag": "graphrag",
        "graph-rag": "graphrag",
        "graph rag": "graphrag",

        # Infrastructure
        "docker": "docker",
        "k8s": "kubernetes",
        "kubernetes": "kubernetes",
        "aws": "aws",
        "amazon web services": "aws",
        "gcp": "gcp",
        "google cloud": "gcp",
        "azure": "azure",
        "vercel": "vercel",

        # Tools
        "git": "git",
        "github": "github",
        "gh": "github",
        "gitlab": "gitlab",
        "vscode": "vscode",
        "vs code": "vscode",
        "visual studio code": "vscode",
        "cursor": "cursor",
        "ollama": "ollama",
        "mcp": "mcp",
        "model context protocol": "mcp",
    }

    def __init__(self) -> None:
        """Initialize with built-in aliases."""
        self._aliases: dict[str, str] = dict(self._builtin_aliases)
        self._reverse: dict[str, list[str]] = {}
        self._build_reverse_index()

    def _build_reverse_index(self) -> None:
        """Build reverse index from canonical to aliases."""
        self._reverse.clear()
        for alias, canonical in self._aliases.items():
            if canonical not in self._reverse:
                self._reverse[canonical] = []
            self._reverse[canonical].append(alias)

    def add_alias(self, alias: str, canonical: str) -> None:
        """Add a new alias mapping."""
        normalized = alias.lower().strip()
        self._aliases[normalized] = canonical
        if canonical not in self._reverse:
            self._reverse[canonical] = []
        if normalized not in self._reverse[canonical]:
            self._reverse[canonical].append(normalized)

    def resolve(self, name: str) -> str:
        """
        Resolve an alias to its canonical name.

        Returns the original name if no alias is found.
        """
        normalized = name.lower().strip()
        return self._aliases.get(normalized, normalized)

    def get_aliases(self, canonical: str) -> list[str]:
        """Get all aliases for a canonical name."""
        return self._reverse.get(canonical, [])

    def has_alias(self, name: str) -> bool:
        """Check if a name has an alias mapping."""
        return name.lower().strip() in self._aliases

    def all_aliases(self) -> dict[str, str]:
        """Get all alias mappings."""
        return dict(self._aliases)

    def load_from_yaml(self, path: str) -> None:
        """Load additional aliases from YAML file."""
        import yaml
        from pathlib import Path

        yaml_path = Path(path)
        if yaml_path.exists():
            with open(yaml_path) as f:
                data = yaml.safe_load(f)
                if data and isinstance(data, dict):
                    for alias, canonical in data.items():
                        self.add_alias(alias, canonical)


# Global alias registry
alias_registry = AliasRegistry()


__all__ = ["AliasRegistry", "alias_registry"]
