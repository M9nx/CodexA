"""Sample CodexA plugin — custom code validator.

Demonstrates the CUSTOM_VALIDATION hook to add project-specific
code quality checks. This example flags common issues like TODO
comments and print statements in production code.

Usage:
    1. Copy this file to `.codex/plugins/`
    2. Custom validations will run during `codex review`
"""

from __future__ import annotations

import re
from typing import Any

from semantic_code_intelligence.plugins import PluginBase, PluginHook, PluginMetadata


class CodeQualityPlugin(PluginBase):
    """Custom code quality validator."""

    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="code-quality",
            version="0.1.0",
            description="Custom code quality validation rules",
            author="CodexA Team",
            hooks=[PluginHook.CUSTOM_VALIDATION],
        )

    def on_hook(self, hook: PluginHook, data: dict[str, Any]) -> dict[str, Any]:
        """Run custom validation rules.

        CUSTOM_VALIDATION data contract:
            - code: str — source code to validate
            - issues: list — existing issues (append to this)
        """
        if hook != PluginHook.CUSTOM_VALIDATION:
            return data

        code = data.get("code", "")
        issues = data.get("issues", [])

        # Flag TODO/FIXME/HACK comments
        for i, line in enumerate(code.splitlines(), 1):
            for tag in ("TODO", "FIXME", "HACK", "XXX"):
                if tag in line:
                    issues.append({
                        "line": i,
                        "description": f"{tag} comment found",
                        "severity": "info",
                        "source": "code-quality",
                    })

        # Flag bare print() statements (suggests using logging)
        for i, line in enumerate(code.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("print(") and not stripped.startswith("print(f\"DEBUG"):
                issues.append({
                    "line": i,
                    "description": "Consider using logging instead of print()",
                    "severity": "warning",
                    "source": "code-quality",
                })

        data["issues"] = issues
        return data


def create_plugin() -> CodeQualityPlugin:
    """Factory function for plugin discovery."""
    return CodeQualityPlugin()
