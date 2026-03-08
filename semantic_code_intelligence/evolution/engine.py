"""Evolution engine — orchestrates the self-improving development loop.

Each iteration:
1.  Run tests to get baseline.
2.  Select a task (fix tests → type hints → error handling → dedup → optimise).
3.  Build minimal LLM context.
4.  Generate + apply patch via LLM.
5.  Run tests again.
6.  If tests pass → commit.  If tests fail → revert.
7.  Repeat until budget exhausted.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from semantic_code_intelligence.evolution.budget_guard import BudgetGuard
from semantic_code_intelligence.evolution.commit_manager import CommitManager
from semantic_code_intelligence.evolution.context_builder import ContextBuilder
from semantic_code_intelligence.evolution.patch_generator import PatchGenerator, PatchResult
from semantic_code_intelligence.evolution.task_selector import EvolutionTask, TaskSelector
from semantic_code_intelligence.evolution.test_runner import TestResult, TestRunner
from semantic_code_intelligence.llm.provider import LLMProvider
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("evolution.engine")


# ------------------------------------------------------------------ #
# Result dataclasses
# ------------------------------------------------------------------ #


@dataclass
class IterationRecord:
    """Record of a single evolution iteration."""

    iteration: int = 0
    task_category: str = ""
    task_description: str = ""
    target_files: list[str] = field(default_factory=list)
    patch_lines_changed: int = 0
    tests_before: int = 0
    tests_after: int = 0
    committed: bool = False
    commit_sha: str = ""
    reverted: bool = False
    error: str = ""
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "iteration": self.iteration,
            "task_category": self.task_category,
            "task_description": self.task_description,
            "target_files": self.target_files,
            "patch_lines_changed": self.patch_lines_changed,
            "tests_before": self.tests_before,
            "tests_after": self.tests_after,
            "committed": self.committed,
            "commit_sha": self.commit_sha,
            "reverted": self.reverted,
            "error": self.error,
            "duration_seconds": round(self.duration_seconds, 2),
        }


@dataclass
class EvolutionResult:
    """Aggregate result of an evolution run."""

    iterations_completed: int = 0
    commits: list[str] = field(default_factory=list)
    reverts: int = 0
    stop_reason: str = ""
    budget_summary: dict[str, object] = field(default_factory=dict)
    history: list[IterationRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "iterations_completed": self.iterations_completed,
            "commits": self.commits,
            "reverts": self.reverts,
            "stop_reason": self.stop_reason,
            "budget_summary": self.budget_summary,
            "history": [r.to_dict() for r in self.history],
        }


# ------------------------------------------------------------------ #
# Engine
# ------------------------------------------------------------------ #


class EvolutionEngine:
    """Runs the self-improving development loop."""

    def __init__(
        self,
        project_root: Path,
        provider: LLMProvider,
        budget: BudgetGuard,
    ) -> None:
        self._root = project_root.resolve()
        self._provider = provider
        self._budget = budget

        # Build sub-components
        self._test_runner = TestRunner(project_root=self._root)
        self._commit_mgr = CommitManager(project_root=self._root)
        self._ctx_builder = ContextBuilder(
            project_root=self._root,
            commit_manager=self._commit_mgr,
        )
        self._task_selector = TaskSelector(
            project_root=self._root,
            test_runner=self._test_runner,
            commit_manager=self._commit_mgr,
        )
        self._patch_gen = PatchGenerator(
            project_root=self._root,
            provider=self._provider,
            context_builder=self._ctx_builder,
            budget=self._budget,
        )

    # ------------------------------------------------------------------ #
    # Main loop
    # ------------------------------------------------------------------ #

    def run(self) -> EvolutionResult:
        """Execute the evolution loop until the budget is exhausted."""
        result = EvolutionResult()
        self._budget.start()

        # Baseline test run
        last_test = self._test_runner.run()
        logger.info("baseline tests: %s", last_test.summary_line())

        iteration = 0
        while self._budget.can_continue():
            iteration += 1
            iter_start = time.time()
            record = IterationRecord(iteration=iteration, tests_before=last_test.passed)

            # 1. Select task
            task = self._task_selector.select(last_test)
            record.task_category = task.category
            record.task_description = task.description
            record.target_files = list(task.target_files)
            logger.info("iter %d: %s — %s", iteration, task.category, task.description)

            # 2. Generate + apply patch
            patch_result = self._patch_gen.generate_and_apply(task)
            record.patch_lines_changed = patch_result.lines_changed

            if not patch_result.success:
                record.error = patch_result.error
                record.duration_seconds = time.time() - iter_start
                result.history.append(record)
                self._budget.record_iteration()
                logger.warning("iter %d: patch failed — %s", iteration, patch_result.error)
                continue

            # 3. Re-run tests
            new_test = self._test_runner.run()
            record.tests_after = new_test.passed
            logger.info(
                "iter %d: tests %d → %d",
                iteration, last_test.passed, new_test.passed,
            )

            # 4. Decide: commit or revert
            if new_test.return_code == 0 and new_test.passed >= last_test.passed:
                # Tests pass and we did not regress — commit
                self._commit_mgr.stage_files(patch_result.files_changed)
                sha = self._commit_mgr.commit(
                    f"evolve: {task.category} — {task.description[:60]}"
                )
                record.committed = True
                record.commit_sha = sha
                result.commits.append(sha)
                last_test = new_test
                logger.info("iter %d: committed %s", iteration, sha)
            else:
                # Revert
                self._commit_mgr.revert_files(patch_result.files_changed)
                record.reverted = True
                result.reverts += 1
                logger.info("iter %d: reverted — tests regressed", iteration)

            record.duration_seconds = time.time() - iter_start
            result.history.append(record)
            self._budget.record_iteration()

        result.iterations_completed = iteration
        result.stop_reason = self._budget.stop_reason() or "completed"
        result.budget_summary = self._budget.summary()

        # Persist history
        self._write_history(result)
        return result

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _write_history(self, result: EvolutionResult) -> None:
        """Append the evolution run to ``.codex/evolution_history.json``."""
        history_dir = self._root / ".codex"
        history_dir.mkdir(parents=True, exist_ok=True)
        history_file = history_dir / "evolution_history.json"

        runs: list[dict[str, Any]] = []
        if history_file.exists():
            try:
                runs = json.loads(history_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                runs = []

        runs.append(result.to_dict())
        history_file.write_text(
            json.dumps(runs, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        logger.info("evolution history written to %s", history_file)
