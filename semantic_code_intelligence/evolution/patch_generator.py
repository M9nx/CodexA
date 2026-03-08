"""Patch generator — asks the LLM for a unified diff and applies it.

The generator sends a minimal prompt (system + context) to the configured
LLM provider and parses the response as a unified diff.  It then applies
the diff to the working tree using ``git apply``.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from semantic_code_intelligence.evolution.budget_guard import BudgetGuard
from semantic_code_intelligence.evolution.context_builder import SYSTEM_PROMPT, ContextBuilder
from semantic_code_intelligence.evolution.task_selector import EvolutionTask
from semantic_code_intelligence.llm.provider import LLMMessage, LLMProvider, LLMResponse, MessageRole
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("evolution.patch_generator")

# Safety limits
_MAX_FILES_CHANGED = 3
_MAX_LINES_CHANGED = 200


@dataclass
class PatchResult:
    """Result of a patch generation + apply attempt."""

    success: bool = False
    diff_text: str = ""
    files_changed: list[str] = field(default_factory=list)
    lines_changed: int = 0
    llm_response: LLMResponse | None = None
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialise the patch result to a plain dictionary."""
        return {
            "success": self.success,
            "files_changed": self.files_changed,
            "lines_changed": self.lines_changed,
            "error": self.error,
        }


class PatchGenerator:
    """Generates and applies patches via LLM."""

    def __init__(
        self,
        project_root: Path,
        provider: LLMProvider,
        context_builder: ContextBuilder,
        budget: BudgetGuard,
    ) -> None:
        self._root = project_root.resolve()
        self._provider = provider
        self._ctx = context_builder
        self._budget = budget

    def generate_and_apply(self, task: EvolutionTask) -> PatchResult:
        """Generate a patch and apply it to the working tree.

        Steps:
        1.  Build minimal context prompt.
        2.  Call LLM.
        3.  Parse unified diff from response.
        4.  Validate safety limits.
        5.  Apply via ``git apply``.
        """
        # 1. Build context
        user_msg = self._ctx.build(task)
        prompt_tokens = self._ctx.estimate_tokens(SYSTEM_PROMPT + user_msg)

        if prompt_tokens > self._budget.tokens_remaining:
            return PatchResult(
                error=f"Prompt ({prompt_tokens} tokens) exceeds remaining budget "
                      f"({self._budget.tokens_remaining} tokens)."
            )

        # 2. Call LLM
        messages = [
            LLMMessage(role=MessageRole.SYSTEM, content=SYSTEM_PROMPT),
            LLMMessage(role=MessageRole.USER, content=user_msg),
        ]
        try:
            response = self._provider.chat(messages, temperature=0.2, max_tokens=2048)
        except Exception as exc:
            return PatchResult(error=f"LLM call failed: {exc}")

        total_tokens = response.usage.get("total_tokens", prompt_tokens + len(response.content) // 4)
        self._budget.record_tokens(total_tokens)

        # 3. Parse diff
        diff_text = _extract_diff(response.content)
        if not diff_text:
            return PatchResult(
                llm_response=response,
                error="LLM response did not contain a valid unified diff.",
            )

        # 4. Validate safety limits
        files = _diff_files(diff_text)
        lines = _diff_line_count(diff_text)

        if len(files) > _MAX_FILES_CHANGED:
            return PatchResult(
                diff_text=diff_text,
                files_changed=files,
                lines_changed=lines,
                error=f"Patch touches {len(files)} files (max {_MAX_FILES_CHANGED}).",
            )
        if lines > _MAX_LINES_CHANGED:
            return PatchResult(
                diff_text=diff_text,
                files_changed=files,
                lines_changed=lines,
                error=f"Patch changes {lines} lines (max {_MAX_LINES_CHANGED}).",
            )

        # 5. Apply
        ok, apply_err = _apply_diff(diff_text, self._root)
        if not ok:
            return PatchResult(
                diff_text=diff_text,
                files_changed=files,
                lines_changed=lines,
                error=f"git apply failed: {apply_err}",
            )

        return PatchResult(
            success=True,
            diff_text=diff_text,
            files_changed=files,
            lines_changed=lines,
            llm_response=response,
        )


# ------------------------------------------------------------------ #
# Diff parsing helpers
# ------------------------------------------------------------------ #

def _extract_diff(text: str) -> str:
    """Extract a unified diff block from LLM output.

    Looks for ``--- a/`` or a fenced code block containing diff content.
    """
    # Try fenced code block first
    m = re.search(r"```(?:diff)?\s*\n(.*?)```", text, re.DOTALL)
    if m:
        candidate = m.group(1).strip()
        if "--- " in candidate or "+++ " in candidate:
            return candidate

    # Try raw diff
    lines = text.splitlines()
    diff_lines: list[str] = []
    in_diff = False
    for line in lines:
        if line.startswith("--- ") or line.startswith("+++ ") or line.startswith("@@ "):
            in_diff = True
        if in_diff:
            diff_lines.append(line)
            # Stop on blank line after diff section
            if not line.strip() and diff_lines and diff_lines[-2].strip():
                continue
    return "\n".join(diff_lines).strip()


def _diff_files(diff_text: str) -> list[str]:
    """Extract file paths changed in a unified diff."""
    files: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            path = line[4:].strip()
            # Strip "b/" prefix
            if path.startswith("b/"):
                path = path[2:]
            if path and path != "/dev/null" and path not in files:
                files.append(path)
    return files


def _diff_line_count(diff_text: str) -> int:
    """Count the number of added + removed lines in a diff."""
    count = 0
    for line in diff_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            count += 1
        elif line.startswith("-") and not line.startswith("---"):
            count += 1
    return count


def _apply_diff(diff_text: str, cwd: Path) -> tuple[bool, str]:
    """Apply a unified diff via ``git apply``.  Returns (success, error)."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".patch", delete=False, encoding="utf-8"
    ) as f:
        f.write(diff_text)
        patch_path = f.name

    try:
        proc = subprocess.run(
            ["git", "apply", "--check", patch_path],
            capture_output=True,
            text=True,
            cwd=str(cwd),
        )
        if proc.returncode != 0:
            return False, proc.stderr.strip()

        proc = subprocess.run(
            ["git", "apply", patch_path],
            capture_output=True,
            text=True,
            cwd=str(cwd),
        )
        if proc.returncode != 0:
            return False, proc.stderr.strip()
        return True, ""
    finally:
        Path(patch_path).unlink(missing_ok=True)
