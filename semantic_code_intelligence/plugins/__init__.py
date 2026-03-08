"""Plugin architecture SDK — extensible hook system for CodexA.

Provides:
- PluginBase: abstract base class for plugins
- PluginHook: enumeration of hook points
- PluginManager: discovery, registration, and lifecycle management
"""

from __future__ import annotations

import importlib
import importlib.util
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("plugins")


# ---------------------------------------------------------------------------
# Hook Points
# ---------------------------------------------------------------------------

class PluginHook(str, Enum):
    """Available hook points in the CodexA pipeline."""

    # Indexing hooks
    PRE_INDEX = "pre_index"
    POST_INDEX = "post_index"
    ON_CHUNK = "on_chunk"

    # Search hooks
    PRE_SEARCH = "pre_search"
    POST_SEARCH = "post_search"

    # Analysis hooks
    PRE_ANALYSIS = "pre_analysis"
    POST_ANALYSIS = "post_analysis"

    # AI hooks
    PRE_AI = "pre_ai"
    POST_AI = "post_ai"

    # File event hooks
    ON_FILE_CHANGE = "on_file_change"

    # Streaming hooks (Phase 12)
    ON_STREAM = "on_stream"  # fired for streaming LLM token chunks

    # Validation hooks (Phase 12)
    CUSTOM_VALIDATION = "custom_validation"  # user-defined code validation rules

    # Workflow intelligence hooks (Phase 18)
    PRE_HOTSPOT_ANALYSIS = "pre_hotspot_analysis"
    POST_HOTSPOT_ANALYSIS = "post_hotspot_analysis"
    PRE_IMPACT_ANALYSIS = "pre_impact_analysis"
    POST_IMPACT_ANALYSIS = "post_impact_analysis"
    PRE_TRACE = "pre_trace"
    POST_TRACE = "post_trace"

    # Custom hooks
    CUSTOM = "custom"


# ---------------------------------------------------------------------------
# Plugin Metadata
# ---------------------------------------------------------------------------

@dataclass
class PluginMetadata:
    """Metadata describing a plugin."""

    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    hooks: list[PluginHook] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "hooks": [h.value for h in self.hooks],
        }


# ---------------------------------------------------------------------------
# Plugin Base Class
# ---------------------------------------------------------------------------

class PluginBase(ABC):
    """Abstract base class for CodexA plugins.

    Subclass this and implement the required methods to create a plugin.
    """

    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Return metadata for this plugin."""
        ...

    def activate(self, context: dict[str, Any]) -> None:
        """Called when the plugin is activated. Override for setup logic."""

    def deactivate(self) -> None:
        """Called when the plugin is deactivated. Override for cleanup logic."""

    def on_hook(self, hook: PluginHook, data: dict[str, Any]) -> dict[str, Any]:
        """Called when a registered hook fires.

        Args:
            hook: The hook that fired.
            data: Hook-specific data dict. Plugin may modify and return it.

        Returns:
            Possibly modified data dict (passed to next plugin in chain).
        """
        return data


# ---------------------------------------------------------------------------
# Plugin Manager
# ---------------------------------------------------------------------------

class PluginManager:
    """Manages plugin discovery, registration, and hook dispatch."""

    def __init__(self) -> None:
        self._plugins: dict[str, PluginBase] = {}
        self._hook_registry: dict[PluginHook, list[str]] = {h: [] for h in PluginHook}
        self._active: set[str] = set()

    @property
    def registered_plugins(self) -> list[str]:
        return list(self._plugins.keys())

    @property
    def active_plugins(self) -> list[str]:
        return list(self._active)

    def register(self, plugin: PluginBase) -> None:
        """Register a plugin instance."""
        meta = plugin.metadata()
        if meta.name in self._plugins:
            logger.warning("Plugin '%s' already registered; replacing.", meta.name)
        self._plugins[meta.name] = plugin
        for hook in meta.hooks:
            if meta.name not in self._hook_registry[hook]:
                self._hook_registry[hook].append(meta.name)
        logger.info("Registered plugin: %s v%s", meta.name, meta.version)

    def unregister(self, name: str) -> None:
        """Unregister a plugin by name."""
        if name in self._active:
            self.deactivate(name)
        if name in self._plugins:
            # Remove from hook registry
            for hook in self._hook_registry:
                if name in self._hook_registry[hook]:
                    self._hook_registry[hook].remove(name)
            del self._plugins[name]
            logger.info("Unregistered plugin: %s", name)

    def activate(self, name: str, context: dict[str, Any] | None = None) -> None:
        """Activate a registered plugin."""
        plugin = self._plugins.get(name)
        if plugin is None:
            raise ValueError(f"Plugin '{name}' is not registered.")
        plugin.activate(context or {})
        self._active.add(name)
        logger.info("Activated plugin: %s", name)

    def deactivate(self, name: str) -> None:
        """Deactivate a plugin."""
        plugin = self._plugins.get(name)
        if plugin and name in self._active:
            plugin.deactivate()
            self._active.discard(name)
            logger.info("Deactivated plugin: %s", name)

    def dispatch(self, hook: PluginHook, data: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a hook to all active plugins registered for it.

        Plugins are called in registration order. Each plugin receives
        the data dict (possibly modified by the previous plugin).

        Returns:
            The final data dict after all plugins have processed it.
        """
        for name in self._hook_registry.get(hook, []):
            if name not in self._active:
                continue
            plugin = self._plugins[name]
            try:
                data = plugin.on_hook(hook, data)
            except Exception:
                logger.exception("Plugin '%s' error on hook '%s'", name, hook.value)
        return data

    def get_plugin_info(self, name: str) -> dict[str, Any] | None:
        """Get metadata for a specific plugin."""
        plugin = self._plugins.get(name)
        if plugin is None:
            return None
        meta = plugin.metadata()
        info = meta.to_dict()
        info["active"] = name in self._active
        return info

    def discover_from_directory(self, directory: Path) -> int:
        """Discover and register plugins from a directory.

        Looks for Python files with a `create_plugin()` factory function.

        Returns:
            Number of plugins discovered.
        """
        count = 0
        if not directory.is_dir():
            return 0

        for py_file in sorted(directory.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            try:
                spec = importlib.util.spec_from_file_location(
                    f"codex_plugin_{py_file.stem}", py_file
                )
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)  # type: ignore[union-attr]

                factory = getattr(module, "create_plugin", None)
                if callable(factory):
                    plugin = factory()
                    if isinstance(plugin, PluginBase):
                        self.register(plugin)
                        count += 1
            except Exception:
                logger.exception("Failed to load plugin from %s", py_file)

        logger.info("Discovered %d plugin(s) from %s", count, directory)
        return count
