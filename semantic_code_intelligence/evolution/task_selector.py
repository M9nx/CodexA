"""Task selector — chooses the next small improvement task.

Analyses the current repository state (git diff, failing tests, code
quality signals) and picks a single, well-scoped task for the LLM to
implement.  Every task targets **≤3 files** and **≤200 lines changed**.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from semantic_code_intelligence.evolution.commit_manager import CommitManager
from semantic_code_intelligence.evolution.test_runner import TestResult, TestRunner
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("evolution.task_selector")

# Priority-ordered task categories
TASK_FIX_TESTS = "fix_failing_tests"
TASK_TYPE_HINTS = "add_missing_type_hints"
TASK_ERROR_HANDLING = "improve_error_handling"
TASK_REDUCE_DUPLICATION = "reduce_duplication"
TASK_SMALL_OPTIMISATION = "small_performance_optimisation"

TASK_PRIORITIES: list[str] = [
    TASK_FIX_TESTS,
    TASK_TYPE_HINTS,
    TASK_ERROR_HANDLING,
    TASK_REDUCE_DUPLICATION,
    TASK_SMALL_OPTIMISATION,
]


@dataclass
class EvolutionTask:
    """A single, well-scoped improvement task."""

    category: str
    description: str
    target_files: list[str] = field(default_factory=list)
    context_hint: str = ""

    def to_dict(self) -> dict[str, object]:
        """Serialise the task to a plain dictionary."""
        return {
            "category": self.category,
            "description": self.description,
            "target_files": self.target_files,
            "context_hint": self.context_hint,
        }


class TaskSelector:
    """Selects the next evolution task based on repo state."""

    def __init__(
        self,
        project_root: Path,
        test_runner: TestRunner,
        commit_manager: CommitManager,
    ) -> None:
        self._root = project_root.resolve()
        self._runner = test_runner
        self._git = commit_manager

    def select(self, last_test_result: TestResult | None = None) -> EvolutionTask:
        """Choose the highest-priority actionable task.

        1. If tests are failing → fix them
        2. Else scan for missing type hints
        3. Else scan for bare excepts / weak error handling
        4. Else look for obvious duplication
        5. Fallback: small quality improvement
        """
        # Priority 1: fix failing tests
        if last_test_result and not last_test_result.passed:
            return self._task_from_failures(last_test_result)

        # Priority 2–5: static analysis of source files
        src_dir = self._root / "semantic_code_intelligence"
        py_files = self._collect_py_files(src_dir)

        task = self._find_type_hint_task(py_files)
        if task:
            return task

        task = self._find_error_handling_task(py_files)
        if task:
            return task

        task = self._find_duplication_task(py_files)
        if task:
            return task

        # Fallback
        return EvolutionTask(
            category=TASK_SMALL_OPTIMISATION,
            description="Look for a small quality or performance improvement in the codebase.",
            target_files=[],
            context_hint="Focus on hot-path functions or frequently used utilities.",
        )

    # ------------------------------------------------------------------ #
    # Task builders
    # ------------------------------------------------------------------ #

    def _task_from_failures(self, result: TestResult) -> EvolutionTask:
        """Extract a fix-tests task from failing test output."""
        # Pull failing file hints from the output (pytest --tb=line gives file:line)
        failing_files: list[str] = []
        for line in result.output.splitlines():
            stripped = line.strip()
            if stripped.startswith("FAILED ") or "::" in stripped:
                parts = stripped.split("::")
                if parts:
                    fpath = parts[0].replace("FAILED ", "").strip()
                    if fpath.endswith(".py") and fpath not in failing_files:
                        failing_files.append(fpath)
        return EvolutionTask(
            category=TASK_FIX_TESTS,
            description=f"Fix {result.failures} failing test(s).",
            target_files=failing_files[:3],
            context_hint=_last_n_lines(result.output, 40),
        )

    def _find_type_hint_task(self, files: list[Path]) -> EvolutionTask | None:
        """Find a source file with functions lacking return type annotations."""
        import re
        pattern = re.compile(r"^\s*def\s+\w+\([^)]*\)\s*:", re.MULTILINE)
        typed = re.compile(r"^\s*def\s+\w+\([^)]*\)\s*->\s*", re.MULTILINE)

        for fpath in files:
            try:
                text = fpath.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            all_defs = pattern.findall(text)
            typed_defs = typed.findall(text)
            missing = len(all_defs) - len(typed_defs)
            if missing >= 2:
                rel = str(fpath.relative_to(self._root))
                return EvolutionTask(
                    category=TASK_TYPE_HINTS,
                    description=f"Add return type hints to {missing} function(s) in {rel}.",
                    target_files=[rel],
                    context_hint=f"File has {len(all_defs)} defs, {len(typed_defs)} typed.",
                )
        return None

    def _find_error_handling_task(self, files: list[Path]) -> EvolutionTask | None:
        """Find a file with bare ``except:`` or ``except Exception:`` blocks."""
        for fpath in files:
            try:
                text = fpath.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "\nexcept:" in text or "\nexcept Exception:" in text:
                rel = str(fpath.relative_to(self._root))
                return EvolutionTask(
                    category=TASK_ERROR_HANDLING,
                    description=f"Replace bare/broad except blocks with specific exceptions in {rel}.",
                    target_files=[rel],
                    context_hint="Catch only the exceptions that can actually occur.",
                )
        return None

    def _find_duplication_task(self, files: list[Path]) -> EvolutionTask | None:
        """Very lightweight duplication detector — looks for repeated blocks."""
        # Simplified: look for files > 300 lines with repeated 5-line blocks
        for fpath in files:
            try:
                lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            if len(lines) < 300:
                continue
            blocks: dict[str, int] = {}
            for i in range(len(lines) - 4):
                block = "\n".join(lines[i : i + 5]).strip()
                if len(block) > 60:
                    blocks[block] = blocks.get(block, 0) + 1
            dups = sum(1 for v in blocks.values() if v >= 2)
            if dups >= 2:
                rel = str(fpath.relative_to(self._root))
                return EvolutionTask(
                    category=TASK_REDUCE_DUPLICATION,
                    description=f"Extract duplicated logic into helper functions in {rel}.",
                    target_files=[rel],
                    context_hint=f"Found {dups} repeated 5-line blocks.",
                )
        return None

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _collect_py_files(self, src_dir: Path) -> list[Path]:
        """Collect .py source files, excluding tests and __pycache__."""
        results: list[Path] = []
        if not src_dir.exists():
            return results
        for fpath in sorted(src_dir.rglob("*.py")):
            rel = str(fpath.relative_to(self._root))
            if "tests" in rel or "__pycache__" in rel:
                continue
            results.append(fpath)
        return results


def _last_n_lines(text: str, n: int) -> str:
    """Return the last *n* non-empty lines of *text*."""
    lines = [l for l in text.splitlines() if l.strip()]
    return "\n".join(lines[-n:])
