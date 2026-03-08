"""Pre-commit validation hook support.

Provides a lightweight validation pipeline that can be invoked as a
pre-commit hook or standalone CLI command.  Hooks run the safety
validator and optionally dispatch ``CUSTOM_VALIDATION`` plugin hooks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from semantic_code_intelligence.llm.safety import SafetyValidator, SafetyReport
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("ci.hooks")


@dataclass
class HookResult:
    """Result from a pre-commit validation run."""

    passed: bool = True
    files_checked: int = 0
    safety: SafetyReport | None = None
    plugin_results: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "files_checked": self.files_checked,
            "safety": self.safety.to_dict() if self.safety else None,
            "plugin_results": self.plugin_results,
        }


def run_precommit_check(
    files: list[str],
    *,
    project_root: Path | None = None,
    run_plugins: bool = True,
) -> HookResult:
    """Run pre-commit safety and validation checks on *files*.

    1. Safety validation: scans each file for dangerous patterns.
    2. Plugin hooks: dispatches ``CUSTOM_VALIDATION`` on each file (optional).
    """
    result = HookResult(files_checked=len(files))

    # Aggregate file content for safety scan
    all_code = ""
    for fpath in files:
        try:
            all_code += Path(fpath).read_text(encoding="utf-8", errors="replace") + "\n"
        except Exception as exc:
            logger.debug("Could not read %s: %s", fpath, exc)

    # Run safety validator
    validator = SafetyValidator()
    result.safety = validator.validate(all_code)
    if not result.safety.safe:
        result.passed = False

    # Run plugin CUSTOM_VALIDATION hooks if enabled
    if run_plugins and project_root:
        try:
            from semantic_code_intelligence.plugins import PluginManager, PluginHook

            mgr = PluginManager()
            plugin_dir = project_root / ".codex" / "plugins"
            if plugin_dir.is_dir():
                mgr.discover_from_directory(plugin_dir)
                for name in mgr.registered_plugins:
                    mgr.activate(name)

                for fpath in files:
                    try:
                        content = Path(fpath).read_text(encoding="utf-8", errors="replace")
                    except Exception:
                        logger.debug("Failed to read %s for plugin validation", fpath)
                        continue
                    data = {
                        "file_path": fpath,
                        "content": content,
                        "issues": [],
                    }
                    out = mgr.dispatch(PluginHook.CUSTOM_VALIDATION, data)
                    if out.get("issues"):
                        result.plugin_results.append({
                            "file": fpath,
                            "issues": out["issues"],
                        })
                        result.passed = False
        except Exception as exc:
            logger.debug("Plugin validation skipped: %s", exc)

    return result
