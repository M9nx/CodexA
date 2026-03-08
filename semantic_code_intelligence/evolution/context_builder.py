"""Context builder — constructs minimal LLM prompt context.

The builder gathers *only* the information the LLM needs to generate a
patch: the task description, the target file contents (or relevant
excerpts), the git diff, and failing test output.  The assembled context
is capped at a configurable token target (default 2 000 tokens ≈ 8 000
chars) to keep LLM costs low.
"""

from __future__ import annotations

from pathlib import Path

from semantic_code_intelligence.evolution.budget_guard import BudgetGuard
from semantic_code_intelligence.evolution.commit_manager import CommitManager
from semantic_code_intelligence.evolution.task_selector import EvolutionTask
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("evolution.context_builder")

# Rough approximation: 1 token ≈ 4 characters
_CHARS_PER_TOKEN = 4
_DEFAULT_MAX_TOKENS = 2000

# System prompt used for every evolution call
SYSTEM_PROMPT = (
    "You are a senior software engineer improving the CodexA codebase. "
    "Your job is to make a SMALL, SAFE improvement. Rules:\n"
    "- Change at most 3 files and 200 lines.\n"
    "- Output ONLY a unified diff (no explanation before or after).\n"
    "- Do NOT add new dependencies.\n"
    "- Do NOT rewrite subsystems or change architecture.\n"
    "- Preserve all existing tests.\n"
    "- Use full type hints.\n"
    "- Keep it simple."
)


class ContextBuilder:
    """Assembles a minimal prompt context for the patch generator."""

    def __init__(
        self,
        project_root: Path,
        commit_manager: CommitManager,
        max_context_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> None:
        self._root = project_root.resolve()
        self._git = commit_manager
        self._max_chars = max_context_tokens * _CHARS_PER_TOKEN

    def build(self, task: EvolutionTask) -> str:
        """Build the user-message portion of the LLM prompt.

        Sections (included in priority order until budget exhausted):
        1. Task description  (always included)
        2. Target file contents (trimmed to budget)
        3. Git diff           (if any)
        4. Failing test output (if present in task context_hint)
        """
        parts: list[str] = []
        budget = self._max_chars

        # 1. Task description
        header = self._task_section(task)
        parts.append(header)
        budget -= len(header)

        # 2. Target file contents
        for rel_path in task.target_files[:3]:
            if budget <= 200:
                break
            section = self._file_section(rel_path, budget)
            if section:
                parts.append(section)
                budget -= len(section)

        # 3. Git diff
        if budget > 200:
            diff = self._git.git_diff()
            if diff.strip():
                diff_section = f"### Current git diff\n```diff\n{_truncate(diff, budget - 60)}\n```"
                parts.append(diff_section)
                budget -= len(diff_section)

        # 4. Context hint (failing test output, etc.)
        if budget > 200 and task.context_hint:
            hint = f"### Additional context\n```\n{_truncate(task.context_hint, budget - 60)}\n```"
            parts.append(hint)

        return "\n\n".join(parts)

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimate for a text string."""
        return max(1, len(text) // _CHARS_PER_TOKEN)

    # ------------------------------------------------------------------ #
    # Section builders
    # ------------------------------------------------------------------ #

    @staticmethod
    def _task_section(task: EvolutionTask) -> str:
        lines = [
            f"### Task: {task.category}",
            task.description,
        ]
        if task.target_files:
            lines.append(f"Target files: {', '.join(task.target_files)}")
        lines.append(
            "\nProduce a unified diff that implements this improvement."
        )
        return "\n".join(lines)

    def _file_section(self, rel_path: str, budget: int) -> str | None:
        """Read a target file and return a fenced code block."""
        full = self._root / rel_path
        if not full.exists():
            return None
        try:
            content = full.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        content = _truncate(content, budget - 80)
        return f"### File: {rel_path}\n```python\n{content}\n```"


def _truncate(text: str, max_chars: int) -> str:
    """Truncate *text* to at most *max_chars*, appending '…' if trimmed."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n... (truncated)"
