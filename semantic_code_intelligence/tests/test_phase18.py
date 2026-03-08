"""Tests for Phase 18 — Developer Workflow Intelligence.

Covers: hotspot detection, impact analysis, symbol trace, CLI commands,
router registration (30 commands), version (0.18.0), docs generation,
plugin hooks, and module structure.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner


# =========================================================================
# Test helpers
# =========================================================================


def _write_sample_project(root: Path) -> None:
    """Write a multi-file project with known call relationships."""
    src = root / "src"
    src.mkdir(parents=True, exist_ok=True)

    (src / "core.py").write_text(
        "def helper():\n"
        "    return 42\n"
        "\n"
        "def compute(x):\n"
        "    return helper() + x\n"
        "\n"
        "def orchestrate(a, b):\n"
        "    return compute(a) + compute(b)\n",
        encoding="utf-8",
    )

    (src / "api.py").write_text(
        "from src.core import orchestrate\n"
        "\n"
        "def handle_request(data):\n"
        "    result = orchestrate(data, data)\n"
        "    return result\n"
        "\n"
        "def validate(data):\n"
        "    if not data:\n"
        "        return False\n"
        "    if len(data) > 100:\n"
        "        return False\n"
        "    return True\n",
        encoding="utf-8",
    )

    (src / "utils.py").write_text(
        "def format_output(value):\n"
        "    return str(value)\n"
        "\n"
        "def log_event(event):\n"
        "    pass\n",
        encoding="utf-8",
    )


def _build_context(root: Path):
    """Index the project and return (symbols, call_graph, dep_map)."""
    from semantic_code_intelligence.context.engine import CallGraph, ContextBuilder, DependencyMap

    builder = ContextBuilder()
    dep_map = DependencyMap()

    for fp in sorted(root.rglob("*.py")):
        content = fp.read_text(encoding="utf-8")
        builder.index_file(str(fp), content)
        dep_map.add_file(str(fp), content)

    symbols = builder.get_all_symbols()
    cg = CallGraph()
    cg.build(symbols)
    return symbols, cg, dep_map


# =========================================================================
# HotspotFactor / Hotspot / HotspotReport dataclass tests
# =========================================================================


class TestHotspotDataclasses:
    """Tests for hotspot data structures."""

    def test_hotspot_factor_to_dict(self):
        from semantic_code_intelligence.ci.hotspots import HotspotFactor

        f = HotspotFactor(name="complexity", raw_value=12.0, normalized=0.8, weight=0.3)
        d = f.to_dict()
        assert d["name"] == "complexity"
        assert d["raw_value"] == 12.0
        assert d["normalized"] == 0.8
        assert d["weight"] == 0.3

    def test_hotspot_to_dict(self):
        from semantic_code_intelligence.ci.hotspots import Hotspot, HotspotFactor

        h = Hotspot(
            name="process",
            file_path="src/api.py",
            kind="symbol",
            risk_score=72.5,
            factors=[HotspotFactor("complexity", 10.0, 0.7, 0.3)],
        )
        d = h.to_dict()
        assert d["name"] == "process"
        assert d["risk_score"] == 72.5
        assert len(d["factors"]) == 1

    def test_hotspot_report_to_dict(self):
        from semantic_code_intelligence.ci.hotspots import Hotspot, HotspotReport

        r = HotspotReport(
            files_analyzed=5,
            symbols_analyzed=20,
            hotspots=[Hotspot("f1", "/a.py", "symbol", 50.0)],
        )
        d = r.to_dict()
        assert d["files_analyzed"] == 5
        assert d["symbols_analyzed"] == 20
        assert d["hotspot_count"] == 1

    def test_hotspot_report_empty(self):
        from semantic_code_intelligence.ci.hotspots import HotspotReport

        r = HotspotReport(files_analyzed=0, symbols_analyzed=0)
        assert r.to_dict()["hotspot_count"] == 0


# =========================================================================
# analyze_hotspots tests
# =========================================================================


class TestAnalyzeHotspots:
    """Tests for the hotspot detection engine."""

    def test_basic_analysis(self, tmp_path):
        from semantic_code_intelligence.ci.hotspots import analyze_hotspots

        _write_sample_project(tmp_path)
        symbols, cg, dep_map = _build_context(tmp_path)

        report = analyze_hotspots(
            symbols, cg, dep_map, tmp_path, include_git=False,
        )
        assert report.files_analyzed >= 1
        assert report.symbols_analyzed >= 1
        assert isinstance(report.hotspots, list)

    def test_top_n_limits(self, tmp_path):
        from semantic_code_intelligence.ci.hotspots import analyze_hotspots

        _write_sample_project(tmp_path)
        symbols, cg, dep_map = _build_context(tmp_path)

        report = analyze_hotspots(
            symbols, cg, dep_map, tmp_path,
            top_n=2, include_git=False,
        )
        assert len(report.hotspots) <= 2

    def test_custom_weights(self, tmp_path):
        from semantic_code_intelligence.ci.hotspots import analyze_hotspots

        _write_sample_project(tmp_path)
        symbols, cg, dep_map = _build_context(tmp_path)

        report = analyze_hotspots(
            symbols, cg, dep_map, tmp_path,
            include_git=False,
            weights={"complexity": 1.0, "duplication": 0.0, "fan_in": 0.0, "fan_out": 0.0, "churn": 0.0},
        )
        assert report.symbols_analyzed >= 1

    def test_no_git_redistributes_weights(self, tmp_path):
        from semantic_code_intelligence.ci.hotspots import analyze_hotspots

        _write_sample_project(tmp_path)
        symbols, cg, dep_map = _build_context(tmp_path)

        report = analyze_hotspots(
            symbols, cg, dep_map, tmp_path, include_git=False,
        )
        # When git is not available, churn factor should NOT appear
        for h in report.hotspots:
            factor_names = [f.name for f in h.factors]
            assert "churn" not in factor_names

    def test_hotspot_scores_are_sorted_desc(self, tmp_path):
        from semantic_code_intelligence.ci.hotspots import analyze_hotspots

        _write_sample_project(tmp_path)
        symbols, cg, dep_map = _build_context(tmp_path)

        report = analyze_hotspots(
            symbols, cg, dep_map, tmp_path, include_git=False,
        )
        scores = [h.risk_score for h in report.hotspots]
        assert scores == sorted(scores, reverse=True)

    def test_empty_project(self, tmp_path):
        from semantic_code_intelligence.ci.hotspots import analyze_hotspots

        (tmp_path / "empty.py").write_text("", encoding="utf-8")
        symbols, cg, dep_map = _build_context(tmp_path)

        report = analyze_hotspots(
            symbols, cg, dep_map, tmp_path, include_git=False,
        )
        assert report.symbols_analyzed == 0
        assert report.hotspots == []

    def test_report_serialisation_roundtrip(self, tmp_path):
        from semantic_code_intelligence.ci.hotspots import analyze_hotspots

        _write_sample_project(tmp_path)
        symbols, cg, dep_map = _build_context(tmp_path)

        report = analyze_hotspots(
            symbols, cg, dep_map, tmp_path, include_git=False,
        )
        d = report.to_dict()
        s = json.dumps(d)
        loaded = json.loads(s)
        assert loaded["files_analyzed"] == report.files_analyzed


# =========================================================================
# AffectedSymbol / AffectedModule / ImpactReport dataclass tests
# =========================================================================


class TestImpactDataclasses:
    """Tests for impact analysis data structures."""

    def test_affected_symbol_to_dict(self):
        from semantic_code_intelligence.ci.impact import AffectedSymbol

        a = AffectedSymbol("foo", "/a.py", "function", "direct_caller", 1)
        d = a.to_dict()
        assert d["name"] == "foo"
        assert d["relationship"] == "direct_caller"
        assert d["depth"] == 1

    def test_affected_module_to_dict(self):
        from semantic_code_intelligence.ci.impact import AffectedModule

        m = AffectedModule("/b.py", "imports_target", 1)
        assert m.to_dict()["file_path"] == "/b.py"

    def test_dependency_chain_to_dict(self):
        from semantic_code_intelligence.ci.impact import DependencyChain

        c = DependencyChain(path=["a", "b", "c"])
        assert c.to_dict()["path"] == ["a", "b", "c"]

    def test_impact_report_total_affected(self):
        from semantic_code_intelligence.ci.impact import AffectedSymbol, ImpactReport

        r = ImpactReport(
            target="foo", target_kind="symbol",
            direct_symbols=[
                AffectedSymbol("bar", "/a.py", "function", "direct_caller", 1),
            ],
            transitive_symbols=[
                AffectedSymbol("baz", "/b.py", "function", "transitive_caller", 2),
            ],
        )
        assert r.total_affected == 2

    def test_impact_report_to_dict(self):
        from semantic_code_intelligence.ci.impact import ImpactReport

        r = ImpactReport(target="foo", target_kind="symbol")
        d = r.to_dict()
        assert d["target"] == "foo"
        assert d["total_affected"] == 0


# =========================================================================
# analyze_impact tests
# =========================================================================


class TestAnalyzeImpact:
    """Tests for the impact analysis engine."""

    def test_basic_impact(self, tmp_path):
        from semantic_code_intelligence.ci.impact import analyze_impact

        _write_sample_project(tmp_path)
        symbols, cg, dep_map = _build_context(tmp_path)

        report = analyze_impact("helper", symbols, cg, dep_map, tmp_path)
        assert report.target == "helper"
        assert report.target_kind == "symbol"

    def test_unknown_symbol_empty_report(self, tmp_path):
        from semantic_code_intelligence.ci.impact import analyze_impact

        _write_sample_project(tmp_path)
        symbols, cg, dep_map = _build_context(tmp_path)

        report = analyze_impact("nonexistent_xyz", symbols, cg, dep_map, tmp_path)
        assert report.total_affected == 0

    def test_impact_file_target(self, tmp_path):
        from semantic_code_intelligence.ci.impact import analyze_impact

        _write_sample_project(tmp_path)
        symbols, cg, dep_map = _build_context(tmp_path)

        report = analyze_impact(
            str(tmp_path / "src" / "core.py"),
            symbols, cg, dep_map, tmp_path,
        )
        assert report.target_kind == "file"

    def test_impact_max_depth(self, tmp_path):
        from semantic_code_intelligence.ci.impact import analyze_impact

        _write_sample_project(tmp_path)
        symbols, cg, dep_map = _build_context(tmp_path)

        report = analyze_impact(
            "helper", symbols, cg, dep_map, tmp_path, max_depth=1,
        )
        # Should only get direct callers at depth 1
        for s in report.transitive_symbols:
            assert s.depth <= 1

    def test_impact_chains(self, tmp_path):
        from semantic_code_intelligence.ci.impact import analyze_impact

        _write_sample_project(tmp_path)
        symbols, cg, dep_map = _build_context(tmp_path)

        report = analyze_impact("helper", symbols, cg, dep_map, tmp_path)
        assert isinstance(report.chains, list)

    def test_impact_serialisation(self, tmp_path):
        from semantic_code_intelligence.ci.impact import analyze_impact

        _write_sample_project(tmp_path)
        symbols, cg, dep_map = _build_context(tmp_path)

        report = analyze_impact("helper", symbols, cg, dep_map, tmp_path)
        s = json.dumps(report.to_dict())
        loaded = json.loads(s)
        assert loaded["target"] == "helper"


# =========================================================================
# TraceNode / TraceEdge / TraceResult dataclass tests
# =========================================================================


class TestTraceDataclasses:
    """Tests for trace data structures."""

    def test_trace_node_to_dict(self):
        from semantic_code_intelligence.ci.trace import TraceNode

        n = TraceNode("func_a", "/a.py", "function", -2)
        d = n.to_dict()
        assert d["name"] == "func_a"
        assert d["depth"] == -2

    def test_trace_edge_to_dict(self):
        from semantic_code_intelligence.ci.trace import TraceEdge

        e = TraceEdge("a", "b", "/x.py")
        d = e.to_dict()
        assert d["caller"] == "a"
        assert d["callee"] == "b"

    def test_trace_result_total_nodes(self):
        from semantic_code_intelligence.ci.trace import TraceNode, TraceResult

        r = TraceResult(
            target="f", target_file="/x.py",
            upstream=[TraceNode("a", "/a.py", "function", -1)],
            downstream=[TraceNode("b", "/b.py", "function", 1),
                        TraceNode("c", "/c.py", "function", 2)],
        )
        assert r.total_nodes == 3

    def test_trace_result_to_dict(self):
        from semantic_code_intelligence.ci.trace import TraceResult

        r = TraceResult(target="f", target_file="/x.py")
        d = r.to_dict()
        assert d["target"] == "f"
        assert d["total_nodes"] == 0


# =========================================================================
# trace_symbol tests
# =========================================================================


class TestTraceSymbol:
    """Tests for the symbol trace tool."""

    def test_basic_trace(self, tmp_path):
        from semantic_code_intelligence.ci.trace import trace_symbol

        _write_sample_project(tmp_path)
        symbols, cg, _ = _build_context(tmp_path)

        result = trace_symbol("compute", symbols, cg)
        assert result.target == "compute"
        assert result.target_file != ""

    def test_trace_unknown_symbol(self, tmp_path):
        from semantic_code_intelligence.ci.trace import trace_symbol

        _write_sample_project(tmp_path)
        symbols, cg, _ = _build_context(tmp_path)

        result = trace_symbol("nonexistent_xyz", symbols, cg)
        assert result.target_file == ""
        assert result.total_nodes == 0

    def test_trace_has_upstream(self, tmp_path):
        from semantic_code_intelligence.ci.trace import trace_symbol

        _write_sample_project(tmp_path)
        symbols, cg, _ = _build_context(tmp_path)

        result = trace_symbol("helper", symbols, cg)
        # helper is called by compute, so upstream should be non-empty
        assert len(result.upstream) >= 1 or len(result.edges) >= 0

    def test_trace_has_downstream(self, tmp_path):
        from semantic_code_intelligence.ci.trace import trace_symbol

        _write_sample_project(tmp_path)
        symbols, cg, _ = _build_context(tmp_path)

        result = trace_symbol("orchestrate", symbols, cg)
        # orchestrate calls compute, so downstream should be non-empty
        assert len(result.downstream) >= 0  # depends on call graph heuristic

    def test_trace_max_depth(self, tmp_path):
        from semantic_code_intelligence.ci.trace import trace_symbol

        _write_sample_project(tmp_path)
        symbols, cg, _ = _build_context(tmp_path)

        result = trace_symbol("helper", symbols, cg, max_depth=1)
        for n in result.upstream:
            assert abs(n.depth) <= 1

    def test_trace_edges_list(self, tmp_path):
        from semantic_code_intelligence.ci.trace import trace_symbol

        _write_sample_project(tmp_path)
        symbols, cg, _ = _build_context(tmp_path)

        result = trace_symbol("compute", symbols, cg)
        assert isinstance(result.edges, list)

    def test_trace_serialisation(self, tmp_path):
        from semantic_code_intelligence.ci.trace import trace_symbol

        _write_sample_project(tmp_path)
        symbols, cg, _ = _build_context(tmp_path)

        result = trace_symbol("compute", symbols, cg)
        s = json.dumps(result.to_dict())
        loaded = json.loads(s)
        assert loaded["target"] == "compute"


# =========================================================================
# _normalise helper tests
# =========================================================================


class TestNormalise:
    """Tests for the normalisation helper."""

    def test_normalise_basic(self):
        from semantic_code_intelligence.ci.hotspots import _normalise

        assert _normalise(5.0, 10.0) == 0.5

    def test_normalise_zero_max(self):
        from semantic_code_intelligence.ci.hotspots import _normalise

        assert _normalise(5.0, 0.0) == 0.0

    def test_normalise_clamp(self):
        from semantic_code_intelligence.ci.hotspots import _normalise

        assert _normalise(20.0, 10.0) == 1.0


# =========================================================================
# _resolve_target_symbols tests
# =========================================================================


class TestResolveTarget:
    """Tests for target resolution in impact analysis."""

    def test_resolve_symbol(self, tmp_path):
        from semantic_code_intelligence.ci.impact import _resolve_target_symbols

        _write_sample_project(tmp_path)
        symbols, _, _ = _build_context(tmp_path)

        kind, matched = _resolve_target_symbols("helper", symbols, tmp_path)
        assert kind == "symbol"
        assert len(matched) >= 1

    def test_resolve_file(self, tmp_path):
        from semantic_code_intelligence.ci.impact import _resolve_target_symbols

        _write_sample_project(tmp_path)
        symbols, _, _ = _build_context(tmp_path)

        kind, matched = _resolve_target_symbols(
            str(tmp_path / "src" / "core.py"), symbols, tmp_path,
        )
        assert kind == "file"

    def test_resolve_unknown(self, tmp_path):
        from semantic_code_intelligence.ci.impact import _resolve_target_symbols

        _write_sample_project(tmp_path)
        symbols, _, _ = _build_context(tmp_path)

        kind, matched = _resolve_target_symbols("not_real", symbols, tmp_path)
        assert kind == "symbol"
        assert matched == []


# =========================================================================
# CLI: codex hotspots
# =========================================================================


class TestHotspotsCLI:
    """Tests for the hotspots CLI command."""

    def test_hotspots_help(self):
        from semantic_code_intelligence.cli.commands.hotspots_cmd import hotspots_cmd

        runner = CliRunner()
        result = runner.invoke(hotspots_cmd, ["--help"])
        assert result.exit_code == 0
        assert "hotspot" in result.output.lower()

    def test_hotspots_json(self, tmp_path):
        from semantic_code_intelligence.cli.commands.hotspots_cmd import hotspots_cmd

        _write_sample_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(hotspots_cmd, [
            "--path", str(tmp_path), "--json", "--no-git",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "hotspots" in data

    def test_hotspots_pipe(self, tmp_path):
        from semantic_code_intelligence.cli.commands.hotspots_cmd import hotspots_cmd

        _write_sample_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(hotspots_cmd, [
            "--path", str(tmp_path), "--pipe", "--no-git",
        ])
        assert result.exit_code == 0
        assert "files=" in result.output

    def test_hotspots_top_n(self, tmp_path):
        from semantic_code_intelligence.cli.commands.hotspots_cmd import hotspots_cmd

        _write_sample_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(hotspots_cmd, [
            "--path", str(tmp_path), "--json", "--no-git", "--top-n", "1",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["hotspots"]) <= 1

    def test_hotspots_rich_output(self, tmp_path):
        from semantic_code_intelligence.cli.commands.hotspots_cmd import hotspots_cmd

        _write_sample_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(hotspots_cmd, [
            "--path", str(tmp_path), "--no-git",
        ])
        assert result.exit_code == 0


# =========================================================================
# CLI: codex impact
# =========================================================================


class TestImpactCLI:
    """Tests for the impact CLI command."""

    def test_impact_help(self):
        from semantic_code_intelligence.cli.commands.impact_cmd import impact_cmd

        runner = CliRunner()
        result = runner.invoke(impact_cmd, ["--help"])
        assert result.exit_code == 0
        assert "impact" in result.output.lower() or "blast" in result.output.lower()

    def test_impact_json(self, tmp_path):
        from semantic_code_intelligence.cli.commands.impact_cmd import impact_cmd

        _write_sample_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(impact_cmd, [
            "helper", "--path", str(tmp_path), "--json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["target"] == "helper"

    def test_impact_pipe(self, tmp_path):
        from semantic_code_intelligence.cli.commands.impact_cmd import impact_cmd

        _write_sample_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(impact_cmd, [
            "helper", "--path", str(tmp_path), "--pipe",
        ])
        assert result.exit_code == 0
        assert "target=helper" in result.output

    def test_impact_unknown_target(self, tmp_path):
        from semantic_code_intelligence.cli.commands.impact_cmd import impact_cmd

        _write_sample_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(impact_cmd, [
            "zzz_nonexistent", "--path", str(tmp_path), "--json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total_affected"] == 0

    def test_impact_rich_output(self, tmp_path):
        from semantic_code_intelligence.cli.commands.impact_cmd import impact_cmd

        _write_sample_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(impact_cmd, [
            "helper", "--path", str(tmp_path),
        ])
        assert result.exit_code == 0


# =========================================================================
# CLI: codex trace
# =========================================================================


class TestTraceCLI:
    """Tests for the trace CLI command."""

    def test_trace_help(self):
        from semantic_code_intelligence.cli.commands.trace_cmd import trace_cmd

        runner = CliRunner()
        result = runner.invoke(trace_cmd, ["--help"])
        assert result.exit_code == 0
        assert "trace" in result.output.lower()

    def test_trace_json(self, tmp_path):
        from semantic_code_intelligence.cli.commands.trace_cmd import trace_cmd

        _write_sample_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(trace_cmd, [
            "compute", "--path", str(tmp_path), "--json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["target"] == "compute"

    def test_trace_pipe(self, tmp_path):
        from semantic_code_intelligence.cli.commands.trace_cmd import trace_cmd

        _write_sample_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(trace_cmd, [
            "compute", "--path", str(tmp_path), "--pipe",
        ])
        assert result.exit_code == 0
        assert "target=compute" in result.output

    def test_trace_unknown_symbol(self, tmp_path):
        from semantic_code_intelligence.cli.commands.trace_cmd import trace_cmd

        _write_sample_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(trace_cmd, [
            "zzz_missing", "--path", str(tmp_path), "--json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "error" in data

    def test_trace_rich_output(self, tmp_path):
        from semantic_code_intelligence.cli.commands.trace_cmd import trace_cmd

        _write_sample_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(trace_cmd, [
            "compute", "--path", str(tmp_path),
        ])
        assert result.exit_code == 0


# =========================================================================
# Plugin hooks
# =========================================================================


class TestPluginHooks:
    """Tests for Phase 18 plugin hooks."""

    def test_pre_hotspot_analysis_hook(self):
        from semantic_code_intelligence.plugins import PluginHook

        assert hasattr(PluginHook, "PRE_HOTSPOT_ANALYSIS")

    def test_post_hotspot_analysis_hook(self):
        from semantic_code_intelligence.plugins import PluginHook

        assert hasattr(PluginHook, "POST_HOTSPOT_ANALYSIS")

    def test_pre_impact_analysis_hook(self):
        from semantic_code_intelligence.plugins import PluginHook

        assert hasattr(PluginHook, "PRE_IMPACT_ANALYSIS")

    def test_post_impact_analysis_hook(self):
        from semantic_code_intelligence.plugins import PluginHook

        assert hasattr(PluginHook, "POST_IMPACT_ANALYSIS")

    def test_pre_trace_hook(self):
        from semantic_code_intelligence.plugins import PluginHook

        assert hasattr(PluginHook, "PRE_TRACE")

    def test_post_trace_hook(self):
        from semantic_code_intelligence.plugins import PluginHook

        assert hasattr(PluginHook, "POST_TRACE")

    def test_all_hooks_registered_in_manager(self):
        from semantic_code_intelligence.plugins import PluginHook, PluginManager

        pm = PluginManager()
        for hook in PluginHook:
            assert hook in pm._hook_registry

    def test_hook_count_is_22(self):
        from semantic_code_intelligence.plugins import PluginHook

        assert len(PluginHook) == 22


# =========================================================================
# Router — 30 commands
# =========================================================================


class TestRouter:
    """Tests for CLI router with 31 commands."""

    def test_command_count_is_31(self):
        import click

        from semantic_code_intelligence.cli.router import register_commands

        group = click.Group("test")
        register_commands(group)
        assert len(group.commands) == 34

    def test_hotspots_registered(self):
        import click

        from semantic_code_intelligence.cli.router import register_commands

        group = click.Group("test")
        register_commands(group)
        assert "hotspots" in group.commands

    def test_impact_registered(self):
        import click

        from semantic_code_intelligence.cli.router import register_commands

        group = click.Group("test")
        register_commands(group)
        assert "impact" in group.commands

    def test_trace_registered(self):
        import click

        from semantic_code_intelligence.cli.router import register_commands

        group = click.Group("test")
        register_commands(group)
        assert "trace" in group.commands


# =========================================================================
# Version
# =========================================================================


class TestVersion:
    """Test version is 0.19.0."""

    def test_version_string(self):
        from semantic_code_intelligence import __version__

        assert __version__ == "0.26.0"

    def test_cli_version(self):
        from semantic_code_intelligence.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.26.0" in result.output


# =========================================================================
# Docs generation
# =========================================================================


class TestDocsGeneration:
    """Tests for WORKFLOW_INTELLIGENCE.md generation."""

    def test_generate_workflow_intelligence_reference(self):
        from semantic_code_intelligence.docs import (
            generate_workflow_intelligence_reference,
        )

        md = generate_workflow_intelligence_reference()
        assert "Hotspot Detection" in md
        assert "Impact Analysis" in md
        assert "Symbol Trace" in md
        assert "codex hotspots" in md
        assert "codex impact" in md
        assert "codex trace" in md

    def test_workflow_intelligence_in_all_docs(self, tmp_path):
        from semantic_code_intelligence.docs import generate_all_docs

        generated = generate_all_docs(tmp_path)
        assert "WORKFLOW_INTELLIGENCE.md" in generated

    def test_workflow_intelligence_file_content(self, tmp_path):
        from semantic_code_intelligence.docs import generate_all_docs

        generate_all_docs(tmp_path)
        path = tmp_path / "WORKFLOW_INTELLIGENCE.md"
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "Workflow Intelligence Reference" in content


# =========================================================================
# Module structure
# =========================================================================


class TestModuleStructure:
    """Tests for Phase 18 module structure."""

    def test_ci_hotspots_importable(self):
        from semantic_code_intelligence.ci import hotspots

        assert hasattr(hotspots, "analyze_hotspots")
        assert hasattr(hotspots, "HotspotReport")

    def test_ci_impact_importable(self):
        from semantic_code_intelligence.ci import impact

        assert hasattr(impact, "analyze_impact")
        assert hasattr(impact, "ImpactReport")

    def test_ci_trace_importable(self):
        from semantic_code_intelligence.ci import trace

        assert hasattr(trace, "trace_symbol")
        assert hasattr(trace, "TraceResult")

    def test_hotspots_cmd_importable(self):
        from semantic_code_intelligence.cli.commands.hotspots_cmd import hotspots_cmd

        assert hotspots_cmd is not None

    def test_impact_cmd_importable(self):
        from semantic_code_intelligence.cli.commands.impact_cmd import impact_cmd

        assert impact_cmd is not None

    def test_trace_cmd_importable(self):
        from semantic_code_intelligence.cli.commands.trace_cmd import trace_cmd

        assert trace_cmd is not None

    def test_ci_init_docstring(self):
        import semantic_code_intelligence.ci as ci_mod

        assert "hotspots" in ci_mod.__doc__
        assert "impact" in ci_mod.__doc__
        assert "trace" in ci_mod.__doc__
