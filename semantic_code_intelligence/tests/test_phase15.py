"""Tests for Phase 15 — CI/CD and Contribution Safety Pipeline.

Covers: quality analyzers, PR intelligence, CI templates, pre-commit
hooks, CLI commands, router registration, version bump, module imports.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from semantic_code_intelligence.parsing.parser import Symbol

# =========================================================================
# Quality analyzer tests
# =========================================================================


class TestComplexity:
    """Tests for cyclomatic complexity analysis."""

    def _sym(self, name: str, body: str, kind: str = "function") -> Symbol:
        return Symbol(
            name=name,
            kind=kind,
            file_path="test.py",
            start_line=1,
            end_line=10,
            start_col=0,
            end_col=0,
            body=body,
        )

    def test_simple_function_low(self):
        from semantic_code_intelligence.ci.quality import compute_complexity

        sym = self._sym("hello", "def hello():\n    return 1\n")
        result = compute_complexity(sym)
        assert result.complexity >= 1
        assert result.rating == "low"

    def test_branching_function(self):
        from semantic_code_intelligence.ci.quality import compute_complexity

        body = textwrap.dedent("""\
            def check(x):
                if x > 0:
                    if x > 10:
                        return "big"
                    elif x > 5:
                        return "medium"
                    else:
                        return "small"
                for i in range(x):
                    if i % 2 == 0:
                        continue
                while x > 0:
                    x -= 1
                return x
        """)
        sym = self._sym("check", body)
        result = compute_complexity(sym)
        # 1 base + if + if + elif + for + if + while = 7
        assert result.complexity >= 7
        assert result.rating in ("moderate", "high")

    def test_analyze_complexity_threshold(self):
        from semantic_code_intelligence.ci.quality import analyze_complexity

        simple = self._sym("simple", "def simple():\n    pass\n")
        complex_body = "\n".join(
            f"    if x == {i}:" for i in range(12)
        )
        hard = self._sym("hard", f"def hard(x):\n{complex_body}\n")
        results = analyze_complexity([simple, hard], threshold=5)
        assert len(results) >= 1
        assert results[0].symbol_name == "hard"

    def test_skips_classes(self):
        from semantic_code_intelligence.ci.quality import analyze_complexity

        cls = self._sym("MyClass", "class MyClass:\n    pass\n", kind="class")
        results = analyze_complexity([cls], threshold=1)
        assert len(results) == 0

    def test_rating_scale(self):
        from semantic_code_intelligence.ci.quality import _rate_complexity

        assert _rate_complexity(3) == "low"
        assert _rate_complexity(8) == "moderate"
        assert _rate_complexity(15) == "high"
        assert _rate_complexity(25) == "very_high"


class TestDeadCode:
    """Tests for dead code detection."""

    def _sym(self, name: str, kind: str = "function", body: str = "pass") -> Symbol:
        return Symbol(
            name=name,
            kind=kind,
            file_path="test.py",
            start_line=1,
            end_line=2,
            start_col=0,
            end_col=0,
            body=body,
        )

    def test_empty_input(self):
        from semantic_code_intelligence.ci.quality import detect_dead_code

        assert detect_dead_code([]) == []

    def test_entry_point_excluded(self):
        from semantic_code_intelligence.ci.quality import detect_dead_code

        sym = self._sym("main")
        assert detect_dead_code([sym]) == []

    def test_test_functions_excluded(self):
        from semantic_code_intelligence.ci.quality import detect_dead_code

        sym = self._sym("test_something")
        assert detect_dead_code([sym]) == []

    def test_unreferenced_detected(self):
        from semantic_code_intelligence.ci.quality import detect_dead_code

        sym = self._sym("orphan_func", body="def orphan_func():\n    return 42\n")
        results = detect_dead_code([sym])
        assert len(results) == 1
        assert results[0].symbol_name == "orphan_func"

    def test_referenced_not_dead(self):
        from semantic_code_intelligence.ci.quality import detect_dead_code

        caller = self._sym("caller", body="def caller():\n    helper()\n")
        helper = self._sym("helper", body="def helper():\n    pass\n")
        results = detect_dead_code([caller, helper])
        helper_names = [r.symbol_name for r in results]
        assert "helper" not in helper_names

    def test_imports_excluded(self):
        from semantic_code_intelligence.ci.quality import detect_dead_code

        imp = self._sym("os", kind="import")
        assert detect_dead_code([imp]) == []


class TestDuplicates:
    """Tests for duplicate logic detection."""

    def _sym(self, name: str, body: str, file_path: str = "a.py") -> Symbol:
        return Symbol(
            name=name,
            kind="function",
            file_path=file_path,
            start_line=1,
            end_line=10,
            start_col=0,
            end_col=0,
            body=body,
        )

    def test_empty_input(self):
        from semantic_code_intelligence.ci.quality import detect_duplicates

        assert detect_duplicates([]) == []

    def test_identical_bodies(self):
        from semantic_code_intelligence.ci.quality import detect_duplicates

        body = "def f(x):\n    result = x + 1\n    result *= 2\n    return result\n    # extra\n"
        sym_a = self._sym("func_a", body, "a.py")
        sym_b = self._sym("func_b", body, "b.py")
        results = detect_duplicates([sym_a, sym_b], threshold=0.7)
        assert len(results) == 1
        assert results[0].similarity >= 0.9

    def test_different_bodies(self):
        from semantic_code_intelligence.ci.quality import detect_duplicates

        body_a = "def a():\n    return 1\n    x = 2\n    y = 3\n"
        body_b = "def b():\n    for i in range(100):\n        print(i)\n        z = i * 2\n"
        sym_a = self._sym("a", body_a)
        sym_b = self._sym("b", body_b)
        results = detect_duplicates([sym_a, sym_b], threshold=0.9)
        assert len(results) == 0

    def test_short_bodies_skipped(self):
        from semantic_code_intelligence.ci.quality import detect_duplicates

        body = "pass"
        sym_a = self._sym("a", body)
        sym_b = self._sym("b", body)
        results = detect_duplicates([sym_a, sym_b], min_lines=4)
        assert len(results) == 0

    def test_jaccard_basics(self):
        from semantic_code_intelligence.ci.quality import _jaccard

        assert _jaccard(set(), set()) == 1.0
        assert _jaccard({"a", "b"}, {"a", "b"}) == 1.0
        assert _jaccard({"a"}, set()) == 0.0


class TestQualityReport:
    """Tests for aggregate quality report."""

    def test_report_to_dict(self):
        from semantic_code_intelligence.ci.quality import QualityReport

        report = QualityReport(files_analyzed=5, symbol_count=20)
        d = report.to_dict()
        assert d["files_analyzed"] == 5
        assert d["symbol_count"] == 20
        assert d["issue_count"] == 0

    def test_issue_count_aggregation(self):
        from semantic_code_intelligence.ci.quality import (
            QualityReport,
            ComplexityResult,
            DeadCodeResult,
            DuplicateResult,
        )
        from semantic_code_intelligence.llm.safety import SafetyReport, SafetyIssue

        report = QualityReport(
            complexity_issues=[ComplexityResult("f", "a.py", 1, 10, 15, "high")],
            dead_code=[DeadCodeResult("g", "function", "b.py", 1)],
            duplicates=[DuplicateResult("a", "a.py", 1, "b", "b.py", 1, 0.9)],
            safety=SafetyReport(safe=False, issues=[SafetyIssue("p", "d", 1)]),
        )
        assert report.issue_count == 4


class TestAnalyzeProject:
    """Tests for project-level analysis."""

    def test_analyze_empty_dir(self, tmp_path):
        from semantic_code_intelligence.ci.quality import analyze_project

        report = analyze_project(tmp_path)
        assert report.files_analyzed == 0
        assert report.issue_count == 0

    def test_analyze_with_file(self, tmp_path):
        from semantic_code_intelligence.ci.quality import analyze_project

        py_file = tmp_path / "hello.py"
        py_file.write_text("def hello():\n    return 1\n", encoding="utf-8")
        report = analyze_project(tmp_path, file_paths=[str(py_file)])
        assert report.files_analyzed == 1
        assert report.symbol_count >= 1


# =========================================================================
# PR intelligence tests
# =========================================================================


class TestChangeSummary:
    """Tests for change summary generation."""

    def test_empty_files(self):
        from semantic_code_intelligence.ci.pr import build_change_summary

        result = build_change_summary([])
        assert result.files_changed == 0
        assert result.to_dict()["files_changed"] == 0

    def test_with_python_file(self, tmp_path):
        from semantic_code_intelligence.ci.pr import build_change_summary

        f = tmp_path / "test.py"
        f.write_text("def hello():\n    pass\n", encoding="utf-8")
        result = build_change_summary([str(f)])
        assert result.files_changed == 1
        assert "python" in result.languages

    def test_nonsupported_file(self, tmp_path):
        from semantic_code_intelligence.ci.pr import build_change_summary

        f = tmp_path / "readme.txt"
        f.write_text("Hello world", encoding="utf-8")
        result = build_change_summary([str(f)])
        assert result.files_changed == 1
        d = result.file_details[0]
        assert d.language is None

    def test_symbols_detected(self, tmp_path):
        from semantic_code_intelligence.ci.pr import build_change_summary

        f = tmp_path / "main.py"
        f.write_text("def foo():\n    pass\n\ndef bar():\n    pass\n", encoding="utf-8")
        result = build_change_summary([str(f)])
        fd = result.file_details[0]
        assert "foo" in fd.symbols_added
        assert "bar" in fd.symbols_added


class TestImpactAnalysis:
    """Tests for semantic impact analysis."""

    def test_impact_empty(self, tmp_path):
        from semantic_code_intelligence.ci.pr import analyze_impact

        result = analyze_impact([], tmp_path)
        assert result.changed_symbols == []
        assert result.to_dict()["affected_files"] == []

    def test_impact_with_file(self, tmp_path):
        from semantic_code_intelligence.ci.pr import analyze_impact

        f = tmp_path / "lib.py"
        f.write_text("def helper():\n    pass\n", encoding="utf-8")
        result = analyze_impact([str(f)], tmp_path)
        assert "helper" in result.changed_symbols


class TestSuggestReviewers:
    """Tests for reviewer suggestion."""

    def test_empty(self):
        from semantic_code_intelligence.ci.pr import suggest_reviewers

        assert suggest_reviewers([]) == []

    def test_domain_grouping(self):
        from semantic_code_intelligence.ci.pr import suggest_reviewers

        files = ["src/auth/login.py", "src/auth/logout.py", "src/db/models.py"]
        result = suggest_reviewers(files)
        domains = [r["domain"] for r in result]
        assert len(result) >= 2
        assert any("auth" in d for d in domains)


class TestRiskScoring:
    """Tests for risk severity scoring."""

    def test_zero_risk(self):
        from semantic_code_intelligence.ci.pr import compute_risk, ChangeSummary

        cs = ChangeSummary(files_changed=0)
        risk = compute_risk(cs)
        assert risk.score == 0
        assert risk.level == "low"

    def test_large_changeset(self):
        from semantic_code_intelligence.ci.pr import compute_risk, ChangeSummary

        cs = ChangeSummary(files_changed=25, total_symbols_removed=15)
        risk = compute_risk(cs)
        assert risk.score >= 30
        assert risk.level in ("medium", "high", "critical")

    def test_safety_issues_increase_risk(self):
        from semantic_code_intelligence.ci.pr import compute_risk, ChangeSummary
        from semantic_code_intelligence.llm.safety import SafetyReport, SafetyIssue

        cs = ChangeSummary(files_changed=1)
        safety = SafetyReport(safe=False, issues=[
            SafetyIssue("p", "eval detected", 1),
            SafetyIssue("p", "exec detected", 2),
        ])
        risk = compute_risk(cs, safety_report=safety)
        assert risk.score >= 20
        assert any("safety" in f.lower() for f in risk.factors)

    def test_risk_level_function(self):
        from semantic_code_intelligence.ci.pr import _risk_level

        assert _risk_level(10) == "low"
        assert _risk_level(30) == "medium"
        assert _risk_level(60) == "high"
        assert _risk_level(80) == "critical"


class TestPRReport:
    """Tests for full PR report generation."""

    def test_report_to_dict(self):
        from semantic_code_intelligence.ci.pr import (
            PRReport,
            ChangeSummary,
            RiskScore,
        )

        report = PRReport(
            change_summary=ChangeSummary(files_changed=1),
            risk=RiskScore(score=10, level="low"),
        )
        d = report.to_dict()
        assert d["change_summary"]["files_changed"] == 1
        assert d["risk"]["score"] == 10

    def test_generate_pr_report_empty(self, tmp_path):
        from semantic_code_intelligence.ci.pr import generate_pr_report

        report = generate_pr_report([], tmp_path)
        assert report.change_summary.files_changed == 0
        assert report.risk is not None


# =========================================================================
# CI template tests
# =========================================================================


class TestTemplates:
    """Tests for CI workflow template generation."""

    def test_analysis_workflow(self):
        from semantic_code_intelligence.ci.templates import generate_analysis_workflow

        content = generate_analysis_workflow()
        assert "CodexA Analysis" in content
        assert "codexa quality" in content
        assert "codexa pr-summary" in content
        assert "pull_request" in content

    def test_analysis_custom_python(self):
        from semantic_code_intelligence.ci.templates import generate_analysis_workflow

        content = generate_analysis_workflow(python_version="3.13")
        assert "3.13" in content

    def test_safety_workflow(self):
        from semantic_code_intelligence.ci.templates import generate_safety_workflow

        content = generate_safety_workflow()
        assert "CodexA Safety" in content
        assert "--safety-only" in content

    def test_precommit_config(self):
        from semantic_code_intelligence.ci.templates import generate_precommit_config

        content = generate_precommit_config()
        assert "codexa-safety" in content
        assert "codexa-quality" in content
        assert "pre-commit" in content.lower()

    def test_template_registry(self):
        from semantic_code_intelligence.ci.templates import TEMPLATES

        assert "analysis" in TEMPLATES
        assert "safety" in TEMPLATES
        assert "precommit" in TEMPLATES

    def test_get_template(self):
        from semantic_code_intelligence.ci.templates import get_template

        content = get_template("analysis")
        assert "codexa quality" in content

    def test_get_template_unknown(self):
        from semantic_code_intelligence.ci.templates import get_template

        with pytest.raises(KeyError):
            get_template("nonexistent")


# =========================================================================
# Pre-commit hook tests
# =========================================================================


class TestPrecommitHooks:
    """Tests for pre-commit validation hooks."""

    def test_empty_files(self):
        from semantic_code_intelligence.ci.hooks import run_precommit_check

        result = run_precommit_check([])
        assert result.passed is True
        assert result.files_checked == 0

    def test_safe_file(self, tmp_path):
        from semantic_code_intelligence.ci.hooks import run_precommit_check

        f = tmp_path / "safe.py"
        f.write_text("def hello():\n    return 1\n", encoding="utf-8")
        result = run_precommit_check([str(f)])
        assert result.passed is True

    def test_unsafe_file(self, tmp_path):
        from semantic_code_intelligence.ci.hooks import run_precommit_check

        f = tmp_path / "unsafe.py"
        f.write_text("import os\nos.system('rm -rf /')\n", encoding="utf-8")
        result = run_precommit_check([str(f)])
        assert result.passed is False
        assert result.safety is not None
        assert not result.safety.safe

    def test_result_to_dict(self):
        from semantic_code_intelligence.ci.hooks import HookResult

        result = HookResult(passed=True, files_checked=3)
        d = result.to_dict()
        assert d["passed"] is True
        assert d["files_checked"] == 3


# =========================================================================
# CLI command tests
# =========================================================================


class TestQualityCLI:
    """Tests for the `codexa quality` command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_help(self, runner):
        from semantic_code_intelligence.cli.commands.quality_cmd import quality_cmd

        result = runner.invoke(quality_cmd, ["--help"])
        assert result.exit_code == 0
        assert "quality" in result.output.lower() or "complexity" in result.output.lower()

    def test_has_json_option(self, runner):
        from semantic_code_intelligence.cli.commands.quality_cmd import quality_cmd

        result = runner.invoke(quality_cmd, ["--help"])
        assert "--json" in result.output

    def test_has_safety_only(self, runner):
        from semantic_code_intelligence.cli.commands.quality_cmd import quality_cmd

        result = runner.invoke(quality_cmd, ["--help"])
        assert "--safety-only" in result.output

    def test_has_pipe(self, runner):
        from semantic_code_intelligence.cli.commands.quality_cmd import quality_cmd

        result = runner.invoke(quality_cmd, ["--help"])
        assert "--pipe" in result.output

    def test_json_output(self, runner, tmp_path):
        from semantic_code_intelligence.cli.commands.quality_cmd import quality_cmd

        result = runner.invoke(quality_cmd, ["--json", "--path", str(tmp_path)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "files_analyzed" in data

    def test_safety_only_mode(self, runner, tmp_path):
        from semantic_code_intelligence.cli.commands.quality_cmd import quality_cmd

        result = runner.invoke(quality_cmd, [
            "--safety-only", "--pipe", "--path", str(tmp_path)
        ])
        assert result.exit_code == 0
        assert "PASS" in result.output or "FAIL" in result.output

    def test_pipe_mode(self, runner, tmp_path):
        from semantic_code_intelligence.cli.commands.quality_cmd import quality_cmd

        result = runner.invoke(quality_cmd, ["--pipe", "--path", str(tmp_path)])
        assert result.exit_code == 0
        assert "Files:" in result.output


class TestPRSummaryCLI:
    """Tests for the `codexa pr-summary` command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_help(self, runner):
        from semantic_code_intelligence.cli.commands.pr_summary_cmd import pr_summary_cmd

        result = runner.invoke(pr_summary_cmd, ["--help"])
        assert result.exit_code == 0
        assert "pr-summary" in result.output.lower() or "pull request" in result.output.lower()

    def test_has_json_option(self, runner):
        from semantic_code_intelligence.cli.commands.pr_summary_cmd import pr_summary_cmd

        result = runner.invoke(pr_summary_cmd, ["--help"])
        assert "--json" in result.output

    def test_has_files_option(self, runner):
        from semantic_code_intelligence.cli.commands.pr_summary_cmd import pr_summary_cmd

        result = runner.invoke(pr_summary_cmd, ["--help"])
        assert "--files" in result.output or "-f" in result.output

    def test_json_with_specific_file(self, runner, tmp_path):
        from semantic_code_intelligence.cli.commands.pr_summary_cmd import pr_summary_cmd

        f = tmp_path / "main.py"
        f.write_text("def hello():\n    pass\n", encoding="utf-8")
        result = runner.invoke(pr_summary_cmd, [
            "--json", "-f", str(f), "--path", str(tmp_path)
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "change_summary" in data

    def test_pipe_mode(self, runner, tmp_path):
        from semantic_code_intelligence.cli.commands.pr_summary_cmd import pr_summary_cmd

        f = tmp_path / "main.py"
        f.write_text("def foo():\n    pass\n", encoding="utf-8")
        result = runner.invoke(pr_summary_cmd, [
            "--pipe", "-f", str(f), "--path", str(tmp_path)
        ])
        assert result.exit_code == 0
        assert "Changed:" in result.output


class TestCIGenCLI:
    """Tests for the `codexa ci-gen` command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_help(self, runner):
        from semantic_code_intelligence.cli.commands.ci_gen_cmd import ci_gen_cmd

        result = runner.invoke(ci_gen_cmd, ["--help"])
        assert result.exit_code == 0
        assert "ci-gen" in result.output.lower() or "template" in result.output.lower()

    def test_analysis_template(self, runner):
        from semantic_code_intelligence.cli.commands.ci_gen_cmd import ci_gen_cmd

        result = runner.invoke(ci_gen_cmd, ["analysis"])
        assert result.exit_code == 0
        assert "CodexA Analysis" in result.output

    def test_safety_template(self, runner):
        from semantic_code_intelligence.cli.commands.ci_gen_cmd import ci_gen_cmd

        result = runner.invoke(ci_gen_cmd, ["safety"])
        assert result.exit_code == 0
        assert "CodexA Safety" in result.output

    def test_precommit_template(self, runner):
        from semantic_code_intelligence.ci.templates import generate_precommit_config
        from semantic_code_intelligence.cli.commands.ci_gen_cmd import ci_gen_cmd

        result = runner.invoke(ci_gen_cmd, ["precommit"])
        assert result.exit_code == 0
        assert "pre-commit" in result.output.lower()

    def test_output_to_file(self, runner, tmp_path):
        from semantic_code_intelligence.cli.commands.ci_gen_cmd import ci_gen_cmd

        outfile = tmp_path / "workflow.yml"
        result = runner.invoke(ci_gen_cmd, ["analysis", "-o", str(outfile)])
        assert result.exit_code == 0
        assert outfile.exists()
        content = outfile.read_text()
        assert "CodexA Analysis" in content

    def test_custom_python_version(self, runner):
        from semantic_code_intelligence.cli.commands.ci_gen_cmd import ci_gen_cmd

        result = runner.invoke(ci_gen_cmd, ["safety", "--python-version", "3.13"])
        assert result.exit_code == 0
        assert "3.13" in result.output


# =========================================================================
# Router, version, and module structure tests
# =========================================================================


class TestRouterPhase15:
    """Tests for CLI router registration."""

    def test_register_commands_count(self):
        import click
        from semantic_code_intelligence.cli.router import register_commands

        group = click.Group("test")
        register_commands(group)
        assert len(group.commands) == 38

    def test_quality_command_registered(self):
        from semantic_code_intelligence.cli.main import cli

        assert "quality" in cli.commands

    def test_pr_summary_command_registered(self):
        from semantic_code_intelligence.cli.main import cli

        assert "pr-summary" in cli.commands

    def test_ci_gen_command_registered(self):
        from semantic_code_intelligence.cli.main import cli

        assert "ci-gen" in cli.commands


class TestVersionBump:
    """Test version is 0.19.0."""

    def test_version_is_015(self):
        from semantic_code_intelligence import __version__

        assert __version__ == "0.29.0"


class TestCIModuleStructure:
    """Tests for module import structure."""

    def test_import_ci_package(self):
        import semantic_code_intelligence.ci

    def test_import_quality(self):
        from semantic_code_intelligence.ci.quality import (
            analyze_complexity,
            detect_dead_code,
            detect_duplicates,
            analyze_project,
            QualityReport,
        )

    def test_import_pr(self):
        from semantic_code_intelligence.ci.pr import (
            build_change_summary,
            analyze_impact,
            suggest_reviewers,
            compute_risk,
            generate_pr_report,
        )

    def test_import_templates(self):
        from semantic_code_intelligence.ci.templates import (
            generate_analysis_workflow,
            generate_safety_workflow,
            generate_precommit_config,
            get_template,
            TEMPLATES,
        )

    def test_import_hooks(self):
        from semantic_code_intelligence.ci.hooks import (
            run_precommit_check,
            HookResult,
        )


class TestDocsGenerator:
    """Tests for CI doc generation."""

    def test_generate_ci_reference(self):
        from semantic_code_intelligence.docs import generate_ci_reference

        md = generate_ci_reference()
        assert "CI/CD" in md
        assert "Quality" in md
        assert "codexa quality" in md
        assert "codexa pr-summary" in md
        assert "codexa ci-gen" in md

    def test_generate_all_docs_includes_ci(self, tmp_path):
        from semantic_code_intelligence.docs import generate_all_docs

        generated = generate_all_docs(tmp_path)
        assert "CI.md" in generated


# =========================================================================
# Backward compatibility tests
# =========================================================================


class TestBackwardCompatibility:
    """Ensure Phase 13 and Phase 14 modules still work."""

    def test_web_module_imports(self):
        from semantic_code_intelligence.web.api import APIHandler
        from semantic_code_intelligence.web.ui import page_search
        from semantic_code_intelligence.web.visualize import render_call_graph
        from semantic_code_intelligence.web.server import WebServer

    def test_docs_module_imports(self):
        from semantic_code_intelligence.docs import (
            generate_cli_reference,
            generate_plugin_reference,
            generate_bridge_reference,
            generate_tool_reference,
            generate_web_reference,
            generate_ci_reference,
        )

    def test_plugin_hooks_intact(self):
        from semantic_code_intelligence.plugins import PluginHook

        assert len(PluginHook) == 22
        assert PluginHook.CUSTOM_VALIDATION.value == "custom_validation"

    def test_safety_validator_intact(self):
        from semantic_code_intelligence.llm.safety import SafetyValidator

        validator = SafetyValidator()
        report = validator.validate("x = 1\n")
        assert report.safe is True
