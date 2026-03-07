"""Sample CodexA plugin — search result annotator.

This example plugin demonstrates how to build a CodexA plugin that
hooks into the search pipeline. It adds a timestamp and custom tag
to every search result passing through.

Usage:
    1. Copy this file to `.codex/plugins/`
    2. Results from `codex search` will include the annotation

This serves as a starting point for building your own plugins.
"""

from __future__ import annotations

import time
from typing import Any

from semantic_code_intelligence.plugins import PluginBase, PluginHook, PluginMetadata


class SearchAnnotatorPlugin(PluginBase):
    """Annotates search results with custom metadata."""

    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="search-annotator",
            version="0.1.0",
            description="Annotates search results with custom metadata",
            author="CodexA Team",
            hooks=[PluginHook.POST_SEARCH],
        )

    def activate(self, context: dict[str, Any]) -> None:
        """Store activation time for annotation."""
        self._activated_at = time.time()

    def on_hook(self, hook: PluginHook, data: dict[str, Any]) -> dict[str, Any]:
        """Add annotation to search results.

        POST_SEARCH data contract:
            - results: list of search result dicts
            - query: the original search query
        """
        if hook == PluginHook.POST_SEARCH:
            results = data.get("results", [])
            for result in results:
                result["annotated_by"] = "search-annotator"
                result["annotated_at"] = time.time()
            data["annotation_count"] = len(results)
        return data


def create_plugin() -> SearchAnnotatorPlugin:
    """Factory function for plugin discovery."""
    return SearchAnnotatorPlugin()
