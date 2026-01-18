"""Plugin architecture for extensibility."""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class PluginState(str, Enum):
    """Plugin lifecycle states."""

    UNLOADED = "unloaded"
    LOADING = "loading"
    ACTIVE = "active"
    DISABLED = "disabled"
    ERROR = "error"


@dataclass
class PluginConfig:
    """Plugin configuration."""

    name: str
    version: str
    description: str = ""
    author: str = ""
    homepage: str = ""
    dependencies: list[str] = field(default_factory=list)
    settings_schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class HookDefinition:
    """Definition of a hook point."""

    name: str
    description: str
    args: list[str] = field(default_factory=list)
    returns: str = "Any"


class Plugin(ABC):
    """
    Base class for Knowledge Engine plugins.

    Plugins can extend the system by:
    - Registering hooks for lifecycle events
    - Adding new ingestion sources
    - Providing custom processing pipelines
    - Adding API endpoints
    """

    def __init__(self):
        self.state = PluginState.UNLOADED
        self.settings: dict[str, Any] = {}
        self._hooks: dict[str, list[Callable[..., Any]]] = {}

    @property
    @abstractmethod
    def config(self) -> PluginConfig:
        """Return plugin configuration."""
        ...

    async def on_load(self) -> None:  # noqa: B027
        """Called when plugin is loaded. Override to initialize resources."""
        pass

    async def on_unload(self) -> None:  # noqa: B027
        """Called when plugin is unloaded. Override to cleanup resources."""
        pass

    async def on_enable(self) -> None:  # noqa: B027
        """Called when plugin is enabled."""
        pass

    async def on_disable(self) -> None:  # noqa: B027
        """Called when plugin is disabled."""
        pass

    def register_hook(self, hook_name: str, handler: Callable[..., Any]) -> None:
        """Register a hook handler."""
        if hook_name not in self._hooks:
            self._hooks[hook_name] = []
        self._hooks[hook_name].append(handler)

    def get_hooks(self, hook_name: str) -> list[Callable[..., Any]]:
        """Get all handlers for a hook."""
        return self._hooks.get(hook_name, [])


# Hook decorator
def hook(hook_name: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to register a method as a hook handler.

    Usage:
        class MyPlugin(Plugin):
            @hook("document.pre_ingest")
            async def process_document(self, document):
                return document
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        if not hasattr(func, "_hooks"):
            func._hooks = []
        func._hooks.append(hook_name)
        return func

    return decorator


class PluginManager:
    """
    Manages plugin lifecycle and hook execution.

    Features:
    - Plugin discovery and loading
    - Dependency resolution
    - Hook management
    - Plugin settings
    """

    # Available hooks
    HOOKS = {
        # Document lifecycle
        "document.pre_ingest": HookDefinition(
            name="document.pre_ingest",
            description="Called before document ingestion",
            args=["document"],
            returns="document",
        ),
        "document.post_ingest": HookDefinition(
            name="document.post_ingest",
            description="Called after document ingestion",
            args=["document", "chunks"],
        ),
        "document.pre_delete": HookDefinition(
            name="document.pre_delete",
            description="Called before document deletion",
            args=["document_id"],
        ),
        # Search lifecycle
        "search.pre_query": HookDefinition(
            name="search.pre_query",
            description="Called before search query",
            args=["query", "options"],
            returns="tuple[query, options]",
        ),
        "search.post_query": HookDefinition(
            name="search.post_query",
            description="Called after search query",
            args=["query", "results"],
            returns="results",
        ),
        # Chunk processing
        "chunk.pre_embed": HookDefinition(
            name="chunk.pre_embed",
            description="Called before generating embeddings",
            args=["chunk"],
            returns="chunk",
        ),
        "chunk.post_embed": HookDefinition(
            name="chunk.post_embed",
            description="Called after generating embeddings",
            args=["chunk", "embedding"],
        ),
        # RAG pipeline
        "rag.pre_generate": HookDefinition(
            name="rag.pre_generate",
            description="Called before RAG generation",
            args=["query", "context"],
            returns="tuple[query, context]",
        ),
        "rag.post_generate": HookDefinition(
            name="rag.post_generate",
            description="Called after RAG generation",
            args=["query", "response"],
            returns="response",
        ),
    }

    def __init__(self, plugin_dirs: list[Path] | None = None):
        """
        Initialize plugin manager.

        Args:
            plugin_dirs: Directories to search for plugins
        """
        self.plugin_dirs = plugin_dirs or []
        self._plugins: dict[str, Plugin] = {}
        self._hook_handlers: dict[str, list[tuple[Plugin, Callable[..., Any]]]] = {
            hook: [] for hook in self.HOOKS
        }
        self._lock = asyncio.Lock()

    async def discover_plugins(self) -> list[str]:
        """Discover available plugins in plugin directories."""
        discovered = []

        for plugin_dir in self.plugin_dirs:
            if not plugin_dir.exists():
                continue

            for path in plugin_dir.iterdir():
                if path.is_dir() and (path / "plugin.py").exists():
                    discovered.append(path.name)
                elif path.suffix == ".py" and path.stem != "__init__":
                    discovered.append(path.stem)

        return discovered

    async def load_plugin(
        self,
        name: str,
        settings: dict[str, Any] | None = None,
    ) -> Plugin:
        """
        Load a plugin by name.

        Args:
            name: Plugin name or module path
            settings: Optional plugin settings

        Returns:
            Loaded plugin instance
        """
        async with self._lock:
            # Check if already loaded
            if name in self._plugins:
                return self._plugins[name]

            logger.info(f"Loading plugin: {name}")

            # Find and load plugin module
            plugin_class = await self._find_plugin_class(name)
            if not plugin_class:
                raise ValueError(f"Plugin not found: {name}")

            # Create instance
            plugin = plugin_class()
            plugin.state = PluginState.LOADING
            plugin.settings = settings or {}

            # Check dependencies
            await self._check_dependencies(plugin)

            # Load plugin
            try:
                await plugin.on_load()
                plugin.state = PluginState.ACTIVE

                # Register hooks
                self._register_plugin_hooks(plugin)

                self._plugins[name] = plugin
                logger.info(f"Plugin loaded: {name} v{plugin.config.version}")

                return plugin

            except Exception as e:
                plugin.state = PluginState.ERROR
                logger.error(f"Failed to load plugin {name}: {e}")
                raise

    async def unload_plugin(self, name: str) -> None:
        """Unload a plugin."""
        async with self._lock:
            if name not in self._plugins:
                return

            plugin = self._plugins[name]
            logger.info(f"Unloading plugin: {name}")

            try:
                await plugin.on_unload()
            except Exception as e:
                logger.warning(f"Error during plugin unload: {e}")

            # Remove hooks
            self._unregister_plugin_hooks(plugin)

            del self._plugins[name]
            plugin.state = PluginState.UNLOADED

    async def enable_plugin(self, name: str) -> None:
        """Enable a disabled plugin."""
        plugin = self._plugins.get(name)
        if plugin and plugin.state == PluginState.DISABLED:
            await plugin.on_enable()
            plugin.state = PluginState.ACTIVE
            self._register_plugin_hooks(plugin)

    async def disable_plugin(self, name: str) -> None:
        """Disable an active plugin."""
        plugin = self._plugins.get(name)
        if plugin and plugin.state == PluginState.ACTIVE:
            await plugin.on_disable()
            plugin.state = PluginState.DISABLED
            self._unregister_plugin_hooks(plugin)

    async def execute_hook(
        self,
        hook_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Execute all handlers for a hook.

        For hooks that return values, handlers are chained
        (output of one becomes input of next).
        """
        if hook_name not in self._hook_handlers:
            return args[0] if args else None

        handlers = self._hook_handlers[hook_name]
        if not handlers:
            return args[0] if args else None

        result = args[0] if args else None

        for plugin, handler in handlers:
            if plugin.state != PluginState.ACTIVE:
                continue

            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(result, *args[1:], **kwargs)
                else:
                    result = handler(result, *args[1:], **kwargs)
            except Exception as e:
                logger.error(
                    f"Hook {hook_name} error in plugin {plugin.config.name}: {e}"
                )

        return result

    async def _find_plugin_class(self, name: str) -> type[Plugin] | None:
        """Find and import a plugin class."""
        # Try as module path
        if "." in name:
            try:
                module = importlib.import_module(name)
                return self._find_plugin_in_module(module)
            except ImportError:
                pass

        # Search plugin directories
        for plugin_dir in self.plugin_dirs:
            # Try as package
            package_path = plugin_dir / name / "plugin.py"
            if package_path.exists():
                return await self._load_plugin_from_file(package_path)

            # Try as single file
            file_path = plugin_dir / f"{name}.py"
            if file_path.exists():
                return await self._load_plugin_from_file(file_path)

        return None

    async def _load_plugin_from_file(self, path: Path) -> type[Plugin] | None:
        """Load a plugin class from a file."""
        spec = importlib.util.spec_from_file_location(path.stem, path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return self._find_plugin_in_module(module)
        return None

    def _find_plugin_in_module(self, module: Any) -> type[Plugin] | None:
        """Find Plugin subclass in a module."""
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, Plugin)
                and attr is not Plugin
            ):
                return attr
        return None

    async def _check_dependencies(self, plugin: Plugin) -> None:
        """Check and load plugin dependencies."""
        for dep in plugin.config.dependencies:
            if dep not in self._plugins:
                await self.load_plugin(dep)

    def _register_plugin_hooks(self, plugin: Plugin) -> None:
        """Register all hooks from a plugin."""
        # Register decorated hooks
        for attr_name in dir(plugin):
            attr = getattr(plugin, attr_name)
            if callable(attr) and hasattr(attr, "_hooks"):
                for hook_name in attr._hooks:
                    if hook_name in self._hook_handlers:
                        self._hook_handlers[hook_name].append((plugin, attr))

        # Register manually registered hooks
        for hook_name, handlers in plugin._hooks.items():
            if hook_name in self._hook_handlers:
                for handler in handlers:
                    self._hook_handlers[hook_name].append((plugin, handler))

    def _unregister_plugin_hooks(self, plugin: Plugin) -> None:
        """Unregister all hooks from a plugin."""
        for hook_name in self._hook_handlers:
            self._hook_handlers[hook_name] = [
                (p, h) for p, h in self._hook_handlers[hook_name] if p is not plugin
            ]

    def get_plugin(self, name: str) -> Plugin | None:
        """Get a loaded plugin by name."""
        return self._plugins.get(name)

    def list_plugins(self) -> list[dict[str, Any]]:
        """List all loaded plugins."""
        return [
            {
                "name": plugin.config.name,
                "version": plugin.config.version,
                "description": plugin.config.description,
                "state": plugin.state.value,
            }
            for plugin in self._plugins.values()
        ]

    def list_hooks(self) -> list[dict[str, Any]]:
        """List all available hooks."""
        return [
            {
                "name": hook.name,
                "description": hook.description,
                "args": hook.args,
                "returns": hook.returns,
                "handlers": len(self._hook_handlers[hook.name]),
            }
            for hook in self.HOOKS.values()
        ]
