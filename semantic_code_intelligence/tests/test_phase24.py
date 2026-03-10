"""Phase 24 — Self-Improving Development Loop.

Tests verify:
  1.  BudgetGuard — start, can_continue, record_tokens/iteration, stop_reason, summary
  2.  TestRunner — parse_summary, TestResult
  3.  CommitManager — git operations with mocked subprocess
  4.  TaskSelector — priority selection, task builders
  5.  ContextBuilder — system prompt, build sections, truncation, estimate_tokens
  6.  PatchGenerator — diff extraction, diff parsing, safety limits
  7.  EvolutionEngine — orchestrated loop with mocked components
  8.  CLI command — evolve command exists, help text, options
  9.  Module imports and version
"""

from __future__ import annotations

import json
import textwrap
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------

from semantic_code_intelligence.evolution.budget_guard import BudgetGuard
from semantic_code_intelligence.evolution.test_runner import TestResult, TestRunner, _parse_summary
from semantic_code_intelligence.evolution.commit_manager import CommitManager
from semantic_code_intelligence.evolution.task_selector import (
    TASK_ERROR_HANDLING,
    TASK_FIX_TESTS,
    TASK_REDUCE_DUPLICATION,
    TASK_SMALL_OPTIMISATION,
    TASK_TYPE_HINTS,
    EvolutionTask,
    TaskSelector,
)
from semantic_code_intelligence.evolution.context_builder import (
    SYSTEM_PROMPT,
    ContextBuilder,
)
from semantic_code_intelligence.evolution.patch_generator import (
    PatchGenerator,
    PatchResult,
    _diff_files,
    _diff_line_count,
    _extract_diff,
)
from semantic_code_intelligence.evolution.engine import (
    EvolutionEngine,
    EvolutionResult,
    IterationRecord,
)
from semantic_code_intelligence.llm.mock_provider import MockProvider
from semantic_code_intelligence.llm.provider import LLMMessage, LLMResponse, MessageRole

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SRC = _PROJECT_ROOT / "semantic_code_intelligence"


# ═══════════════════════════════════════════════════════════════════════════
# 1 — BudgetGuard
# ═══════════════════════════════════════════════════════════════════════════


class TestBudgetGuard:
    """Tests for the BudgetGuard resource tracker."""

    def test_defaults(self):
        g = BudgetGuard()
        assert g.max_tokens == 20_000
        assert g.max_iterations == 5
        assert g.max_seconds == 600.0
        assert g.tokens_used == 0
        assert g.iterations_done == 0

    def test_can_continue_fresh(self):
        g = BudgetGuard()
        assert g.can_continue() is True

    def test_record_tokens(self):
        g = BudgetGuard(max_tokens=100)
        g.record_tokens(40)
        assert g.tokens_used == 40
        assert g.tokens_remaining == 60

    def test_record_iteration(self):
        g = BudgetGuard(max_iterations=3)
        g.record_iteration()
        g.record_iteration()
        assert g.iterations_done == 2
        assert g.iterations_remaining == 1

    def test_stop_on_token_limit(self):
        g = BudgetGuard(max_tokens=50)
        g.record_tokens(50)
        assert g.can_continue() is False
        assert "token" in g.stop_reason().lower()

    def test_stop_on_iteration_limit(self):
        g = BudgetGuard(max_iterations=2)
        g.record_iteration()
        g.record_iteration()
        assert g.can_continue() is False
        assert "iteration" in g.stop_reason().lower()

    def test_stop_on_time_limit(self):
        g = BudgetGuard(max_seconds=0.01)
        g.start()
        time.sleep(0.02)
        assert g.can_continue() is False
        assert "time" in g.stop_reason().lower()

    def test_stop_reason_none_when_ok(self):
        g = BudgetGuard()
        assert g.stop_reason() is None

    def test_elapsed_without_start(self):
        g = BudgetGuard()
        assert g.elapsed_seconds == 0.0

    def test_summary(self):
        g = BudgetGuard(max_tokens=1000, max_iterations=3, max_seconds=300)
        g.start()
        g.record_tokens(150)
        g.record_iteration()
        s = g.summary()
        assert s["tokens_used"] == 150
        assert s["tokens_max"] == 1000
        assert s["iterations_done"] == 1
        assert s["iterations_max"] == 3
        assert isinstance(s["elapsed_seconds"], float)

    def test_tokens_remaining_never_negative(self):
        g = BudgetGuard(max_tokens=10)
        g.record_tokens(100)
        assert g.tokens_remaining == 0


# ═══════════════════════════════════════════════════════════════════════════
# 2 — TestRunner
# ═══════════════════════════════════════════════════════════════════════════


class TestTestResult:
    """Tests for the TestResult dataclass."""

    def test_summary_line_pass(self):
        r = TestResult(passed=True, total=10, failures=0, errors=0)
        line = r.summary_line()
        assert "PASS" in line
        assert "10 tests" in line

    def test_summary_line_fail(self):
        r = TestResult(passed=False, total=10, failures=2, errors=0)
        line = r.summary_line()
        assert "FAIL" in line
        assert "2 failures" in line

    def test_summary_line_errors(self):
        r = TestResult(passed=False, total=10, failures=1, errors=2)
        line = r.summary_line()
        assert "2 errors" in line


class TestTestRunnerParsing:
    """Tests for TestRunner._parse_summary regex parsing."""

    def test_parse_all_passed(self):
        total, failures, errors = _parse_summary("10 passed in 2.34s")
        assert total == 10
        assert failures == 0
        assert errors == 0

    def test_parse_mixed(self):
        total, failures, errors = _parse_summary("8 passed, 2 failed in 5.67s")
        assert total == 10
        assert failures == 2
        assert errors == 0

    def test_parse_errors(self):
        total, failures, errors = _parse_summary("5 passed, 1 failed, 2 errors in 3.0s")
        assert total == 8
        assert failures == 1
        assert errors == 2

    def test_parse_empty(self):
        total, failures, errors = _parse_summary("")
        assert total == 0
        assert failures == 0


# ═══════════════════════════════════════════════════════════════════════════
# 3 — CommitManager
# ═══════════════════════════════════════════════════════════════════════════


class TestCommitManager:
    """Tests for CommitManager git operations (mocked subprocess)."""

    def test_has_changes_true(self):
        cm = CommitManager(project_root=_PROJECT_ROOT)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="M  foo.py\n", returncode=0
            )
            assert cm.has_changes() is True

    def test_has_changes_false(self):
        cm = CommitManager(project_root=_PROJECT_ROOT)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", returncode=0)
            assert cm.has_changes() is False

    def test_git_diff(self):
        cm = CommitManager(project_root=_PROJECT_ROOT)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="+added line\n-removed line\n", returncode=0
            )
            diff = cm.git_diff()
            assert "+added line" in diff

    def test_commit_returns_sha(self):
        cm = CommitManager(project_root=_PROJECT_ROOT)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="abc1234\n", returncode=0
            )
            sha = cm.commit("test message")
            assert sha == "abc1234"

    def test_stage_files(self):
        cm = CommitManager(project_root=_PROJECT_ROOT)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            cm.stage_files(["a.py", "b.py"])
            args = mock_run.call_args[0][0]
            assert "add" in args
            assert "a.py" in args
            assert "b.py" in args

    def test_revert_files(self):
        cm = CommitManager(project_root=_PROJECT_ROOT)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            cm.revert_files(["c.py"])
            args = mock_run.call_args[0][0]
            assert "checkout" in args
            assert "c.py" in args


# ═══════════════════════════════════════════════════════════════════════════
# 4 — TaskSelector
# ═══════════════════════════════════════════════════════════════════════════


class TestEvolutionTask:
    """Tests for the EvolutionTask dataclass."""

    def test_basic_construction(self):
        t = EvolutionTask(
            category=TASK_TYPE_HINTS,
            description="Add return types to foo.py",
            target_files=["foo.py"],
        )
        assert t.category == TASK_TYPE_HINTS
        assert len(t.target_files) == 1
        assert t.context_hint == ""


class TestTaskSelector:
    """Tests for priority-based task selection."""

    def test_fix_tests_has_highest_priority(self):
        runner = MagicMock()
        cm = MagicMock()
        sel = TaskSelector(
            project_root=_PROJECT_ROOT,
            test_runner=runner,
            commit_manager=cm,
        )
        failed_result = TestResult(
            passed=False, total=7, failures=2, errors=0,
            output="FAILED tests/test_foo.py::test_bar - AssertionError",
            return_code=1,
        )
        task = sel.select(failed_result)
        assert task.category == TASK_FIX_TESTS

    def test_fallback_to_generic(self):
        """With no test failures and no code issues -> small optimisation."""
        runner = MagicMock()
        cm = MagicMock()
        sel = TaskSelector(
            project_root=_PROJECT_ROOT,
            test_runner=runner,
            commit_manager=cm,
        )
        passing = TestResult(passed=10, total=10, failures=0, errors=0, return_code=0)
        with patch.object(sel, "_find_type_hint_task", return_value=None), \
             patch.object(sel, "_find_error_handling_task", return_value=None), \
             patch.object(sel, "_find_duplication_task", return_value=None):
            task = sel.select(passing)
            assert task.category == TASK_SMALL_OPTIMISATION

    def test_task_categories_are_strings(self):
        assert isinstance(TASK_FIX_TESTS, str)
        assert isinstance(TASK_TYPE_HINTS, str)
        assert isinstance(TASK_ERROR_HANDLING, str)
        assert isinstance(TASK_REDUCE_DUPLICATION, str)
        assert isinstance(TASK_SMALL_OPTIMISATION, str)


# ═══════════════════════════════════════════════════════════════════════════
# 5 — ContextBuilder
# ═══════════════════════════════════════════════════════════════════════════


class TestContextBuilder:
    """Tests for context assembly."""

    def test_system_prompt_exists(self):
        assert len(SYSTEM_PROMPT) > 100
        assert "diff" in SYSTEM_PROMPT.lower()

    def test_estimate_tokens(self):
        cm = MagicMock()
        cb = ContextBuilder(project_root=_PROJECT_ROOT, commit_manager=cm)
        # 11 chars // 4 = 2 (floor division), min 1
        assert cb.estimate_tokens("hello world") == 2
        assert cb.estimate_tokens("hi") == 1  # min clamp

    def test_build_includes_task(self):
        cm = MagicMock()
        cm.git_diff.return_value = ""
        cb = ContextBuilder(project_root=_PROJECT_ROOT, commit_manager=cm)
        task = EvolutionTask(
            category="test_cat",
            description="Do something helpful",
            target_files=[],
        )
        ctx = cb.build(task)
        assert "Do something helpful" in ctx
        assert "test_cat" in ctx

    def test_build_truncates_large_content(self):
        cm = MagicMock()
        cm.git_diff.return_value = ""
        cb = ContextBuilder(
            project_root=_PROJECT_ROOT,
            commit_manager=cm,
            max_context_tokens=50,
        )
        task = EvolutionTask(
            category="demo",
            description="truncation test",
            target_files=[],
            context_hint="A" * 10000,
        )
        ctx = cb.build(task)
        assert len(ctx) < 10000


# ═══════════════════════════════════════════════════════════════════════════
# 6 — PatchGenerator — diff helpers
# ═══════════════════════════════════════════════════════════════════════════


class TestDiffExtraction:
    """Tests for _extract_diff from LLM output."""

    def test_fenced_diff_block(self):
        text = textwrap.dedent("""\
            Here is the patch:

            ```diff
            --- a/foo.py
            +++ b/foo.py
            @@ -1,3 +1,3 @@
            -old line
            +new line
             context
            ```
        """)
        diff = _extract_diff(text)
        assert "--- a/foo.py" in diff
        assert "+new line" in diff

    def test_raw_diff_without_fence(self):
        text = textwrap.dedent("""\
            --- a/bar.py
            +++ b/bar.py
            @@ -10,4 +10,5 @@
             context
            -removed
            +added
            +another
        """)
        diff = _extract_diff(text)
        assert "--- a/bar.py" in diff
        assert "+added" in diff

    def test_no_diff_returns_empty(self):
        text = "Just some regular text with no diff."
        diff = _extract_diff(text)
        assert diff == ""


class TestDiffFiles:
    """Tests for _diff_files extraction."""

    def test_single_file(self):
        diff = "--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-x\n+y"
        files = _diff_files(diff)
        assert files == ["foo.py"]

    def test_multiple_files(self):
        diff = (
            "--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-x\n+y\n"
            "--- a/b.py\n+++ b/b.py\n@@ -1 +1 @@\n-x\n+y"
        )
        files = _diff_files(diff)
        assert "a.py" in files
        assert "b.py" in files

    def test_dev_null_excluded(self):
        diff = "--- /dev/null\n+++ b/new.py\n@@ -0,0 +1 @@\n+new"
        files = _diff_files(diff)
        assert files == ["new.py"]


class TestDiffLineCount:
    """Tests for _diff_line_count."""

    def test_counts_adds_and_removes(self):
        diff = (
            "--- a/foo.py\n+++ b/foo.py\n@@ -1,3 +1,3 @@\n"
            " ctx\n-removed\n+added\n ctx\n"
        )
        assert _diff_line_count(diff) == 2

    def test_ignores_header_lines(self):
        diff = "--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-x\n+y"
        assert _diff_line_count(diff) == 2


class TestPatchResult:
    """Tests for the PatchResult dataclass."""

    def test_default_is_failure(self):
        r = PatchResult()
        assert r.success is False
        assert r.files_changed == []

    def test_to_dict(self):
        r = PatchResult(success=True, files_changed=["a.py"], lines_changed=5)
        d = r.to_dict()
        assert d["success"] is True
        assert d["files_changed"] == ["a.py"]


class TestPatchGeneratorSafety:
    """Tests for PatchGenerator safety limits with mock LLM."""

    def test_rejects_too_many_files(self):
        provider = MockProvider()
        lines = []
        for i in range(5):
            lines.append(f"--- a/f{i}.py")
            lines.append(f"+++ b/f{i}.py")
            lines.append("@@ -1 +1 @@")
            lines.append(f"-old{i}")
            lines.append(f"+new{i}")
        diff_text = "\n".join(lines)
        provider.enqueue_response(f"```diff\n{diff_text}\n```")

        budget = BudgetGuard(max_tokens=50000)
        cm = MagicMock()
        cm.git_diff.return_value = ""
        cb = ContextBuilder(project_root=_PROJECT_ROOT, commit_manager=cm)
        pg = PatchGenerator(
            project_root=_PROJECT_ROOT,
            provider=provider,
            context_builder=cb,
            budget=budget,
        )
        task = EvolutionTask(category="test", description="test", target_files=[])
        result = pg.generate_and_apply(task)
        assert result.success is False
        assert "files" in result.error.lower()

    def test_rejects_when_budget_exceeded(self):
        provider = MockProvider()
        budget = BudgetGuard(max_tokens=10)
        budget.record_tokens(10)

        cm = MagicMock()
        cm.git_diff.return_value = ""
        cb = ContextBuilder(project_root=_PROJECT_ROOT, commit_manager=cm)
        pg = PatchGenerator(
            project_root=_PROJECT_ROOT,
            provider=provider,
            context_builder=cb,
            budget=budget,
        )
        task = EvolutionTask(category="test", description="test", target_files=[])
        result = pg.generate_and_apply(task)
        assert result.success is False
        assert "budget" in result.error.lower()

    def test_handles_llm_returning_no_diff(self):
        provider = MockProvider()
        provider.enqueue_response("Sorry, I cannot generate a diff for this.")

        budget = BudgetGuard(max_tokens=50000)
        cm = MagicMock()
        cm.git_diff.return_value = ""
        cb = ContextBuilder(project_root=_PROJECT_ROOT, commit_manager=cm)
        pg = PatchGenerator(
            project_root=_PROJECT_ROOT,
            provider=provider,
            context_builder=cb,
            budget=budget,
        )
        task = EvolutionTask(category="test", description="test", target_files=[])
        result = pg.generate_and_apply(task)
        assert result.success is False
        assert "valid" in result.error.lower() or "diff" in result.error.lower()


# ═══════════════════════════════════════════════════════════════════════════
# 7 — Engine — IterationRecord and EvolutionResult
# ═══════════════════════════════════════════════════════════════════════════


class TestIterationRecord:
    """Tests for the IterationRecord dataclass."""

    def test_to_dict(self):
        r = IterationRecord(
            iteration=1,
            task_category="type_hints",
            task_description="Add types",
            committed=True,
            commit_sha="abc123",
        )
        d = r.to_dict()
        assert d["iteration"] == 1
        assert d["committed"] is True
        assert d["commit_sha"] == "abc123"


class TestEvolutionResult:
    """Tests for the EvolutionResult aggregate."""

    def test_to_dict(self):
        r = EvolutionResult(
            iterations_completed=2,
            commits=["abc", "def"],
            reverts=1,
            stop_reason="iteration limit reached (2)",
        )
        d = r.to_dict()
        assert d["iterations_completed"] == 2
        assert len(d["commits"]) == 2
        assert d["reverts"] == 1


class TestEvolutionEngineOrchestration:
    """Tests for the EvolutionEngine loop with mocked components."""

    def test_engine_runs_iterations(self, tmp_path):
        """Engine should run iterations and respect budget."""
        provider = MockProvider()
        provider.enqueue_response("no diff here")
        provider.enqueue_response("no diff here")

        budget = BudgetGuard(max_tokens=50000, max_iterations=2, max_seconds=60)

        with patch.object(TestRunner, "run") as mock_test_run, \
             patch.object(CommitManager, "has_changes", return_value=False):
            mock_test_run.return_value = TestResult(
                passed=10, total=10, failures=0, errors=0, return_code=0,
            )

            engine = EvolutionEngine(
                project_root=tmp_path,
                provider=provider,
                budget=budget,
            )
            result = engine.run()

        assert result.iterations_completed == 2
        assert result.stop_reason is not None
        assert len(result.history) == 2

    def test_engine_writes_history(self, tmp_path):
        """Engine should persist evolution_history.json."""
        provider = MockProvider()
        provider.enqueue_response("no diff")
        budget = BudgetGuard(max_tokens=50000, max_iterations=1, max_seconds=60)

        with patch.object(TestRunner, "run") as mock_test_run, \
             patch.object(CommitManager, "has_changes", return_value=False):
            mock_test_run.return_value = TestResult(
                passed=5, total=5, failures=0, errors=0, return_code=0,
            )

            engine = EvolutionEngine(
                project_root=tmp_path,
                provider=provider,
                budget=budget,
            )
            engine.run()

        history_file = tmp_path / ".codexa" / "evolution_history.json"
        assert history_file.exists()
        data = json.loads(history_file.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 8 — CLI command
# ═══════════════════════════════════════════════════════════════════════════


class TestEvolveCLI:
    """Tests for the evolve CLI command."""

    def test_command_exists(self):
        from semantic_code_intelligence.cli.commands.evolve_cmd import evolve_cmd
        assert evolve_cmd.name == "evolve"

    def test_command_has_options(self):
        from semantic_code_intelligence.cli.commands.evolve_cmd import evolve_cmd
        param_names = [p.name for p in evolve_cmd.params]
        assert "iterations" in param_names
        assert "budget" in param_names
        assert "timeout" in param_names
        assert "path" in param_names

    def test_command_registered_in_router(self):
        from semantic_code_intelligence.cli.router import register_commands
        group = MagicMock(spec=["add_command"])
        register_commands(group)
        added_names = [call.args[0].name for call in group.add_command.call_args_list]
        assert "evolve" in added_names

    def test_help_mentions_evolve(self):
        from click.testing import CliRunner
        from semantic_code_intelligence.cli.commands.evolve_cmd import evolve_cmd
        runner = CliRunner()
        result = runner.invoke(evolve_cmd, ["--help"])
        assert result.exit_code == 0
        assert "self-improving" in result.output.lower() or "evolve" in result.output.lower()


# ═══════════════════════════════════════════════════════════════════════════
# 9 — Module imports and version
# ═══════════════════════════════════════════════════════════════════════════


class TestModuleImports:
    """Verify that all Phase 24 modules are importable."""

    def test_import_budget_guard(self):
        from semantic_code_intelligence.evolution import budget_guard
        assert hasattr(budget_guard, "BudgetGuard")

    def test_import_test_runner(self):
        from semantic_code_intelligence.evolution import test_runner
        assert hasattr(test_runner, "TestRunner")
        assert hasattr(test_runner, "TestResult")

    def test_import_commit_manager(self):
        from semantic_code_intelligence.evolution import commit_manager
        assert hasattr(commit_manager, "CommitManager")

    def test_import_task_selector(self):
        from semantic_code_intelligence.evolution import task_selector
        assert hasattr(task_selector, "TaskSelector")
        assert hasattr(task_selector, "EvolutionTask")

    def test_import_context_builder(self):
        from semantic_code_intelligence.evolution import context_builder
        assert hasattr(context_builder, "ContextBuilder")
        assert hasattr(context_builder, "SYSTEM_PROMPT")

    def test_import_patch_generator(self):
        from semantic_code_intelligence.evolution import patch_generator
        assert hasattr(patch_generator, "PatchGenerator")
        assert hasattr(patch_generator, "PatchResult")

    def test_import_engine(self):
        from semantic_code_intelligence.evolution import engine
        assert hasattr(engine, "EvolutionEngine")
        assert hasattr(engine, "EvolutionResult")
        assert hasattr(engine, "IterationRecord")

    def test_import_evolve_cmd(self):
        from semantic_code_intelligence.cli.commands import evolve_cmd
        assert hasattr(evolve_cmd, "evolve_cmd")


class TestVersion:
    """Verify the project version reflects Phase 24."""

    def test_version_is_0_24_0(self):
        from semantic_code_intelligence import __version__
        assert __version__ == "0.30.0"
