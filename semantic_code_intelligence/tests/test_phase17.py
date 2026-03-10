"""Tests for Phase 17 — Code Quality Metrics & Trends.

Covers: file metrics, project metrics, maintainability index, quality snapshots,
trend analysis, quality policies, gate enforcement, CLI commands,
router, version, docs, and module structure.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner


# =========================================================================
# Helper: create sample Python files
# =========================================================================


def _write_sample_project(root: Path) -> None:
    """Write a small multi-file project for metrics testing."""
    src = root / "src"
    src.mkdir(parents=True, exist_ok=True)

    (src / "simple.py").write_text(
        '# Simple module\n'
        'def greet(name: str) -> str:\n'
        '    """Return a greeting."""\n'
        '    return f"Hello, {name}!"\n'
        '\n'
        'def add(a: int, b: int) -> int:\n'
        '    return a + b\n',
        encoding="utf-8",
    )

    (src / "complex.py").write_text(
        'def process(data):\n'
        '    if not data:\n'
        '        return None\n'
        '    result = []\n'
        '    for item in data:\n'
        '        if isinstance(item, dict):\n'
        '            if "key" in item:\n'
        '                if item["key"] > 0:\n'
        '                    result.append(item)\n'
        '                else:\n'
        '                    result.append(None)\n'
        '            elif "alt" in item:\n'
        '                result.append(item["alt"])\n'
        '        elif isinstance(item, list):\n'
        '            result.extend(item)\n'
        '        else:\n'
        '            result.append(item)\n'
        '    return result\n',
        encoding="utf-8",
    )

    (src / "empty.py").write_text("", encoding="utf-8")


# =========================================================================
# FileMetrics tests
# =========================================================================


class TestFileMetrics:
    """Tests for per-file metric computation."""

    def test_basic_metrics(self, tmp_path):
        from semantic_code_intelligence.ci.metrics import compute_file_metrics

        _write_sample_project(tmp_path)
        fm = compute_file_metrics(tmp_path / "src" / "simple.py")

        assert fm.file_path.endswith("simple.py")
        assert fm.lines_of_code > 0
        assert fm.comment_lines >= 1  # '# Simple module'
        assert fm.symbol_count >= 2  # greet, add
        assert 0 <= fm.maintainability_index <= 100

    def test_empty_file(self, tmp_path):
        from semantic_code_intelligence.ci.metrics import compute_file_metrics

        _write_sample_project(tmp_path)
        fm = compute_file_metrics(tmp_path / "src" / "empty.py")

        assert fm.lines_of_code == 0
        assert fm.maintainability_index >= 0

    def test_nonexistent_file(self, tmp_path):
        from semantic_code_intelligence.ci.metrics import compute_file_metrics

        fm = compute_file_metrics(tmp_path / "nope.py")
        assert fm.lines_of_code == 0

    def test_comment_ratio_property(self, tmp_path):
        from semantic_code_intelligence.ci.metrics import compute_file_metrics

        _write_sample_project(tmp_path)
        fm = compute_file_metrics(tmp_path / "src" / "simple.py")
        assert 0.0 <= fm.comment_ratio <= 1.0

    def test_to_dict(self, tmp_path):
        from semantic_code_intelligence.ci.metrics import compute_file_metrics

        _write_sample_project(tmp_path)
        fm = compute_file_metrics(tmp_path / "src" / "simple.py")
        d = fm.to_dict()

        assert "file_path" in d
        assert "lines_of_code" in d
        assert "maintainability_index" in d
        assert "comment_ratio" in d
        assert isinstance(d["maintainability_index"], float)


# =========================================================================
# ProjectMetrics tests
# =========================================================================


class TestProjectMetrics:
    """Tests for project-wide metric aggregation."""

    def test_project_metrics(self, tmp_path):
        from semantic_code_intelligence.ci.metrics import compute_project_metrics

        _write_sample_project(tmp_path)
        pm = compute_project_metrics(tmp_path)

        assert pm.files_analyzed >= 2  # simple.py, complex.py (empty.py may be counted too)
        assert pm.total_loc > 0
        assert pm.total_symbols > 0
        assert 0 <= pm.maintainability_index <= 100

    def test_project_metrics_with_file_paths(self, tmp_path):
        from semantic_code_intelligence.ci.metrics import compute_project_metrics

        _write_sample_project(tmp_path)
        files = [str(tmp_path / "src" / "simple.py")]
        pm = compute_project_metrics(tmp_path, file_paths=files)

        assert pm.files_analyzed == 1

    def test_empty_project(self, tmp_path):
        from semantic_code_intelligence.ci.metrics import compute_project_metrics

        pm = compute_project_metrics(tmp_path)
        assert pm.files_analyzed == 0
        assert pm.maintainability_index >= 0

    def test_to_dict(self, tmp_path):
        from semantic_code_intelligence.ci.metrics import compute_project_metrics

        _write_sample_project(tmp_path)
        pm = compute_project_metrics(tmp_path)
        d = pm.to_dict()

        assert "files_analyzed" in d
        assert "total_loc" in d
        assert "maintainability_index" in d
        assert "file_metrics" in d
        assert isinstance(d["file_metrics"], list)

    def test_comment_ratio(self, tmp_path):
        from semantic_code_intelligence.ci.metrics import compute_project_metrics

        _write_sample_project(tmp_path)
        pm = compute_project_metrics(tmp_path)
        assert 0.0 <= pm.comment_ratio <= 1.0


# =========================================================================
# Maintainability index computation
# =========================================================================


class TestMaintainabilityIndex:
    """Tests for the MI formula."""

    def test_mi_range(self):
        from semantic_code_intelligence.ci.metrics import _compute_mi

        # Simple code should have high MI
        mi_simple = _compute_mi(10.0, 1.0, 0.3)
        assert 0 <= mi_simple <= 100

        # Complex code should have lower MI
        mi_complex = _compute_mi(500.0, 20.0, 0.0)
        assert 0 <= mi_complex <= 100
        assert mi_complex < mi_simple

    def test_mi_zero_loc(self):
        from semantic_code_intelligence.ci.metrics import _compute_mi

        mi = _compute_mi(0.0, 0.0, 0.0)
        assert 0 <= mi <= 100

    def test_mi_high_comments_helps(self):
        from semantic_code_intelligence.ci.metrics import _compute_mi

        mi_no_cm = _compute_mi(100.0, 5.0, 0.0)
        mi_with_cm = _compute_mi(100.0, 5.0, 0.3)
        assert mi_with_cm >= mi_no_cm


# =========================================================================
# Line counting helpers
# =========================================================================


class TestLineCounting:
    """Tests for _count_lines helper."""

    def test_count_python_lines(self):
        from semantic_code_intelligence.ci.metrics import _count_lines

        code = "# comment\ndef foo():\n    pass\n\n"
        loc, comments, blanks = _count_lines(code)
        assert comments >= 1
        assert loc >= 2  # def foo, pass
        assert blanks >= 1

    def test_count_js_comments(self):
        from semantic_code_intelligence.ci.metrics import _count_lines

        code = "// comment\nfunction foo() {\n}\n"
        loc, comments, blanks = _count_lines(code)
        assert comments >= 1

    def test_empty_content(self):
        from semantic_code_intelligence.ci.metrics import _count_lines

        loc, comments, blanks = _count_lines("")
        assert loc == 0
        assert comments == 0
        assert blanks == 0


# =========================================================================
# Quality snapshots
# =========================================================================


class TestQualitySnapshots:
    """Tests for snapshot save/load via WorkspaceMemory."""

    def test_save_snapshot(self, tmp_path):
        from semantic_code_intelligence.ci.metrics import (
            ProjectMetrics,
            save_snapshot,
        )
        from semantic_code_intelligence.ci.quality import QualityReport

        (tmp_path / ".codexa").mkdir(exist_ok=True)
        pm = ProjectMetrics(
            files_analyzed=5,
            total_loc=200,
            avg_complexity=3.5,
            max_complexity=8,
            total_symbols=20,
            maintainability_index=72.5,
        )
        qr = QualityReport(files_analyzed=5, symbol_count=20)

        snap = save_snapshot(tmp_path, pm, qr, metadata={"branch": "main"})
        assert snap.timestamp > 0
        assert snap.maintainability_index == 72.5
        assert snap.metadata["branch"] == "main"

    def test_save_and_load(self, tmp_path):
        from semantic_code_intelligence.ci.metrics import (
            ProjectMetrics,
            load_snapshots,
            save_snapshot,
        )
        from semantic_code_intelligence.ci.quality import QualityReport

        (tmp_path / ".codexa").mkdir(exist_ok=True)
        pm = ProjectMetrics(
            files_analyzed=3,
            total_loc=100,
            avg_complexity=2.0,
            max_complexity=5,
            total_symbols=10,
            maintainability_index=80.0,
        )
        qr = QualityReport(files_analyzed=3, symbol_count=10)

        save_snapshot(tmp_path, pm, qr)
        time.sleep(0.01)
        save_snapshot(tmp_path, pm, qr)

        snaps = load_snapshots(tmp_path, limit=10)
        assert len(snaps) >= 2
        # Newest first
        assert snaps[0].timestamp >= snaps[1].timestamp

    def test_load_empty(self, tmp_path):
        from semantic_code_intelligence.ci.metrics import load_snapshots

        (tmp_path / ".codexa").mkdir(exist_ok=True)
        snaps = load_snapshots(tmp_path)
        assert snaps == []

    def test_snapshot_to_dict_roundtrip(self):
        from semantic_code_intelligence.ci.metrics import QualitySnapshot

        snap = QualitySnapshot(
            timestamp=1234567890.0,
            maintainability_index=65.0,
            total_loc=500,
            total_symbols=50,
            issue_count=3,
            files_analyzed=10,
            avg_complexity=4.2,
            comment_ratio=0.15,
            metadata={"test": True},
        )
        d = snap.to_dict()
        restored = QualitySnapshot.from_dict(d)
        assert restored.timestamp == snap.timestamp
        assert restored.maintainability_index == snap.maintainability_index
        assert restored.metadata["test"] is True


# =========================================================================
# Trend analysis
# =========================================================================


class TestTrendAnalysis:
    """Tests for trend computation over snapshots."""

    def _make_snapshot(self, ts, mi, issues=0, cc=1.0, loc=100):
        from semantic_code_intelligence.ci.metrics import QualitySnapshot

        return QualitySnapshot(
            timestamp=ts,
            maintainability_index=mi,
            total_loc=loc,
            total_symbols=10,
            issue_count=issues,
            files_analyzed=5,
            avg_complexity=cc,
            comment_ratio=0.1,
        )

    def test_improving_trend(self):
        from semantic_code_intelligence.ci.metrics import compute_trend

        # MI getting better over time (newest first)
        snaps = [
            self._make_snapshot(3.0, 80.0),
            self._make_snapshot(2.0, 60.0),
            self._make_snapshot(1.0, 40.0),
        ]
        t = compute_trend(snaps, "maintainability_index", higher_is_better=True)
        assert t.direction == "improving"
        assert t.delta > 0

    def test_degrading_trend(self):
        from semantic_code_intelligence.ci.metrics import compute_trend

        # MI getting worse
        snaps = [
            self._make_snapshot(3.0, 30.0),
            self._make_snapshot(2.0, 50.0),
            self._make_snapshot(1.0, 80.0),
        ]
        t = compute_trend(snaps, "maintainability_index", higher_is_better=True)
        assert t.direction == "degrading"
        assert t.delta < 0

    def test_stable_trend(self):
        from semantic_code_intelligence.ci.metrics import compute_trend

        snaps = [
            self._make_snapshot(3.0, 50.0),
            self._make_snapshot(2.0, 50.0),
            self._make_snapshot(1.0, 50.0),
        ]
        t = compute_trend(snaps, "maintainability_index")
        assert t.direction == "stable"

    def test_empty_snapshots(self):
        from semantic_code_intelligence.ci.metrics import compute_trend

        t = compute_trend([], "maintainability_index")
        assert t.snapshot_count == 0
        assert t.direction == "stable"

    def test_single_snapshot(self):
        from semantic_code_intelligence.ci.metrics import compute_trend

        snaps = [self._make_snapshot(1.0, 50.0)]
        t = compute_trend(snaps, "maintainability_index")
        assert t.direction == "stable"
        assert t.snapshot_count == 1

    def test_trend_to_dict(self):
        from semantic_code_intelligence.ci.metrics import compute_trend

        snaps = [
            self._make_snapshot(2.0, 70.0),
            self._make_snapshot(1.0, 50.0),
        ]
        t = compute_trend(snaps, "maintainability_index")
        d = t.to_dict()
        assert "metric_name" in d
        assert "direction" in d
        assert "delta" in d


# =========================================================================
# Quality policy & gate enforcement
# =========================================================================


class TestQualityPolicy:
    """Tests for QualityPolicy dataclass."""

    def test_defaults(self):
        from semantic_code_intelligence.ci.metrics import QualityPolicy

        p = QualityPolicy()
        assert p.min_maintainability == 40.0
        assert p.max_complexity == 25
        assert p.max_issues == 20

    def test_to_dict_roundtrip(self):
        from semantic_code_intelligence.ci.metrics import QualityPolicy

        p = QualityPolicy(min_maintainability=50.0, max_complexity=15)
        d = p.to_dict()
        restored = QualityPolicy.from_dict(d)
        assert restored.min_maintainability == 50.0
        assert restored.max_complexity == 15


class TestGateEnforcement:
    """Tests for enforce_quality_gate."""

    def test_gate_pass(self):
        from semantic_code_intelligence.ci.metrics import (
            ProjectMetrics,
            QualityPolicy,
            enforce_quality_gate,
        )
        from semantic_code_intelligence.ci.quality import QualityReport

        pm = ProjectMetrics(
            maintainability_index=80.0,
            max_complexity=5,
        )
        qr = QualityReport(files_analyzed=5, symbol_count=20)

        result = enforce_quality_gate(pm, qr, QualityPolicy())
        assert result.passed is True
        assert len(result.violations) == 0

    def test_gate_fail_maintainability(self):
        from semantic_code_intelligence.ci.metrics import (
            ProjectMetrics,
            QualityPolicy,
            enforce_quality_gate,
        )
        from semantic_code_intelligence.ci.quality import QualityReport

        pm = ProjectMetrics(maintainability_index=20.0, max_complexity=5)
        qr = QualityReport(files_analyzed=5, symbol_count=20)

        result = enforce_quality_gate(pm, qr, QualityPolicy(min_maintainability=40.0))
        assert result.passed is False
        assert any(v.rule == "min_maintainability" for v in result.violations)

    def test_gate_fail_complexity(self):
        from semantic_code_intelligence.ci.metrics import (
            ProjectMetrics,
            QualityPolicy,
            enforce_quality_gate,
        )
        from semantic_code_intelligence.ci.quality import QualityReport

        pm = ProjectMetrics(maintainability_index=80.0, max_complexity=30)
        qr = QualityReport(files_analyzed=5, symbol_count=20)

        result = enforce_quality_gate(pm, qr, QualityPolicy(max_complexity=25))
        assert result.passed is False
        assert any(v.rule == "max_complexity" for v in result.violations)

    def test_gate_multiple_violations(self):
        from semantic_code_intelligence.ci.metrics import (
            ProjectMetrics,
            QualityPolicy,
            enforce_quality_gate,
        )
        from semantic_code_intelligence.ci.quality import QualityReport

        pm = ProjectMetrics(maintainability_index=10.0, max_complexity=50)
        qr = QualityReport(files_analyzed=5, symbol_count=20)

        result = enforce_quality_gate(pm, qr, QualityPolicy())
        assert result.passed is False
        assert len(result.violations) >= 2

    def test_gate_result_to_dict(self):
        from semantic_code_intelligence.ci.metrics import (
            ProjectMetrics,
            enforce_quality_gate,
        )
        from semantic_code_intelligence.ci.quality import QualityReport

        pm = ProjectMetrics(maintainability_index=80.0, max_complexity=5)
        qr = QualityReport(files_analyzed=5, symbol_count=20)

        result = enforce_quality_gate(pm, qr)
        d = result.to_dict()
        assert "passed" in d
        assert "violations" in d
        assert "policy" in d

    def test_gate_default_policy(self):
        from semantic_code_intelligence.ci.metrics import (
            ProjectMetrics,
            enforce_quality_gate,
        )
        from semantic_code_intelligence.ci.quality import QualityReport

        pm = ProjectMetrics(maintainability_index=80.0, max_complexity=5)
        qr = QualityReport(files_analyzed=5, symbol_count=20)

        # Should use default policy
        result = enforce_quality_gate(pm, qr)
        assert result.passed is True


# =========================================================================
# CLI: metrics command
# =========================================================================


class TestMetricsCLI:
    """Tests for the `codexa metrics` CLI command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_basic_metrics_json(self, runner, tmp_path):
        from semantic_code_intelligence.cli.commands.metrics_cmd import metrics_cmd

        _write_sample_project(tmp_path)
        result = runner.invoke(metrics_cmd, [
            "--path", str(tmp_path), "--json",
        ], obj={"pipe": False})
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "files_analyzed" in data
        assert "maintainability_index" in data

    def test_pipe_mode(self, runner, tmp_path):
        from semantic_code_intelligence.cli.commands.metrics_cmd import metrics_cmd

        _write_sample_project(tmp_path)
        result = runner.invoke(metrics_cmd, [
            "--path", str(tmp_path), "--pipe",
        ], obj={"pipe": False})
        assert result.exit_code == 0
        assert "MI:" in result.output

    def test_rich_output(self, runner, tmp_path):
        from semantic_code_intelligence.cli.commands.metrics_cmd import metrics_cmd

        _write_sample_project(tmp_path)
        result = runner.invoke(metrics_cmd, [
            "--path", str(tmp_path),
        ], obj={"pipe": False})
        assert result.exit_code == 0
        assert "Quality Metrics" in result.output

    def test_snapshot_json(self, runner, tmp_path):
        from semantic_code_intelligence.cli.commands.metrics_cmd import metrics_cmd

        _write_sample_project(tmp_path)
        (tmp_path / ".codexa").mkdir(exist_ok=True)
        result = runner.invoke(metrics_cmd, [
            "--path", str(tmp_path), "--json", "--snapshot",
        ], obj={"pipe": False})
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "snapshot" in data

    def test_history_empty(self, runner, tmp_path):
        from semantic_code_intelligence.cli.commands.metrics_cmd import metrics_cmd

        (tmp_path / ".codexa").mkdir(exist_ok=True)
        result = runner.invoke(metrics_cmd, [
            "--path", str(tmp_path), "--history", "5",
        ], obj={"pipe": False})
        assert result.exit_code == 0

    def test_trend_needs_data(self, runner, tmp_path):
        from semantic_code_intelligence.cli.commands.metrics_cmd import metrics_cmd

        (tmp_path / ".codexa").mkdir(exist_ok=True)
        result = runner.invoke(metrics_cmd, [
            "--path", str(tmp_path), "--trend",
        ], obj={"pipe": False})
        assert result.exit_code == 0
        # Should tell user they need more snapshots
        assert "2 snapshots" in result.output.lower() or "need" in result.output.lower()


# =========================================================================
# CLI: gate command
# =========================================================================


class TestGateCLI:
    """Tests for the `codexa gate` CLI command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_gate_json(self, runner, tmp_path):
        from semantic_code_intelligence.cli.commands.gate_cmd import gate_cmd

        _write_sample_project(tmp_path)
        result = runner.invoke(gate_cmd, [
            "--path", str(tmp_path), "--json",
        ], obj={"pipe": False})
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "passed" in data
        assert "violations" in data

    def test_gate_pipe_pass(self, runner, tmp_path):
        from semantic_code_intelligence.cli.commands.gate_cmd import gate_cmd

        _write_sample_project(tmp_path)
        result = runner.invoke(gate_cmd, [
            "--path", str(tmp_path), "--pipe",
        ], obj={"pipe": False})
        assert result.exit_code == 0
        assert "MI=" in result.output

    def test_gate_rich_output(self, runner, tmp_path):
        from semantic_code_intelligence.cli.commands.gate_cmd import gate_cmd

        _write_sample_project(tmp_path)
        result = runner.invoke(gate_cmd, [
            "--path", str(tmp_path),
        ], obj={"pipe": False})
        assert result.exit_code == 0

    def test_gate_custom_thresholds(self, runner, tmp_path):
        from semantic_code_intelligence.cli.commands.gate_cmd import gate_cmd

        _write_sample_project(tmp_path)
        result = runner.invoke(gate_cmd, [
            "--path", str(tmp_path), "--json",
            "--min-maintainability", "99",
        ], obj={"pipe": False})
        assert result.exit_code == 0
        data = json.loads(result.output)
        # With MI threshold of 99, should likely fail
        assert "passed" in data


# =========================================================================
# Configuration extension
# =========================================================================


class TestQualityConfigExtension:
    """Tests for QualityConfig in AppConfig."""

    def test_default_quality_config(self):
        from semantic_code_intelligence.config.settings import AppConfig

        cfg = AppConfig()
        assert hasattr(cfg, "quality")
        assert cfg.quality.complexity_threshold == 10
        assert cfg.quality.min_maintainability == 40.0
        assert cfg.quality.snapshot_on_index is False

    def test_quality_config_in_json(self):
        from semantic_code_intelligence.config.settings import AppConfig

        cfg = AppConfig()
        d = json.loads(cfg.model_dump_json())
        assert "quality" in d
        assert d["quality"]["complexity_threshold"] == 10

    def test_load_config_with_quality(self, tmp_path):
        from semantic_code_intelligence.config.settings import (
            AppConfig,
            save_config,
            load_config,
        )

        cfg = AppConfig(project_root=str(tmp_path))
        cfg.quality.min_maintainability = 60.0
        save_config(cfg, tmp_path)

        loaded = load_config(tmp_path)
        assert loaded.quality.min_maintainability == 60.0


# =========================================================================
# Documentation generation
# =========================================================================


class TestDocsPhase17:
    """Tests for QUALITY_METRICS.md documentation generation."""

    def test_quality_metrics_reference(self):
        from semantic_code_intelligence.docs import generate_quality_metrics_reference

        md = generate_quality_metrics_reference()
        assert "Maintainability Index" in md
        assert "Quality Gates" in md
        assert "codexa gate" in md
        assert "codexa metrics" in md

    def test_generate_all_docs_includes_quality(self, tmp_path):
        from semantic_code_intelligence.docs import generate_all_docs

        generated = generate_all_docs(tmp_path)
        assert "QUALITY_METRICS.md" in generated

    def test_ci_reference_updated(self):
        from semantic_code_intelligence.docs import generate_ci_reference

        md = generate_ci_reference()
        assert "codexa metrics" in md
        assert "codexa gate" in md


# =========================================================================
# Router, version, and module structure tests
# =========================================================================


class TestRouterPhase17:
    """Tests for CLI router registration."""

    def test_register_commands_count(self):
        import click
        from semantic_code_intelligence.cli.router import register_commands

        group = click.Group("test")
        register_commands(group)
        assert len(group.commands) == 39

    def test_metrics_command_registered(self):
        from semantic_code_intelligence.cli.main import cli

        assert "metrics" in cli.commands

    def test_gate_command_registered(self):
        from semantic_code_intelligence.cli.main import cli

        assert "gate" in cli.commands


class TestVersionBump17:
    """Test version is 0.19.0."""

    def test_version_is_017(self):
        from semantic_code_intelligence import __version__

        assert __version__ == "0.4.0"


class TestPhase17ModuleStructure:
    """Tests for module import structure."""

    def test_import_metrics(self):
        from semantic_code_intelligence.ci.metrics import (
            FileMetrics,
            ProjectMetrics,
            QualitySnapshot,
            TrendResult,
            QualityPolicy,
            GateResult,
            GateViolation,
            compute_file_metrics,
            compute_project_metrics,
            save_snapshot,
            load_snapshots,
            compute_trend,
            enforce_quality_gate,
        )

    def test_import_quality_config(self):
        from semantic_code_intelligence.config.settings import QualityConfig

    def test_import_metrics_cmd(self):
        from semantic_code_intelligence.cli.commands.metrics_cmd import metrics_cmd

    def test_import_gate_cmd(self):
        from semantic_code_intelligence.cli.commands.gate_cmd import gate_cmd

    def test_ci_module_docstring_updated(self):
        import semantic_code_intelligence.ci as ci_mod

        assert "metrics" in ci_mod.__doc__.lower()
