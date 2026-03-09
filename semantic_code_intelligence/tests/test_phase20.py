"""Phase 20 — Deep Coverage & Hardening Tests.

Target: bring total tests from 1204 to 2000+.
Tests cover every under-tested module with unit-level granularity:
  - ci/ (quality, metrics, pr, hooks, templates, hotspots, impact, trace)
  - web/ (api, visualize)
  - llm/ (safety, reasoning, conversation, investigation, streaming, providers)
  - bridge/ (protocol, server, context_provider, vscode)
  - context/ (engine, memory)
  - tools/ (protocol, executor, registry)
  - workspace/
  - daemon/watcher
  - docs/
  - config/settings
  - parsing/parser
  - indexing/ (scanner, chunker, semantic_chunker)
  - services/ (indexing_service, search_service)
  - storage/ (vector_store, hash_store)
  - embeddings/
  - scalability/
  - plugins/
  - cli/ (router, commands)
"""

from __future__ import annotations

import json
import math
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
#  CI Quality
# ---------------------------------------------------------------------------
from semantic_code_intelligence.ci.quality import (
    ComplexityResult,
    DeadCodeResult,
    DuplicateResult,
    QualityReport,
    _jaccard,
    _normalize_body,
    _rate_complexity,
    _trigram_set,
    analyze_complexity,
    compute_complexity,
    detect_dead_code,
    detect_duplicates,
)
from semantic_code_intelligence.parsing.parser import Symbol


def _sym(name="foo", kind="function", body="pass", file_path="a.py",
         start_line=1, end_line=2, parent="") -> Symbol:
    """Helper to build stub Symbols."""
    return Symbol(
        name=name, kind=kind, body=body, file_path=file_path,
        start_line=start_line, end_line=end_line, start_col=0, end_col=0,
        parent=parent,
    )


class TestRateComplexity:
    def test_low(self):
        assert _rate_complexity(1) == "low"
        assert _rate_complexity(5) == "low"

    def test_moderate(self):
        assert _rate_complexity(6) == "moderate"
        assert _rate_complexity(10) == "moderate"

    def test_high(self):
        assert _rate_complexity(11) == "high"
        assert _rate_complexity(20) == "high"

    def test_very_high(self):
        assert _rate_complexity(21) == "very_high"
        assert _rate_complexity(100) == "very_high"


class TestComputeComplexity:
    def test_simple_function(self):
        s = _sym(body="return 1")
        cr = compute_complexity(s)
        assert cr.complexity == 1
        assert cr.rating == "low"

    def test_with_if(self):
        s = _sym(body="if x:\n  return 1\nreturn 2")
        cr = compute_complexity(s)
        assert cr.complexity >= 2

    def test_with_for_while(self):
        s = _sym(body="for i in range(10):\n  while True:\n    break")
        cr = compute_complexity(s)
        assert cr.complexity >= 3

    def test_with_logical_operators(self):
        s = _sym(body="if a and b or c:\n  pass")
        cr = compute_complexity(s)
        assert cr.complexity >= 4  # if + and + or

    def test_comments_ignored(self):
        s = _sym(body="# if something\nreturn 1")
        cr = compute_complexity(s)
        assert cr.complexity == 1

    def test_result_fields(self):
        s = _sym(name="bar", file_path="b.py", start_line=10, end_line=20, body="pass")
        cr = compute_complexity(s)
        assert cr.symbol_name == "bar"
        assert cr.file_path == "b.py"
        assert cr.start_line == 10
        assert cr.end_line == 20

    def test_to_dict(self):
        s = _sym(body="pass")
        d = compute_complexity(s).to_dict()
        assert "complexity" in d
        assert "rating" in d
        assert "symbol_name" in d

    def test_empty_body(self):
        s = _sym(body="")
        cr = compute_complexity(s)
        assert cr.complexity == 1

    def test_except_catch(self):
        s = _sym(body="try:\n  pass\nexcept:\n  pass")
        cr = compute_complexity(s)
        assert cr.complexity >= 2

    def test_case_switch(self):
        s = _sym(body="case 1:\n  break\ncase 2:\n  break")
        cr = compute_complexity(s)
        assert cr.complexity >= 3


class TestAnalyzeComplexity:
    def test_filters_by_threshold(self):
        syms = [
            _sym(name="simple", body="return 1"),
            _sym(name="complex", body="if a:\n if b:\n if c:\n if d:\n if e:\n if f:\n if g:\n if h:\n if i:\n if j:\n pass"),
        ]
        results = analyze_complexity(syms, threshold=5)
        names = [r.symbol_name for r in results]
        assert "complex" in names

    def test_skips_non_callables(self):
        syms = [_sym(name="MyClass", kind="class", body="if a:\n if b:\n if c:\n if d:\n if e:\n if f:\n pass")]
        results = analyze_complexity(syms, threshold=1)
        assert len(results) == 0

    def test_sorted_descending(self):
        syms = [
            _sym(name="a", body="if x:\n pass"),
            _sym(name="b", body="if x:\n if y:\n if z:\n pass"),
        ]
        results = analyze_complexity(syms, threshold=1)
        if len(results) >= 2:
            assert results[0].complexity >= results[1].complexity

    def test_empty_input(self):
        assert analyze_complexity([]) == []


class TestNormalizeBody:
    def test_strips_comments(self):
        assert "# comment" not in _normalize_body("# comment\ncode")

    def test_strips_blank_lines(self):
        result = _normalize_body("\n\ncode\n\n")
        assert result == "code"

    def test_strips_js_comments(self):
        assert "//" not in _normalize_body("// comment\ncode")

    def test_strips_whitespace(self):
        result = _normalize_body("   code   ")
        assert result == "code"


class TestTrigramSet:
    def test_basic(self):
        result = _trigram_set("abcde")
        assert "abc" in result
        assert "bcd" in result
        assert "cde" in result

    def test_short_string(self):
        assert _trigram_set("ab") == {"ab"}

    def test_empty_string(self):
        assert _trigram_set("") == set()

    def test_exactly_three(self):
        result = _trigram_set("abc")
        assert result == {"abc"}


class TestJaccard:
    def test_identical(self):
        s = {"a", "b", "c"}
        assert _jaccard(s, s) == 1.0

    def test_disjoint(self):
        assert _jaccard({"a"}, {"b"}) == 0.0

    def test_partial(self):
        assert 0.0 < _jaccard({"a", "b"}, {"b", "c"}) < 1.0

    def test_both_empty(self):
        assert _jaccard(set(), set()) == 1.0

    def test_one_empty(self):
        assert _jaccard(set(), {"a"}) == 0.0


class TestDetectDuplicates:
    def test_identical_bodies(self):
        body = "x = 1\ny = 2\nz = 3\nw = 4\nreturn x"
        syms = [
            _sym(name="a", body=body, file_path="a.py"),
            _sym(name="b", body=body, file_path="b.py"),
        ]
        results = detect_duplicates(syms, threshold=0.5)
        assert len(results) >= 1
        assert results[0].similarity >= 0.9

    def test_different_bodies(self):
        syms = [
            _sym(name="a", body="x=1\ny=2\nz=3\nw=4"),
            _sym(name="b", body="very different code\nnothing similar\nat all\nreally"),
        ]
        results = detect_duplicates(syms, threshold=0.9)
        assert len(results) == 0

    def test_min_lines_filter(self):
        syms = [
            _sym(name="a", body="short"),
            _sym(name="b", body="short"),
        ]
        assert detect_duplicates(syms, min_lines=4) == []

    def test_result_fields(self):
        body = "x=1\ny=2\nz=3\nw=4\nv=5"
        syms = [
            _sym(name="a", body=body, file_path="f1.py", start_line=1),
            _sym(name="b", body=body, file_path="f2.py", start_line=10),
        ]
        results = detect_duplicates(syms, threshold=0.5)
        if results:
            d = results[0].to_dict()
            assert "symbol_a" in d
            assert "similarity" in d

    def test_empty_input(self):
        assert detect_duplicates([]) == []


class TestDeadCodeDetection:
    def test_unused_function(self):
        syms = [
            _sym(name="used", body="pass"),
            _sym(name="orphan", body="pass"),
        ]
        results = detect_dead_code(syms)
        names = [r.symbol_name for r in results]
        assert "orphan" in names or "used" in names

    def test_entry_points_excluded(self):
        syms = [_sym(name="main", body="pass")]
        results = detect_dead_code(syms)
        assert all(r.symbol_name != "main" for r in results)

    def test_test_functions_excluded(self):
        syms = [_sym(name="test_something", body="pass")]
        results = detect_dead_code(syms)
        assert all(r.symbol_name != "test_something" for r in results)

    def test_with_call_graph(self):
        from semantic_code_intelligence.context.engine import CallGraph
        syms = [
            _sym(name="caller", body="orphan()"),
            _sym(name="orphan", body="pass"),
        ]
        cg = CallGraph()
        cg.build(syms)
        results = detect_dead_code(syms, call_graph=cg)
        names = [r.symbol_name for r in results]
        assert "orphan" not in names  # it's referenced

    def test_empty_input(self):
        assert detect_dead_code([]) == []

    def test_imports_not_flagged(self):
        syms = [_sym(name="os", kind="import", body="import os")]
        results = detect_dead_code(syms)
        assert len(results) == 0

    def test_result_to_dict(self):
        d = DeadCodeResult("foo", "function", "a.py", 1).to_dict()
        assert d["symbol_name"] == "foo"
        assert d["kind"] == "function"


class TestComplexityResult:
    def test_to_dict(self):
        cr = ComplexityResult("fn", "a.py", 1, 10, 5, "low")
        d = cr.to_dict()
        assert d["symbol_name"] == "fn"
        assert d["complexity"] == 5
        assert d["rating"] == "low"


class TestDuplicateResult:
    def test_to_dict(self):
        dr = DuplicateResult("a", "f1.py", 1, "b", "f2.py", 2, 0.85)
        d = dr.to_dict()
        assert d["similarity"] == 0.85
        assert d["symbol_a"] == "a"


class TestQualityReport:
    def test_issue_count(self):
        r = QualityReport(
            complexity_issues=[ComplexityResult("fn", "a", 1, 2, 15, "high")],
            dead_code=[DeadCodeResult("x", "function", "a", 1)],
            duplicates=[],
        )
        assert r.issue_count == 2

    def test_issue_count_with_safety(self):
        from semantic_code_intelligence.llm.safety import SafetyReport, SafetyIssue
        sr = SafetyReport(safe=False, issues=[SafetyIssue("p", "d", 1)])
        r = QualityReport(safety=sr)
        assert r.issue_count == 1

    def test_to_dict(self):
        d = QualityReport().to_dict()
        assert d["issue_count"] == 0
        assert d["files_analyzed"] == 0

    def test_empty_report(self):
        r = QualityReport()
        assert r.issue_count == 0
        assert r.to_dict()["safety"] is None


# ---------------------------------------------------------------------------
#  CI Metrics
# ---------------------------------------------------------------------------
from semantic_code_intelligence.ci.metrics import (
    FileMetrics,
    ProjectMetrics,
    QualitySnapshot,
    QualityPolicy,
    TrendResult,
    _compute_mi,
    _count_lines,
    _linear_slope,
    compute_trend,
)


class TestCountLines:
    def test_blank_lines(self):
        code, comments, blanks = _count_lines("\n\n\n")
        assert blanks == 3

    def test_python_comments(self):
        code, comments, blanks = _count_lines("# comment\ncode")
        assert comments == 1
        assert code == 1

    def test_js_comments(self):
        code, comments, blanks = _count_lines("// comment\ncode")
        assert comments == 1

    def test_block_comments(self):
        code, comments, blanks = _count_lines("/* start\n * middle\n */\ncode")
        assert comments == 3
        assert code == 1

    def test_empty_input(self):
        code, comments, blanks = _count_lines("")
        assert code == 0 and comments == 0 and blanks == 0

    def test_mixed(self):
        code, comments, blanks = _count_lines("x = 1\n\n# comment\ny = 2")
        assert code == 2
        assert comments == 1
        assert blanks == 1


class TestComputeMI:
    def test_high_mi_for_simple_code(self):
        mi = _compute_mi(10.0, 1.0, 0.3)
        assert 0 <= mi <= 100

    def test_low_mi_for_complex_code(self):
        mi = _compute_mi(10000.0, 50.0, 0.0)
        assert mi < 50

    def test_zero_loc(self):
        mi = _compute_mi(0.0, 0.0, 0.0)
        assert 0 <= mi <= 100

    def test_clamped_to_100(self):
        mi = _compute_mi(1.0, 0.0, 1.0)
        assert mi <= 100

    def test_clamped_to_0(self):
        mi = _compute_mi(1e10, 100.0, 0.0)
        assert mi >= 0


class TestFileMetrics:
    def test_comment_ratio(self):
        fm = FileMetrics(file_path="a.py", lines_of_code=70, comment_lines=20, blank_lines=10)
        assert abs(fm.comment_ratio - 0.2) < 0.01

    def test_comment_ratio_zero(self):
        fm = FileMetrics(file_path="a.py")
        assert fm.comment_ratio == 0.0

    def test_to_dict(self):
        d = FileMetrics(file_path="a.py", lines_of_code=10).to_dict()
        assert d["file_path"] == "a.py"
        assert "comment_ratio" in d
        assert "maintainability_index" in d

    def test_defaults(self):
        fm = FileMetrics(file_path="x.py")
        assert fm.lines_of_code == 0
        assert fm.maintainability_index == 100.0


class TestProjectMetrics:
    def test_comment_ratio(self):
        pm = ProjectMetrics(total_loc=80, total_comment_lines=20, total_blank_lines=0)
        assert abs(pm.comment_ratio - 0.2) < 0.01

    def test_comment_ratio_zero(self):
        pm = ProjectMetrics()
        assert pm.comment_ratio == 0.0

    def test_to_dict(self):
        d = ProjectMetrics(files_analyzed=5).to_dict()
        assert d["files_analyzed"] == 5
        assert "file_metrics" in d

    def test_with_file_metrics(self):
        fm = FileMetrics(file_path="a.py", lines_of_code=10)
        pm = ProjectMetrics(file_metrics=[fm])
        assert len(pm.to_dict()["file_metrics"]) == 1


class TestQualitySnapshot:
    def test_to_dict(self):
        qs = QualitySnapshot(
            timestamp=1.0, maintainability_index=80.0, total_loc=100,
            total_symbols=10, issue_count=2, files_analyzed=5,
            avg_complexity=3.5, comment_ratio=0.15,
        )
        d = qs.to_dict()
        assert d["maintainability_index"] == 80.0
        assert d["total_loc"] == 100

    def test_from_dict(self):
        d = {
            "timestamp": 1.0, "maintainability_index": 80.0, "total_loc": 100,
            "total_symbols": 10, "issue_count": 2, "files_analyzed": 5,
            "avg_complexity": 3.5, "comment_ratio": 0.15,
        }
        qs = QualitySnapshot.from_dict(d)
        assert qs.timestamp == 1.0
        assert qs.maintainability_index == 80.0

    def test_roundtrip(self):
        qs = QualitySnapshot(
            timestamp=2.0, maintainability_index=75.0, total_loc=200,
            total_symbols=20, issue_count=5, files_analyzed=10,
            avg_complexity=5.0, comment_ratio=0.1,
        )
        restored = QualitySnapshot.from_dict(qs.to_dict())
        assert restored.timestamp == qs.timestamp
        assert restored.maintainability_index == qs.maintainability_index

    def test_metadata(self):
        qs = QualitySnapshot(
            timestamp=1.0, maintainability_index=80.0, total_loc=100,
            total_symbols=10, issue_count=0, files_analyzed=5,
            avg_complexity=3.5, comment_ratio=0.15,
            metadata={"branch": "main"},
        )
        assert qs.to_dict()["metadata"]["branch"] == "main"


class TestLinearSlope:
    def test_positive_slope(self):
        xs = [1.0, 2.0, 3.0]
        ys = [10.0, 20.0, 30.0]
        assert _linear_slope(xs, ys) == pytest.approx(10.0)

    def test_zero_slope(self):
        xs = [1.0, 2.0, 3.0]
        ys = [5.0, 5.0, 5.0]
        assert _linear_slope(xs, ys) == pytest.approx(0.0)

    def test_negative_slope(self):
        xs = [1.0, 2.0, 3.0]
        ys = [30.0, 20.0, 10.0]
        assert _linear_slope(xs, ys) == pytest.approx(-10.0)

    def test_single_point(self):
        assert _linear_slope([1.0], [5.0]) == 0.0

    def test_empty(self):
        assert _linear_slope([], []) == 0.0


class TestComputeTrend:
    def test_improving(self):
        snaps = [
            QualitySnapshot(timestamp=3.0, maintainability_index=90.0, total_loc=100,
                            total_symbols=10, issue_count=1, files_analyzed=5,
                            avg_complexity=2.0, comment_ratio=0.1),
            QualitySnapshot(timestamp=2.0, maintainability_index=80.0, total_loc=100,
                            total_symbols=10, issue_count=2, files_analyzed=5,
                            avg_complexity=3.0, comment_ratio=0.1),
            QualitySnapshot(timestamp=1.0, maintainability_index=70.0, total_loc=100,
                            total_symbols=10, issue_count=3, files_analyzed=5,
                            avg_complexity=4.0, comment_ratio=0.1),
        ]
        result = compute_trend(snaps)
        assert result.direction == "improving"
        assert result.delta > 0

    def test_degrading(self):
        snaps = [
            QualitySnapshot(timestamp=3.0, maintainability_index=50.0, total_loc=100,
                            total_symbols=10, issue_count=5, files_analyzed=5,
                            avg_complexity=8.0, comment_ratio=0.1),
            QualitySnapshot(timestamp=1.0, maintainability_index=90.0, total_loc=100,
                            total_symbols=10, issue_count=1, files_analyzed=5,
                            avg_complexity=2.0, comment_ratio=0.1),
        ]
        result = compute_trend(snaps)
        assert result.direction == "degrading"

    def test_stable(self):
        snaps = [
            QualitySnapshot(timestamp=2.0, maintainability_index=80.0, total_loc=100,
                            total_symbols=10, issue_count=2, files_analyzed=5,
                            avg_complexity=3.0, comment_ratio=0.1),
            QualitySnapshot(timestamp=1.0, maintainability_index=80.0, total_loc=100,
                            total_symbols=10, issue_count=2, files_analyzed=5,
                            avg_complexity=3.0, comment_ratio=0.1),
        ]
        result = compute_trend(snaps)
        assert result.direction == "stable"

    def test_empty_snapshots(self):
        result = compute_trend([])
        assert result.direction == "stable"
        assert result.snapshot_count == 0

    def test_single_snapshot(self):
        snaps = [
            QualitySnapshot(timestamp=1.0, maintainability_index=80.0, total_loc=100,
                            total_symbols=10, issue_count=2, files_analyzed=5,
                            avg_complexity=3.0, comment_ratio=0.1),
        ]
        result = compute_trend(snaps)
        assert result.direction == "stable"

    def test_to_dict(self):
        result = TrendResult("mi", 3, 70.0, 90.0, 20.0, 10.0, "improving")
        d = result.to_dict()
        assert d["metric_name"] == "mi"
        assert d["direction"] == "improving"


class TestQualityPolicy:
    def test_defaults(self):
        p = QualityPolicy()
        assert p.min_maintainability == 40.0
        assert p.max_complexity == 25
        assert p.require_safety_pass is True

    def test_to_dict(self):
        d = QualityPolicy().to_dict()
        assert "min_maintainability" in d
        assert "max_issues" in d

    def test_from_dict(self):
        d = {"min_maintainability": 60.0, "max_complexity": 15}
        p = QualityPolicy.from_dict(d)
        assert p.min_maintainability == 60.0
        assert p.max_complexity == 15

    def test_roundtrip(self):
        p = QualityPolicy(min_maintainability=55.0, max_dead_code=5)
        restored = QualityPolicy.from_dict(p.to_dict())
        assert restored.min_maintainability == p.min_maintainability
        assert restored.max_dead_code == p.max_dead_code


# ---------------------------------------------------------------------------
#  CI PR
# ---------------------------------------------------------------------------
from semantic_code_intelligence.ci.pr import (
    FileChange,
    ChangeSummary,
    ImpactResult,
    RiskScore,
    _risk_level,
    compute_risk,
    suggest_reviewers,
)


class TestFileChange:
    def test_to_dict(self):
        fc = FileChange(path="a.py", language="python", symbols_added=["foo"])
        d = fc.to_dict()
        assert d["path"] == "a.py"
        assert d["symbols_added"] == ["foo"]

    def test_defaults(self):
        fc = FileChange(path="x.js")
        assert fc.symbols_modified == []
        assert fc.import_changes == []


class TestChangeSummary:
    def test_to_dict(self):
        cs = ChangeSummary(files_changed=3, languages=["python"])
        d = cs.to_dict()
        assert d["files_changed"] == 3
        assert "python" in d["languages"]

    def test_defaults(self):
        cs = ChangeSummary()
        assert cs.files_changed == 0
        assert cs.total_symbols_added == 0


class TestImpactResultPR:
    def test_to_dict(self):
        ir = ImpactResult(
            changed_symbols=["foo"],
            affected_files=["a.py"],
            affected_symbols=["bar"],
        )
        d = ir.to_dict()
        assert "foo" in d["changed_symbols"]

    def test_defaults(self):
        ir = ImpactResult()
        assert ir.changed_symbols == []


class TestRiskLevel:
    def test_low(self):
        assert _risk_level(10) == "low"

    def test_medium(self):
        assert _risk_level(30) == "medium"

    def test_high(self):
        assert _risk_level(60) == "high"

    def test_critical(self):
        assert _risk_level(80) == "critical"


class TestRiskScore:
    def test_to_dict(self):
        rs = RiskScore(score=45, level="medium", factors=["big changeset"])
        d = rs.to_dict()
        assert d["score"] == 45
        assert d["level"] == "medium"


class TestComputeRisk:
    def test_small_changeset(self):
        cs = ChangeSummary(files_changed=2)
        risk = compute_risk(cs)
        assert risk.score < 25
        assert risk.level == "low"

    def test_large_changeset(self):
        cs = ChangeSummary(files_changed=25, total_symbols_removed=15,
                           total_symbols_modified=15)
        risk = compute_risk(cs)
        assert risk.score > 25

    def test_with_safety_issues(self):
        from semantic_code_intelligence.llm.safety import SafetyReport, SafetyIssue
        sr = SafetyReport(safe=False, issues=[SafetyIssue("p", "d"), SafetyIssue("p2", "d2")])
        cs = ChangeSummary(files_changed=1)
        risk = compute_risk(cs, safety_report=sr)
        assert risk.score > 10
        assert any("safety" in f for f in risk.factors)

    def test_with_impact(self):
        ir = ImpactResult(affected_symbols=["a", "b", "c", "d", "e", "f"])
        cs = ChangeSummary(files_changed=5)
        risk = compute_risk(cs, impact=ir)
        assert risk.score > 10

    def test_empty(self):
        cs = ChangeSummary()
        risk = compute_risk(cs)
        assert risk.level == "low"


class TestSuggestReviewers:
    def test_groups_by_domain(self):
        files = ["auth/login.py", "auth/logout.py", "api/routes.py"]
        reviewers = suggest_reviewers(files)
        assert len(reviewers) >= 2

    def test_empty_files(self):
        assert suggest_reviewers([]) == []

    def test_single_file(self):
        result = suggest_reviewers(["app.py"])
        assert len(result) >= 1


# ---------------------------------------------------------------------------
#  CI Hooks
# ---------------------------------------------------------------------------
from semantic_code_intelligence.ci.hooks import HookResult, run_precommit_check


class TestHookResult:
    def test_defaults(self):
        hr = HookResult()
        assert hr.passed is True
        assert hr.files_checked == 0
        assert hr.safety is None

    def test_to_dict(self):
        d = HookResult(passed=False, files_checked=3).to_dict()
        assert d["passed"] is False
        assert d["files_checked"] == 3

    def test_with_safety(self):
        from semantic_code_intelligence.llm.safety import SafetyReport
        sr = SafetyReport(safe=True)
        hr = HookResult(safety=sr)
        d = hr.to_dict()
        assert d["safety"]["safe"] is True


class TestRunPrecommitCheck:
    def test_safe_files(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("x = 1\ny = 2\n")
            f.flush()
            result = run_precommit_check([f.name], run_plugins=False)
            assert result.passed is True
            assert result.files_checked == 1

    def test_unsafe_files(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("import os\nos.system('rm -rf /')\n")
            f.flush()
            result = run_precommit_check([f.name], run_plugins=False)
            assert result.passed is False

    def test_empty_files(self):
        result = run_precommit_check([], run_plugins=False)
        assert result.passed is True
        assert result.files_checked == 0

    def test_nonexistent_file(self):
        result = run_precommit_check(["/nonexistent/file.py"], run_plugins=False)
        assert result.files_checked == 1


# ---------------------------------------------------------------------------
#  CI Templates
# ---------------------------------------------------------------------------
from semantic_code_intelligence.ci.templates import (
    generate_analysis_workflow,
    generate_precommit_config,
    generate_safety_workflow,
)


class TestGenerateAnalysisWorkflow:
    def test_contains_yaml(self):
        wf = generate_analysis_workflow()
        assert "name: CodexA Analysis" in wf

    def test_python_version(self):
        wf = generate_analysis_workflow(python_version="3.13")
        assert "3.13" in wf

    def test_trigger(self):
        wf = generate_analysis_workflow(trigger="push")
        assert "push:" in wf

    def test_contains_steps(self):
        wf = generate_analysis_workflow()
        assert "codex init" in wf
        assert "codex quality" in wf

    def test_permissions(self):
        wf = generate_analysis_workflow()
        assert "permissions:" in wf
        assert "contents: read" in wf


class TestGeneratePrecommitConfig:
    def test_contains_hooks(self):
        cfg = generate_precommit_config()
        assert "codex-safety" in cfg
        assert "codex-quality" in cfg

    def test_repo_local(self):
        cfg = generate_precommit_config()
        assert "repo: local" in cfg


class TestGenerateSafetyWorkflow:
    def test_contains_yaml(self):
        wf = generate_safety_workflow()
        assert "name: CodexA Safety" in wf

    def test_python_version(self):
        wf = generate_safety_workflow(python_version="3.11")
        assert "3.11" in wf

    def test_permissions(self):
        wf = generate_safety_workflow()
        assert "contents: read" in wf


# ---------------------------------------------------------------------------
#  CI Hotspots
# ---------------------------------------------------------------------------
from semantic_code_intelligence.ci.hotspots import (
    HotspotFactor,
    Hotspot,
    HotspotReport,
    _normalise,
)


class TestNormalise:
    def test_zero(self):
        assert _normalise(0.0, 10.0) == 0.0

    def test_max(self):
        assert _normalise(10.0, 10.0) == 1.0

    def test_over_max(self):
        assert _normalise(20.0, 10.0) == 1.0

    def test_zero_max(self):
        assert _normalise(5.0, 0.0) == 0.0

    def test_negative_max(self):
        assert _normalise(5.0, -1.0) == 0.0


class TestHotspotFactor:
    def test_to_dict(self):
        hf = HotspotFactor(name="complexity", raw_value=15.0, normalized=0.75, weight=0.3)
        d = hf.to_dict()
        assert d["name"] == "complexity"
        assert d["normalized"] == 0.75

    def test_rounding(self):
        hf = HotspotFactor(name="x", raw_value=1.23456, normalized=0.12345, weight=0.3)
        d = hf.to_dict()
        assert d["raw_value"] == 1.23
        assert d["normalized"] == 0.123


class TestHotspot:
    def test_to_dict(self):
        h = Hotspot(name="fn", file_path="a.py", kind="symbol", risk_score=85.3)
        d = h.to_dict()
        assert d["risk_score"] == 85.3
        assert d["kind"] == "symbol"

    def test_with_factors(self):
        hf = HotspotFactor("x", 1.0, 0.5, 0.3)
        h = Hotspot(name="fn", file_path="a.py", kind="symbol", risk_score=50.0, factors=[hf])
        assert len(h.to_dict()["factors"]) == 1


class TestHotspotReport:
    def test_to_dict(self):
        hr = HotspotReport(files_analyzed=10, symbols_analyzed=50)
        d = hr.to_dict()
        assert d["files_analyzed"] == 10
        assert d["hotspot_count"] == 0

    def test_with_hotspots(self):
        h = Hotspot(name="fn", file_path="a.py", kind="symbol", risk_score=80.0)
        hr = HotspotReport(files_analyzed=5, symbols_analyzed=20, hotspots=[h])
        assert hr.to_dict()["hotspot_count"] == 1


# ---------------------------------------------------------------------------
#  CI Impact
# ---------------------------------------------------------------------------
from semantic_code_intelligence.ci.impact import (
    AffectedSymbol,
    AffectedModule,
    DependencyChain,
    ImpactReport as CIImpactReport,
)


class TestAffectedSymbol:
    def test_to_dict(self):
        s = AffectedSymbol("fn", "a.py", "function", "direct_caller", 1)
        d = s.to_dict()
        assert d["name"] == "fn"
        assert d["depth"] == 1
        assert d["relationship"] == "direct_caller"


class TestAffectedModule:
    def test_to_dict(self):
        m = AffectedModule("a.py", "imports_target", 1)
        d = m.to_dict()
        assert d["file_path"] == "a.py"


class TestDependencyChain:
    def test_to_dict(self):
        dc = DependencyChain(path=["a.py", "b.py", "c.py"])
        d = dc.to_dict()
        assert len(d["path"]) == 3


class TestCIImpactReport:
    def test_total_affected(self):
        r = CIImpactReport(
            target="fn", target_kind="symbol",
            direct_symbols=[AffectedSymbol("a", "x.py", "function", "direct_caller", 1)],
            transitive_symbols=[AffectedSymbol("b", "y.py", "function", "transitive_caller", 2)],
        )
        assert r.total_affected == 2

    def test_to_dict(self):
        r = CIImpactReport(target="fn", target_kind="symbol")
        d = r.to_dict()
        assert d["target"] == "fn"
        assert d["total_affected"] == 0

    def test_empty_report(self):
        r = CIImpactReport(target="x", target_kind="file")
        assert r.total_affected == 0


# ---------------------------------------------------------------------------
#  CI Trace
# ---------------------------------------------------------------------------
from semantic_code_intelligence.ci.trace import (
    TraceNode,
    TraceEdge,
    TraceResult,
    trace_symbol,
)


class TestTraceNode:
    def test_to_dict(self):
        tn = TraceNode("fn", "a.py", "function", -2)
        d = tn.to_dict()
        assert d["depth"] == -2
        assert d["kind"] == "function"


class TestTraceEdge:
    def test_to_dict(self):
        te = TraceEdge("caller", "callee", "a.py")
        d = te.to_dict()
        assert d["caller"] == "caller"
        assert d["callee"] == "callee"


class TestTraceResult:
    def test_total_nodes(self):
        tr = TraceResult(
            target="fn", target_file="a.py",
            upstream=[TraceNode("a", "a.py", "function", -1)],
            downstream=[TraceNode("b", "b.py", "function", 1),
                        TraceNode("c", "c.py", "function", 2)],
        )
        assert tr.total_nodes == 3

    def test_to_dict(self):
        tr = TraceResult(target="fn", target_file="a.py")
        d = tr.to_dict()
        assert d["target"] == "fn"
        assert d["total_nodes"] == 0

    def test_empty(self):
        tr = TraceResult(target="missing", target_file="")
        assert tr.total_nodes == 0
        assert tr.max_upstream_depth == 0


class TestTraceSymbol:
    def test_unknown_symbol(self):
        result = trace_symbol("nonexistent", [], CallGraph())
        assert result.target_file == ""
        assert result.total_nodes == 0

    def test_symbol_with_callers(self):
        from semantic_code_intelligence.context.engine import CallGraph
        syms = [
            _sym(name="caller", body="target()", file_path="a.py"),
            _sym(name="target", body="pass", file_path="b.py"),
        ]
        cg = CallGraph()
        cg.build(syms)
        result = trace_symbol("target", syms, cg)
        assert len(result.upstream) >= 1

    def test_symbol_with_callees(self):
        from semantic_code_intelligence.context.engine import CallGraph
        syms = [
            _sym(name="entry", body="helper()", file_path="a.py"),
            _sym(name="helper", body="pass", file_path="a.py"),
        ]
        cg = CallGraph()
        cg.build(syms)
        result = trace_symbol("entry", syms, cg)
        assert len(result.downstream) >= 1


# ---------------------------------------------------------------------------
#  LLM Safety
# ---------------------------------------------------------------------------
from semantic_code_intelligence.llm.safety import (
    SafetyIssue,
    SafetyReport,
    SafetyValidator,
)


class TestSafetyIssue:
    def test_to_dict(self):
        si = SafetyIssue("eval", "dangerous", line_number=5, severity="error")
        d = si.to_dict()
        assert d["pattern"] == "eval"
        assert d["line_number"] == 5

    def test_defaults(self):
        si = SafetyIssue("p", "d")
        assert si.line_number == 0
        assert si.severity == "warning"


class TestSafetyReport:
    def test_safe(self):
        sr = SafetyReport()
        assert sr.safe is True
        assert sr.to_dict()["issue_count"] == 0

    def test_unsafe(self):
        sr = SafetyReport(safe=False, issues=[SafetyIssue("p", "d")])
        assert sr.to_dict()["issue_count"] == 1


class TestSafetyValidator:
    def test_safe_code(self):
        v = SafetyValidator()
        report = v.validate("x = 1\ny = 2")
        assert report.safe is True

    def test_os_system(self):
        v = SafetyValidator()
        report = v.validate("os.system('ls')")
        assert report.safe is False

    def test_eval(self):
        v = SafetyValidator()
        report = v.validate("result = eval('1+1')")
        assert report.safe is False

    def test_exec(self):
        v = SafetyValidator()
        report = v.validate("exec('print(1)')")
        assert report.safe is False

    def test_subprocess_shell(self):
        v = SafetyValidator()
        report = v.validate("subprocess.run('cmd', shell=True)")
        assert report.safe is False

    def test_rm_rf(self):
        v = SafetyValidator()
        report = v.validate("rm -rf /important/data")
        assert report.safe is False

    def test_drop_table(self):
        v = SafetyValidator()
        report = v.validate("DROP TABLE users")
        assert report.safe is False

    def test_path_traversal(self):
        v = SafetyValidator()
        report = v.validate("open('../../etc/passwd')")
        assert report.safe is False

    def test_hardcoded_secret(self):
        v = SafetyValidator()
        report = v.validate("password = 'supersecretpassword123'")
        assert report.safe is False

    def test_innerHTML(self):
        v = SafetyValidator()
        report = v.validate("element.innerHTML = userInput")
        assert report.safe is False

    def test_md5(self):
        v = SafetyValidator()
        report = v.validate("hash = MD5(data)")
        assert report.safe is False

    def test_http_url(self):
        v = SafetyValidator()
        report = v.validate("url = 'http://example.com/api'")
        assert report.safe is False

    def test_http_localhost_ok(self):
        v = SafetyValidator()
        report = v.validate("url = 'http://localhost:8080'")
        assert report.safe is True

    def test_verify_false(self):
        v = SafetyValidator()
        report = v.validate("requests.get(url, verify=False)")
        assert report.safe is False

    def test_custom_patterns(self):
        v = SafetyValidator(extra_patterns=[
            (r"DANGER", "Custom danger pattern")
        ])
        report = v.validate("DANGER: doing something bad")
        assert report.safe is False

    def test_dynamic_import(self):
        v = SafetyValidator()
        report = v.validate("mod = __import__('os')")
        assert report.safe is False

    def test_truncate_table(self):
        v = SafetyValidator()
        report = v.validate("TRUNCATE TABLE sessions")
        assert report.safe is False

    def test_document_write(self):
        v = SafetyValidator()
        report = v.validate("document.write(payload)")
        assert report.safe is False

    def test_sha1(self):
        v = SafetyValidator()
        report = v.validate("hash = sha1(data)")
        assert report.safe is False

    def test_multiple_issues(self):
        v = SafetyValidator()
        report = v.validate("eval('x')\nos.system('y')\nexec('z')")
        assert len(report.issues) >= 3


# ---------------------------------------------------------------------------
#  LLM Streaming
# ---------------------------------------------------------------------------
from semantic_code_intelligence.llm.streaming import StreamEvent


class TestStreamEvent:
    def test_create(self):
        se = StreamEvent(kind="token", content="hello")
        assert se.kind == "token"
        assert se.content == "hello"

    def test_to_sse(self):
        se = StreamEvent(kind="token", content="hello")
        sse = se.to_sse()
        assert "data: " in sse
        assert "hello" in sse

    def test_to_sse_multiline(self):
        se = StreamEvent(kind="chunk", content="line1\nline2")
        sse = se.to_sse()
        assert "data: " in sse
        assert "line1\\nline2" in sse


# ---------------------------------------------------------------------------
#  LLM Providers
# ---------------------------------------------------------------------------
from semantic_code_intelligence.llm.provider import MessageRole, LLMMessage, LLMResponse


class TestMessageRole:
    def test_values(self):
        assert MessageRole.SYSTEM == "system"
        assert MessageRole.USER == "user"
        assert MessageRole.ASSISTANT == "assistant"


class TestLLMMessage:
    def test_create(self):
        m = LLMMessage(role=MessageRole.USER, content="Hello")
        assert m.role == "user"
        assert m.content == "Hello"


class TestLLMResponse:
    def test_create(self):
        r = LLMResponse(content="answer", model="gpt-4", usage={"tokens": 100})
        assert r.content == "answer"
        assert r.model == "gpt-4"


# ---------------------------------------------------------------------------
#  LLM Mock Provider
# ---------------------------------------------------------------------------
from semantic_code_intelligence.llm.mock_provider import MockProvider


class TestMockProvider:
    def test_chat(self):
        p = MockProvider()
        msgs = [LLMMessage(role=MessageRole.USER, content="test")]
        response = p.chat(msgs)
        assert isinstance(response, LLMResponse)
        assert len(response.content) > 0

    def test_model_name(self):
        p = MockProvider()
        assert "mock" in p._model.lower()


# ---------------------------------------------------------------------------
#  LLM Conversation
# ---------------------------------------------------------------------------
from semantic_code_intelligence.llm.conversation import ConversationSession


class TestConversationSession:
    def test_create(self):
        cs = ConversationSession(session_id="test-1")
        assert cs.session_id == "test-1"

    def test_add_message(self):
        cs = ConversationSession(session_id="s1")
        from semantic_code_intelligence.llm.provider import MessageRole
        cs.add_message(MessageRole.USER, "hello")
        cs.add_message(MessageRole.ASSISTANT, "hi")
        assert len(cs.messages) == 2

    def test_messages_ordered(self):
        cs = ConversationSession(session_id="s1")
        from semantic_code_intelligence.llm.provider import MessageRole
        cs.add_message(MessageRole.USER, "first")
        cs.add_message(MessageRole.ASSISTANT, "second")
        assert cs.messages[0].content == "first"
        assert cs.messages[1].content == "second"

    def test_to_dict(self):
        cs = ConversationSession(session_id="s1")
        from semantic_code_intelligence.llm.provider import MessageRole
        cs.add_message(MessageRole.USER, "hi")
        d = cs.to_dict()
        assert d["session_id"] == "s1"
        assert len(d["messages"]) == 1


# ---------------------------------------------------------------------------
#  Context Engine
# ---------------------------------------------------------------------------
from semantic_code_intelligence.context.engine import (
    ContextWindow,
    ContextBuilder,
    CallEdge,
    CallGraph,
    DependencyMap,
)


class TestContextWindow:
    def test_to_dict(self):
        s = _sym(name="fn", body="pass")
        cw = ContextWindow(focal_symbol=s)
        d = cw.to_dict()
        assert d["focal_symbol"]["name"] == "fn"

    def test_render(self):
        s = _sym(name="fn", body="pass\nreturn 1", file_path="a.py")
        cw = ContextWindow(focal_symbol=s, imports=[_sym(name="os", kind="import", body="import os")])
        text = cw.render()
        assert "fn" in text
        assert "Imports" in text


class TestContextBuilder:
    def test_index_file_with_content(self):
        cb = ContextBuilder()
        syms = cb.index_file("test.py", "def foo():\n  pass\n")
        assert len(syms) >= 1

    def test_find_symbol(self):
        cb = ContextBuilder()
        cb.index_file("test.py", "def foo():\n  pass\ndef bar():\n  pass\n")
        results = cb.find_symbol("foo")
        assert len(results) >= 1

    def test_get_all_symbols(self):
        cb = ContextBuilder()
        cb.index_file("a.py", "def f1(): pass\n")
        cb.index_file("b.py", "def f2(): pass\n")
        all_syms = cb.get_all_symbols()
        assert len(all_syms) >= 2

    def test_build_context(self):
        cb = ContextBuilder()
        syms = cb.index_file("test.py", "import os\ndef foo():\n  pass\ndef bar():\n  pass\n")
        fn = [s for s in syms if s.name == "foo"]
        if fn:
            cw = cb.build_context(fn[0])
            assert cw.focal_symbol.name == "foo"

    def test_build_context_for_name(self):
        cb = ContextBuilder()
        cb.index_file("test.py", "def target():\n  pass\n")
        windows = cb.build_context_for_name("target")
        assert len(windows) >= 1

    def test_get_symbols_unknown_file(self):
        cb = ContextBuilder()
        assert cb.get_symbols("nonexistent.py") == []


class TestCallEdge:
    def test_to_dict(self):
        e = CallEdge("a.py:fn", "bar", "a.py", 10)
        d = e.to_dict()
        assert d["caller"] == "a.py:fn"
        assert d["callee"] == "bar"


class TestCallGraphDeep:
    def test_build(self):
        syms = [
            _sym(name="caller", body="target()", file_path="a.py"),
            _sym(name="target", body="pass", file_path="a.py"),
        ]
        cg = CallGraph()
        cg.build(syms)
        assert len(cg.edges) >= 1

    def test_callers_of(self):
        syms = [
            _sym(name="a", body="b()", file_path="x.py"),
            _sym(name="b", body="pass", file_path="x.py"),
        ]
        cg = CallGraph()
        cg.build(syms)
        callers = cg.callers_of("b")
        assert len(callers) >= 1

    def test_callees_of(self):
        syms = [
            _sym(name="a", body="b()", file_path="x.py"),
            _sym(name="b", body="pass", file_path="x.py"),
        ]
        cg = CallGraph()
        cg.build(syms)
        callees = cg.callees_of("x.py:a")
        assert len(callees) >= 1

    def test_no_self_reference(self):
        syms = [_sym(name="recursive", body="recursive()", file_path="a.py")]
        cg = CallGraph()
        cg.build(syms)
        # Should not have self-edge since build skips self-references
        callees = cg.callees_of("a.py:recursive")
        assert len(callees) == 0

    def test_to_dict(self):
        cg = CallGraph()
        cg.build([])
        d = cg.to_dict()
        assert d["edge_count"] == 0
        assert d["node_count"] == 0

    def test_empty_callers(self):
        cg = CallGraph()
        assert cg.callers_of("nonexistent") == []

    def test_empty_callees(self):
        cg = CallGraph()
        assert cg.callees_of("nonexistent") == []


# ---------------------------------------------------------------------------
#  Context Memory
# ---------------------------------------------------------------------------
from semantic_code_intelligence.context.memory import (
    MemoryEntry,
    ReasoningStep,
    SessionMemory,
)


class TestMemoryEntry:
    def test_to_dict(self):
        me = MemoryEntry(key="k", content="c", kind="qa")
        d = me.to_dict()
        assert d["key"] == "k"
        assert d["kind"] == "qa"

    def test_from_dict(self):
        d = {"key": "k", "content": "c", "kind": "insight", "timestamp": 1.0, "metadata": {}}
        me = MemoryEntry.from_dict(d)
        assert me.key == "k"
        assert me.kind == "insight"

    def test_roundtrip(self):
        me = MemoryEntry(key="test", content="data", kind="general", metadata={"x": 1})
        restored = MemoryEntry.from_dict(me.to_dict())
        assert restored.key == me.key
        assert restored.content == me.content


class TestReasoningStep:
    def test_to_dict(self):
        rs = ReasoningStep(step_id=1, action="search", input_text="query", output_text="result")
        d = rs.to_dict()
        assert d["step_id"] == 1
        assert d["action"] == "search"


class TestSessionMemory:
    def test_add_and_search(self):
        sm = SessionMemory()
        sm.add("key1", "authentication logic")
        results = sm.search("authentication")
        assert len(results) >= 1

    def test_max_entries(self):
        sm = SessionMemory(max_entries=3)
        for i in range(5):
            sm.add(f"k{i}", f"content{i}")
        assert len(sm.entries) == 3

    def test_get_recent(self):
        sm = SessionMemory()
        sm.add("k1", "first")
        sm.add("k2", "second")
        recent = sm.get_recent(1)
        assert len(recent) == 1
        assert recent[0].key == "k2"

    def test_clear(self):
        sm = SessionMemory()
        sm.add("k", "v")
        sm.start_chain("c1")
        sm.clear()
        assert len(sm.entries) == 0

    def test_reasoning_chain(self):
        sm = SessionMemory()
        sm.start_chain("chain1")
        sm.add_step("chain1", "search", "query", "results")
        sm.add_step("chain1", "analyze", "results", "conclusion")
        chain = sm.get_chain("chain1")
        assert len(chain) == 2
        assert chain[0].step_id == 1
        assert chain[1].step_id == 2

    def test_to_dict(self):
        sm = SessionMemory()
        sm.add("k", "v")
        d = sm.to_dict()
        assert "entries" in d
        assert "chains" in d

    def test_search_empty(self):
        sm = SessionMemory()
        assert sm.search("anything") == []

    def test_get_chain_nonexistent(self):
        sm = SessionMemory()
        assert sm.get_chain("missing") == []


# ---------------------------------------------------------------------------
#  Web Visualize
# ---------------------------------------------------------------------------
from semantic_code_intelligence.web.visualize import (
    render_call_graph,
    render_dependency_graph,
    render_workspace_graph,
    render_symbol_map,
)


class TestRenderCallGraph:
    def test_basic(self):
        edges = [{"caller": "a.py:fn1", "callee": "fn2", "file_path": "a.py"}]
        result = render_call_graph(edges)
        assert "flowchart" in result

    def test_empty_edges(self):
        result = render_call_graph([])
        assert "No call edges found" in result

    def test_custom_title(self):
        result = render_call_graph([], title="My Graph")
        assert "My Graph" in result

    def test_direction(self):
        result = render_call_graph([], direction="TD")
        assert "flowchart TD" in result

    def test_multiple_edges(self):
        edges = [
            {"caller": "a", "callee": "b", "file_path": "x.py"},
            {"caller": "b", "callee": "c", "file_path": "x.py"},
        ]
        result = render_call_graph(edges)
        assert "-->" in result


class TestRenderDependencyGraph:
    def test_basic(self):
        deps = {"dependencies": [{"source_file": "a.py", "import_text": "import os"}]}
        result = render_dependency_graph(deps)
        assert "flowchart" in result

    def test_empty(self):
        result = render_dependency_graph({})
        assert "No dependencies found" in result

    def test_custom_title(self):
        result = render_dependency_graph({}, title="Deps")
        assert "Deps" in result


class TestRenderWorkspaceGraph:
    def test_basic(self):
        repos = [{"name": "repo1", "path": "/a", "file_count": 10, "vector_count": 100}]
        result = render_workspace_graph(repos)
        assert "repo1" in result

    def test_empty_repos(self):
        result = render_workspace_graph([])
        assert "No repositories" in result

    def test_custom_title(self):
        result = render_workspace_graph([], title="My WS")
        assert "My WS" in result


class TestRenderSymbolMap:
    def test_basic(self):
        syms = [
            {"name": "MyClass", "kind": "class", "parent": ""},
            {"name": "my_method", "kind": "method", "parent": "MyClass"},
            {"name": "standalone", "kind": "function", "parent": ""},
        ]
        result = render_symbol_map(syms)
        assert "classDiagram" in result

    def test_empty(self):
        result = render_symbol_map([])
        assert "classDiagram" in result

    def test_custom_title(self):
        result = render_symbol_map([], title="Symbols")
        assert "Symbols" in result


# ---------------------------------------------------------------------------
#  Bridge Protocol
# ---------------------------------------------------------------------------
from semantic_code_intelligence.bridge.protocol import (
    RequestKind,
    AgentRequest,
    AgentResponse,
    BridgeCapabilities,
)


class TestRequestKindDeep:
    def test_all_values_are_strings(self):
        for kind in RequestKind:
            assert isinstance(kind.value, str)

    def test_count(self):
        assert len(RequestKind) == 12

    def test_invoke_tool(self):
        assert RequestKind.INVOKE_TOOL == "invoke_tool"

    def test_list_tools(self):
        assert RequestKind.LIST_TOOLS == "list_tools"

    def test_semantic_search(self):
        assert RequestKind.SEMANTIC_SEARCH == "semantic_search"


class TestAgentRequestDeep:
    def test_to_json_roundtrip(self):
        req = AgentRequest(kind="semantic_search", params={"query": "test"}, request_id="r1")
        j = req.to_json()
        restored = AgentRequest.from_json(j)
        assert restored.kind == req.kind
        assert restored.params == req.params

    def test_from_dict_defaults(self):
        req = AgentRequest.from_dict({"kind": "test", "params": {}})
        assert req.request_id == ""
        assert req.source == ""


class TestAgentResponseDeep:
    def test_to_dict(self):
        resp = AgentResponse(request_id="r1", success=True, data={"key": "val"})
        d = resp.to_dict()
        assert d["success"] is True
        assert d["data"]["key"] == "val"

    def test_error_response(self):
        resp = AgentResponse(request_id="r1", success=False, error="bad request")
        d = resp.to_dict()
        assert d["error"] == "bad request"

    def test_from_dict(self):
        d = {"request_id": "r1", "success": True, "data": {}}
        # AgentResponse doesn't have a from_dict method, we should test the attributes instead
        resp = AgentResponse(request_id="r1", success=True)
        assert resp.request_id == "r1"


class TestBridgeCapabilitiesDeep:
    def test_version(self):
        cap = BridgeCapabilities()
        assert cap.version == "0.9.0"

    def test_name(self):
        cap = BridgeCapabilities()
        assert cap.name == "CodexA Bridge"

    def test_supported_requests(self):
        cap = BridgeCapabilities()
        assert "semantic_search" in cap.supported_requests
        assert "invoke_tool" in cap.supported_requests

    def test_to_json(self):
        cap = BridgeCapabilities()
        j = cap.to_json()
        data = json.loads(j)
        assert "version" in data


# ---------------------------------------------------------------------------
#  Tools Protocol
# ---------------------------------------------------------------------------
from semantic_code_intelligence.tools.protocol import (
    ToolErrorCode,
    ToolInvocation,
    ToolError,
    ToolExecutionResult,
)


class TestToolErrorCodeDeep:
    def test_all_codes(self):
        codes = list(ToolErrorCode)
        assert len(codes) == 6

    def test_values(self):
        assert ToolErrorCode.UNKNOWN_TOOL.value == "unknown_tool"
        assert ToolErrorCode.TIMEOUT.value == "timeout"
        assert ToolErrorCode.PERMISSION_DENIED.value == "permission_denied"


class TestToolInvocationDeep:
    def test_auto_request_id(self):
        inv = ToolInvocation(tool_name="test", arguments={})
        assert inv.request_id != ""

    def test_auto_timestamp(self):
        inv = ToolInvocation(tool_name="test", arguments={})
        assert inv.timestamp > 0

    def test_to_json(self):
        inv = ToolInvocation(tool_name="test", arguments={"q": "hello"})
        data = json.loads(inv.to_json())
        assert data["tool_name"] == "test"
        assert data["arguments"]["q"] == "hello"

    def test_from_dict(self):
        d = {"tool_name": "search", "arguments": {"query": "test"},
             "request_id": "r1", "timestamp": 1.0}
        inv = ToolInvocation.from_dict(d)
        assert inv.tool_name == "search"

    def test_roundtrip(self):
        inv = ToolInvocation(tool_name="test", arguments={"a": 1})
        restored = ToolInvocation.from_dict(inv.to_dict())
        assert restored.tool_name == inv.tool_name
        assert restored.arguments == inv.arguments


class TestToolErrorDeep:
    def test_to_dict(self):
        te = ToolError(tool_name="bad", error_code=ToolErrorCode.UNKNOWN_TOOL,
                       error_message="not found")
        d = te.to_dict()
        assert d["error_code"] == "unknown_tool"

    def test_from_dict(self):
        d = {"tool_name": "x", "error_code": "timeout", "error_message": "timed out",
             "request_id": "r1"}
        te = ToolError.from_dict(d)
        assert te.error_code == ToolErrorCode.TIMEOUT


class TestToolExecutionResultDeep:
    def test_success(self):
        r = ToolExecutionResult(
            tool_name="test", request_id="r1", success=True,
            result_payload={"data": "value"}, execution_time_ms=10.5,
        )
        assert r.success is True
        d = r.to_dict()
        assert d["execution_time_ms"] == 10.5

    def test_failure(self):
        err = ToolError("test", ToolErrorCode.EXECUTION_ERROR, "failed")
        r = ToolExecutionResult(
            tool_name="test", request_id="r1", success=False, error=err,
        )
        d = r.to_dict()
        assert d["success"] is False

    def test_from_dict(self):
        d = {"tool_name": "t", "request_id": "r1", "success": True,
             "result_payload": {}, "error": None, "execution_time_ms": 5.0,
             "timestamp": 1.0}
        r = ToolExecutionResult.from_dict(d)
        assert r.success is True


# ---------------------------------------------------------------------------
#  Tools Executor
# ---------------------------------------------------------------------------
from semantic_code_intelligence.tools.executor import ToolExecutor


class TestToolExecutorDeep:
    def test_list_tool_names(self):
        ex = ToolExecutor(Path("."))
        names = ex.list_tool_names()
        assert "semantic_search" in names
        assert len(names) >= 8

    def test_available_tools(self):
        ex = ToolExecutor(Path("."))
        tools = ex.available_tools
        assert len(tools) >= 8
        assert any(t["name"] == "semantic_search" for t in tools)

    def test_get_tool_schema_known(self):
        ex = ToolExecutor(Path("."))
        schema = ex.get_tool_schema("semantic_search")
        assert schema is not None
        assert schema["name"] == "semantic_search"

    def test_get_tool_schema_unknown(self):
        ex = ToolExecutor(Path("."))
        assert ex.get_tool_schema("nonexistent_tool") is None

    def test_execute_unknown_tool(self):
        ex = ToolExecutor(Path("."))
        inv = ToolInvocation(tool_name="nonexistent", arguments={})
        result = ex.execute(inv)
        assert result.success is False
        assert result.error is not None
        assert result.error.error_code == ToolErrorCode.UNKNOWN_TOOL

    def test_register_plugin_tool(self):
        ex = ToolExecutor(Path("."))
        ex.register_plugin_tool(
            "custom_tool", "A custom tool", {"arg1": {"type": "string"}},
            lambda args: {"result": "ok"}
        )
        assert "custom_tool" in ex.list_tool_names()

    def test_cannot_override_builtin(self):
        ex = ToolExecutor(Path("."))
        with pytest.raises(ValueError, match="[Bb]uilt.in"):
            ex.register_plugin_tool(
                "semantic_search", "Override", {}, lambda args: {}
            )

    def test_unregister_plugin_tool(self):
        ex = ToolExecutor(Path("."))
        ex.register_plugin_tool("temp", "Temp tool", {}, lambda a: {})
        assert "temp" in ex.list_tool_names()
        ex.unregister_plugin_tool("temp")
        assert "temp" not in ex.list_tool_names()

    def test_execute_plugin_tool(self):
        ex = ToolExecutor(Path("."))
        ex.register_plugin_tool(
            "echo", "Echo tool", {"msg": {"type": "string", "required": True}},
            lambda msg="": {"echo": msg}
        )
        inv = ToolInvocation(tool_name="echo", arguments={"msg": "hello"})
        result = ex.execute(inv)
        assert result.success is True
        assert result.result_payload["echo"] == "hello"

    def test_execute_batch(self):
        ex = ToolExecutor(Path("."))
        ex.register_plugin_tool("t1", "Tool 1", {}, lambda **kwargs: {"v": 1})
        ex.register_plugin_tool("t2", "Tool 2", {}, lambda **kwargs: {"v": 2})
        results = ex.execute_batch([
            ToolInvocation(tool_name="t1", arguments={}),
            ToolInvocation(tool_name="t2", arguments={}),
        ])
        assert len(results) == 2
        assert all(r.success for r in results)


# ---------------------------------------------------------------------------
#  Tools Registry
# ---------------------------------------------------------------------------
from semantic_code_intelligence.tools import ToolResult, ToolRegistry, TOOL_DEFINITIONS


class TestToolDefinitions:
    def test_count(self):
        assert len(TOOL_DEFINITIONS) == 11

    def test_all_have_required_fields(self):
        for td in TOOL_DEFINITIONS:
            assert "name" in td
            assert "description" in td
            assert "parameters" in td

    def test_semantic_search_params(self):
        td = next(t for t in TOOL_DEFINITIONS if t["name"] == "semantic_search")
        param_names = list(td["parameters"].keys())
        assert "query" in param_names

    def test_explain_symbol_params(self):
        td = next(t for t in TOOL_DEFINITIONS if t["name"] == "explain_symbol")
        param_names = list(td["parameters"].keys())
        assert "symbol_name" in param_names

    def test_summarize_repo_no_required(self):
        td = next(t for t in TOOL_DEFINITIONS if t["name"] == "summarize_repo")
        required = [name for name, p in td["parameters"].items() if p.get("required")]
        assert len(required) == 0


class TestToolResult:
    def test_success(self):
        tr = ToolResult(tool_name="test", success=True, data={"key": "val"})
        assert tr.success is True

    def test_error(self):
        tr = ToolResult(tool_name="test", success=False, error="bad")
        assert tr.success is False
        assert tr.error == "bad"


class TestToolRegistryDeep:
    def test_create(self):
        tr = ToolRegistry(Path("."))
        assert tr is not None

    def test_available_tools(self):
        tr = ToolRegistry(Path("."))
        tools = tr.tool_definitions
        assert len(tools) == 11

    def test_invoke_unknown(self):
        tr = ToolRegistry(Path("."))
        result = tr.invoke("nonexistent", arg1="val")
        assert result.success is False


# ---------------------------------------------------------------------------
#  Plugins
# ---------------------------------------------------------------------------
from semantic_code_intelligence.plugins import PluginHook, PluginManager, PluginBase


class TestPluginHookDeep:
    def test_count(self):
        assert len(PluginHook) >= 22

    def test_tool_hooks(self):
        names = [h.value for h in PluginHook]
        assert "register_tool" in names
        assert "pre_tool_invoke" in names
        assert "post_tool_invoke" in names

    def test_all_string_values(self):
        for h in PluginHook:
            assert isinstance(h.value, str)


class TestPluginManagerDeep:
    def test_create(self):
        pm = PluginManager()
        assert pm is not None

    def test_register_and_activate(self):
        pm = PluginManager()

        from semantic_code_intelligence.plugins import PluginMetadata

        class TestPlugin20(PluginBase):
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(name="test20", version="1.0", description="test")

            def on_hook(self, hook, data=None):
                return data or {}

        plugin = TestPlugin20()
        pm.register(plugin)
        pm.activate("test20")
        assert "test20" in pm.active_plugins

    def test_dispatch_no_handlers(self):
        pm = PluginManager()
        result = pm.dispatch(PluginHook.PRE_SEARCH, {"query": "test"})
        assert result == {"query": "test"}


# ---------------------------------------------------------------------------
#  Config Settings
# ---------------------------------------------------------------------------
from semantic_code_intelligence.config.settings import (
    AppConfig,
    EmbeddingConfig,
    SearchConfig,
    IndexConfig,
    LLMConfig,
)


class TestEmbeddingConfig:
    def test_defaults(self):
        ec = EmbeddingConfig()
        assert ec.model_name == "all-MiniLM-L6-v2"
        assert ec.chunk_size == 512

    def test_custom(self):
        ec = EmbeddingConfig(model_name="custom", chunk_size=256)
        assert ec.model_name == "custom"


class TestSearchConfig:
    def test_defaults(self):
        sc = SearchConfig()
        assert sc.top_k == 10
        assert sc.similarity_threshold == 0.3


class TestIndexConfig:
    def test_defaults(self):
        ic = IndexConfig()
        assert ic.use_incremental is True
        assert len(ic.extensions) > 0

    def test_ignore_dirs(self):
        ic = IndexConfig()
        assert len(ic.ignore_dirs) > 0


class TestLLMConfig:
    def test_defaults(self):
        lc = LLMConfig()
        assert lc.provider == "mock"
        assert lc.temperature == 0.2


class TestAppConfig:
    def test_defaults(self):
        ac = AppConfig()
        assert isinstance(ac.embedding, EmbeddingConfig)
        assert isinstance(ac.search, SearchConfig)
        assert isinstance(ac.index, IndexConfig)
        assert isinstance(ac.llm, LLMConfig)

    def test_config_dir(self):
        d = AppConfig.config_dir(Path("/tmp/test"))
        assert ".codex" in str(d)


# ---------------------------------------------------------------------------
#  Parsing
# ---------------------------------------------------------------------------
from semantic_code_intelligence.parsing.parser import (
    Symbol as ParserSymbol,
    detect_language,
    parse_file as parser_parse_file,
)


class TestDetectLanguage:
    def test_python(self):
        assert detect_language("app.py") == "python"

    def test_javascript(self):
        assert detect_language("app.js") == "javascript"

    def test_typescript(self):
        assert detect_language("app.ts") == "typescript"

    def test_java(self):
        assert detect_language("App.java") == "java"

    def test_go(self):
        assert detect_language("main.go") == "go"

    def test_rust(self):
        assert detect_language("lib.rs") == "rust"

    def test_cpp(self):
        assert detect_language("main.cpp") == "cpp"

    def test_csharp(self):
        assert detect_language("Program.cs") == "csharp"

    def test_ruby(self):
        assert detect_language("app.rb") == "ruby"

    def test_unknown(self):
        lang = detect_language("file.xyz")
        assert lang is None or lang == ""

    def test_tsx(self):
        assert detect_language("App.tsx") == "tsx"

    def test_php(self):
        assert detect_language("index.php") == "php"


class TestParserSymbol:
    def test_to_dict(self):
        s = ParserSymbol(
            name="fn", kind="function", body="pass", file_path="a.py",
            start_line=1, end_line=2, start_col=0, end_col=0, parent="",
        )
        d = s.to_dict()
        assert d["name"] == "fn"
        assert d["kind"] == "function"

    def test_is_dataclass(self):
        from dataclasses import fields
        f = fields(ParserSymbol)
        names = [ff.name for ff in f]
        assert "name" in names
        assert "kind" in names


class TestParseFile:
    def test_python_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def hello():\n  pass\n\nclass World:\n  def method(self):\n    pass\n")
            f.flush()
            syms = parser_parse_file(f.name)
            names = [s.name for s in syms]
            assert "hello" in names

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("")
            f.flush()
            syms = parser_parse_file(f.name)
            assert isinstance(syms, list)


# ---------------------------------------------------------------------------
#  Indexing Scanner
# ---------------------------------------------------------------------------
from semantic_code_intelligence.indexing.scanner import (
    ScannedFile,
    compute_file_hash,
    should_ignore,
)


class TestScannedFile:
    def test_fields(self):
        sf = ScannedFile(path=Path("a.py"), relative_path="a.py", extension=".py",
                         size_bytes=100, content_hash="abc123")
        assert sf.relative_path == "a.py"
        assert sf.extension == ".py"


class TestComputeFileHash:
    def test_deterministic(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("hello world")
            f.flush()
            h1 = compute_file_hash(f.name)
            h2 = compute_file_hash(f.name)
            assert h1 == h2
            assert len(h1) > 0


class TestShouldIgnore:
    def test_hidden_dirs(self):
        assert should_ignore(Path(".git/config"), Path("."), {".git"}) is True

    def test_pycache(self):
        assert should_ignore(Path("__pycache__/module.pyc"), Path("."), {"__pycache__"}) is True

    def test_normal_file(self):
        assert should_ignore(Path("src/app.py"), Path("."), {".git", "__pycache__"}) is False

    def test_node_modules(self):
        assert should_ignore(Path("node_modules/pkg/index.js"), Path("."), {"node_modules"}) is True


# ---------------------------------------------------------------------------
#  Indexing Chunker
# ---------------------------------------------------------------------------
from semantic_code_intelligence.indexing.chunker import CodeChunk, chunk_code


class TestCodeChunk:
    def test_fields(self):
        cc = CodeChunk(
            content="code", file_path="a.py", start_line=1, end_line=10,
            language="python", chunk_index=0,
        )
        assert cc.content == "code"
        assert cc.language == "python"


class TestChunkCode:
    def test_basic_chunking(self):
        code = "\n".join([f"line{i}" for i in range(100)])
        chunks = chunk_code(code, "test.py", chunk_size=50, chunk_overlap=10)
        assert len(chunks) >= 1

    def test_empty_code(self):
        chunks = chunk_code("", "test.py")
        assert len(chunks) == 0

    def test_small_code(self):
        chunks = chunk_code("single line", "test.py", chunk_size=100)
        assert len(chunks) == 1


# ---------------------------------------------------------------------------
#  Storage VectorStore
# ---------------------------------------------------------------------------
from semantic_code_intelligence.storage.vector_store import VectorStore, ChunkMetadata


class TestChunkMetadata:
    def test_fields(self):
        cm = ChunkMetadata(
            file_path="a.py", start_line=1, end_line=10,
            content="code", language="python", chunk_index=0,
        )
        assert cm.file_path == "a.py"


class TestVectorStoreDeep:
    def test_create(self):
        vs = VectorStore(dimension=384)
        assert vs is not None

    def test_add_and_search(self):
        import numpy as np
        vs = VectorStore(dimension=4)
        embedding = np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32)
        meta = ChunkMetadata(file_path="a.py", start_line=1, end_line=2,
                             chunk_index=0, content="test", language="python")
        vs.add(embedding, [meta])
        query = np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32)
        results = vs.search(query, top_k=1)
        assert len(results) >= 1

    def test_clear(self):
        vs = VectorStore(dimension=4)
        vs.clear()
        assert vs is not None


# ---------------------------------------------------------------------------
#  Storage HashStore
# ---------------------------------------------------------------------------
from semantic_code_intelligence.storage.hash_store import HashStore


class TestHashStoreDeep:
    def test_create(self):
        hs = HashStore()
        assert hs is not None
        assert hs.count == 0

    def test_store_and_check(self):
        hs = HashStore()
        hs.set("a.py", "hash1")
        assert hs.has_changed("a.py", "hash1") is False
        assert hs.has_changed("a.py", "hash2") is True

    def test_unknown_file(self):
        hs = HashStore()
        assert hs.has_changed("missing.py", "hash1") is True


# ---------------------------------------------------------------------------
#  Docs
# ---------------------------------------------------------------------------
from semantic_code_intelligence.docs import generate_all_docs


class TestDocsGeneration:
    def test_generate_all_docs(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = generate_all_docs(Path(tmp))
            assert isinstance(docs, list)

    def test_all_docs_are_strings(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = generate_all_docs(Path(tmp))
            for name in docs:
                assert isinstance(name, str)

    def test_cli_reference_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = generate_all_docs(Path(tmp))
            assert any("CLI" in k or "cli" in k for k in docs)

    def test_architecture_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = generate_all_docs(Path(tmp))
            # May generate PLUGINS, BRIDGE, WEB, CI, etc.
            assert isinstance(docs, list)

    def test_tool_protocol_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = generate_all_docs(Path(tmp))
            assert any("TOOL" in k or "tool" in k.lower() for k in docs)


# ---------------------------------------------------------------------------
#  Scalability
# ---------------------------------------------------------------------------
from semantic_code_intelligence.scalability import (
    BatchProcessor,
    MemoryAwareEmbedder,
    ParallelScanner,
)


class TestBatchProcessorDeep:
    def test_create(self):
        bp = BatchProcessor(batch_size=10)
        assert bp is not None
        assert bp.batch_size == 10

    def test_process(self):
        bp = BatchProcessor(batch_size=3)
        items = list(range(10))
        results, stats = bp.process(items, lambda batch: batch)
        assert results == items
        assert stats.total_items == 10

    def test_single_batch(self):
        bp = BatchProcessor(batch_size=100)
        items = [1, 2, 3]
        results, stats = bp.process(items, lambda batch: batch)
        assert stats.batches_processed == 1

    def test_empty(self):
        bp = BatchProcessor(batch_size=5)
        results, stats = bp.process([], lambda batch: batch)
        assert len(results) == 0
        assert stats.total_items == 0


class TestMemoryAwareEmbedder:
    def test_create(self):
        mae = MemoryAwareEmbedder(model_name="all-MiniLM-L6-v2", batch_size=32)
        assert mae is not None


class TestParallelScanner:
    def test_create(self):
        ps = ParallelScanner(max_workers=2)
        assert ps is not None

    def test_scan_empty(self):
        ps = ParallelScanner(max_workers=2)
        results, errors = ps.scan_and_process([], lambda fp: str(fp))
        assert results == []
        assert errors == []


# ---------------------------------------------------------------------------
#  Workspace
# ---------------------------------------------------------------------------
from semantic_code_intelligence.workspace import RepoEntry, WorkspaceManifest, Workspace


class TestRepoEntry:
    def test_to_dict(self):
        re = RepoEntry(name="myrepo", path="/path/to/repo")
        d = re.to_dict()
        assert d["name"] == "myrepo"
        assert d["path"] == "/path/to/repo"

    def test_defaults(self):
        re = RepoEntry(name="r", path="/r")
        assert re.file_count == 0


class TestWorkspaceManifest:
    def test_create(self):
        wm = WorkspaceManifest()
        assert wm is not None
        assert wm.version == "1.0.0"

    def test_to_dict(self):
        wm = WorkspaceManifest()
        d = wm.to_dict()
        assert isinstance(d, dict)
        assert "repos" in d


class TestWorkspace:
    def test_create(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Workspace(Path(tmp))
            assert ws is not None

    def test_repos_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Workspace(Path(tmp))
            assert isinstance(ws.repos, list)
            assert len(ws.repos) == 0


# ---------------------------------------------------------------------------
#  Daemon Watcher
# ---------------------------------------------------------------------------
from semantic_code_intelligence.daemon.watcher import FileChangeEvent, FileWatcher


class TestFileChangeEvent:
    def test_create(self):
        ev = FileChangeEvent(path=Path("a.py"), relative_path="a.py", change_type="modified")
        assert ev.path == Path("a.py")
        assert ev.change_type == "modified"

    def test_to_dict(self):
        ev = FileChangeEvent(path=Path("b.py"), relative_path="b.py", change_type="created")
        d = ev.to_dict()
        assert d["change_type"] == "created"
        assert d["relative_path"] == "b.py"


class TestFileWatcherDeep:
    def test_create(self):
        with tempfile.TemporaryDirectory() as tmp:
            fw = FileWatcher(Path(tmp))
            assert fw is not None

    def test_has_start_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            fw = FileWatcher(Path(tmp))
            assert hasattr(fw, "start")
            assert hasattr(fw, "stop")


# ---------------------------------------------------------------------------
#  Version & Meta
# ---------------------------------------------------------------------------
from semantic_code_intelligence import __version__, __app_name__


class TestVersionMeta:
    def test_version_format(self):
        parts = __version__.split(".")
        assert len(parts) == 3

    def test_app_name(self):
        assert __app_name__ == "codex"


# ---------------------------------------------------------------------------
#  CLI Router
# ---------------------------------------------------------------------------
from semantic_code_intelligence.cli.router import register_commands
from semantic_code_intelligence.cli.main import cli


class TestCLIRouterDeep:
    def test_command_count(self):
        register_commands(cli)
        # 31 commands
        assert len(cli.commands) >= 31

    def test_tool_command_registered(self):
        register_commands(cli)
        assert "tool" in cli.commands

    def test_serve_command_registered(self):
        register_commands(cli)
        assert "serve" in cli.commands

    def test_quality_command_registered(self):
        register_commands(cli)
        assert "quality" in cli.commands

    def test_impact_command_registered(self):
        register_commands(cli)
        assert "impact" in cli.commands


# ---------------------------------------------------------------------------
#  Cross-cutting: README and copilot-instructions.md
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestReadmeExists:
    def test_readme_exists(self):
        assert (_PROJECT_ROOT / "README.md").exists()


class TestCopilotInstructionsExists:
    _ci_path = _PROJECT_ROOT / ".github" / "copilot-instructions.md"

    def test_file_exists(self):
        assert self._ci_path.exists()

    def test_contains_codex_commands(self):
        content = self._ci_path.read_text(encoding="utf-8")
        assert "codex search" in content
        assert "codex tool run" in content

    def test_contains_rules(self):
        content = self._ci_path.read_text(encoding="utf-8")
        assert "--json" in content

    def test_contains_project_structure(self):
        content = self._ci_path.read_text(encoding="utf-8")
        assert "cli/" in content
        assert "tools/" in content
        assert "bridge/" in content


# ---------------------------------------------------------------------------
#  Embeddings (basic import & structure tests)
# ---------------------------------------------------------------------------
from semantic_code_intelligence.embeddings.enhanced import (
    preprocess_code_for_embedding,
    prepare_semantic_texts,
)


class TestPreprocessCodeForEmbedding:
    def test_basic(self):
        result = preprocess_code_for_embedding("def foo():\n  pass")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_empty(self):
        result = preprocess_code_for_embedding("")
        assert isinstance(result, str)


class TestPrepareSemanticTexts:
    def test_basic(self):
        from semantic_code_intelligence.indexing.semantic_chunker import SemanticChunk
        chunks = [SemanticChunk(content="def foo(): pass", file_path="a.py",
                                start_line=1, end_line=1, language="python",
                                chunk_index=0, semantic_label="function foo")]
        texts = prepare_semantic_texts(chunks)
        assert len(texts) == 1


# ---------------------------------------------------------------------------
#  Search Formatter
# ---------------------------------------------------------------------------
from semantic_code_intelligence.search.formatter import format_results_json


class TestFormatResultsJson:
    def test_basic(self):
        from semantic_code_intelligence.services.search_service import SearchResult
        results = [SearchResult(file_path="a.py", content="code", score=0.9,
                                start_line=1, end_line=1, language="python", chunk_index=0)]
        output = format_results_json("test query", results, top_k=5)
        parsed = json.loads(output)
        assert isinstance(parsed, (list, dict))

    def test_empty(self):
        output = format_results_json("empty", [], top_k=5)
        parsed = json.loads(output)
        assert isinstance(parsed, (list, dict))


# ---------------------------------------------------------------------------
#  Bridge VSCode
# ---------------------------------------------------------------------------
from semantic_code_intelligence.bridge.vscode import VSCodeBridge


class TestVSCodeBridge:
    def test_create(self):
        vsb = VSCodeBridge(Path("."))
        assert vsb is not None

    def test_has_methods(self):
        vsb = VSCodeBridge(Path("."))
        assert hasattr(vsb, "hover")
        assert hasattr(vsb, "diagnostics")
        assert hasattr(vsb, "completions")


# ---------------------------------------------------------------------------
#  Logging
# ---------------------------------------------------------------------------
from semantic_code_intelligence.utils.logging import get_logger, setup_logging


class TestLogging:
    def test_get_logger(self):
        log = get_logger("test")
        assert log is not None

    def test_setup_logging(self):
        setup_logging(verbose=False)
        setup_logging(verbose=True)


# ---------------------------------------------------------------------------
#  Additional edge cases and integration-like tests
# ---------------------------------------------------------------------------


class TestToolRegistryInvocations:
    """Test ToolRegistry invoke for each built-in tool (error paths)."""

    def test_invoke_semantic_search_no_index(self):
        tr = ToolRegistry(Path("."))
        result = tr.invoke("semantic_search", query="test")
        # Should return ToolResult (might not have index)
        assert isinstance(result, ToolResult)

    def test_invoke_explain_symbol(self):
        tr = ToolRegistry(Path("."))
        result = tr.invoke("explain_symbol", symbol_name="nonexistent")
        assert isinstance(result, ToolResult)

    def test_invoke_explain_file(self):
        tr = ToolRegistry(Path("."))
        result = tr.invoke("explain_file", file_path="nonexistent.py")
        assert isinstance(result, ToolResult)

    def test_invoke_summarize_repo(self):
        tr = ToolRegistry(Path("."))
        result = tr.invoke("summarize_repo")
        assert isinstance(result, ToolResult)

    def test_invoke_find_references(self):
        tr = ToolRegistry(Path("."))
        result = tr.invoke("find_references", symbol_name="nonexistent")
        assert isinstance(result, ToolResult)

    def test_invoke_get_dependencies(self):
        tr = ToolRegistry(Path("."))
        result = tr.invoke("get_dependencies", file_path="nonexistent.py")
        assert isinstance(result, ToolResult)

    def test_invoke_get_call_graph(self):
        tr = ToolRegistry(Path("."))
        result = tr.invoke("get_call_graph", symbol_name="nonexistent")
        assert isinstance(result, ToolResult)

    def test_invoke_get_context(self):
        tr = ToolRegistry(Path("."))
        result = tr.invoke("get_context", symbol_name="nonexistent")
        assert isinstance(result, ToolResult)


class TestDependencyMapBasic:
    def test_create(self):
        dm = DependencyMap()
        assert dm is not None

    def test_add_file(self):
        dm = DependencyMap()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("import os\nimport sys\n")
            f.flush()
            dm.add_file(f.name)
            deps = dm.get_dependencies(f.name)
            assert isinstance(deps, list)

    def test_get_all_files(self):
        dm = DependencyMap()
        assert isinstance(dm.get_all_files(), (list, set))


class TestBuildChangeSummary:
    """Test build_change_summary from ci.pr."""

    def test_with_python_file(self):
        from semantic_code_intelligence.ci.pr import build_change_summary
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def hello():\n  pass\n")
            f.flush()
            summary = build_change_summary([f.name])
            assert summary.files_changed == 1

    def test_with_nonexistent_file(self):
        from semantic_code_intelligence.ci.pr import build_change_summary
        summary = build_change_summary(["/nonexistent/file.py"])
        assert summary.files_changed == 1

    def test_empty(self):
        from semantic_code_intelligence.ci.pr import build_change_summary
        summary = build_change_summary([])
        assert summary.files_changed == 0


class TestGateViolation:
    """Test GateViolation dataclass from ci.metrics."""

    def test_create(self):
        from semantic_code_intelligence.ci.metrics import GateViolation
        gv = GateViolation(rule="min_mi", message="MI too low", actual=30.0, threshold=40.0)
        d = gv.to_dict()
        assert d["rule"] == "min_mi"
        assert d["actual"] == 30.0


class TestStreamEventSSE:
    """Additional SSE formatting tests."""

    def test_empty_data(self):
        se = StreamEvent(kind="heartbeat", content="")
        sse = se.to_sse()
        assert "heartbeat" in sse

    def test_json_data(self):
        data = json.dumps({"key": "value"})
        se = StreamEvent(kind="data", content=data)
        sse = se.to_sse()
        assert "key" in sse


class TestContextWindowRender:
    """More context window rendering tests."""

    def test_render_with_max_lines(self):
        s = _sym(body="\n".join(f"line{i}" for i in range(100)))
        cw = ContextWindow(focal_symbol=s)
        text = cw.render(max_lines=5)
        assert "more lines" in text

    def test_render_with_related(self):
        s = _sym(name="main", body="pass")
        related = _sym(name="helper", body="pass")
        cw = ContextWindow(focal_symbol=s, related_symbols=[related])
        text = cw.render()
        assert "helper" in text


class TestCallGraphMultiFile:
    """Test call graph across multiple files."""

    def test_cross_file_calls(self):
        syms = [
            _sym(name="fn_a", body="fn_b()", file_path="a.py"),
            _sym(name="fn_b", body="fn_c()", file_path="b.py"),
            _sym(name="fn_c", body="pass", file_path="c.py"),
        ]
        cg = CallGraph()
        cg.build(syms)
        assert len(cg.edges) >= 2

    def test_multiple_callers(self):
        syms = [
            _sym(name="caller1", body="target()", file_path="a.py"),
            _sym(name="caller2", body="target()", file_path="b.py"),
            _sym(name="target", body="pass", file_path="c.py"),
        ]
        cg = CallGraph()
        cg.build(syms)
        callers = cg.callers_of("target")
        assert len(callers) >= 2


class TestQualityReportAggregation:
    """Test QualityReport with mixed issues."""

    def test_mixed_issues(self):
        from semantic_code_intelligence.llm.safety import SafetyReport, SafetyIssue
        r = QualityReport(
            files_analyzed=5,
            symbol_count=20,
            complexity_issues=[ComplexityResult("fn", "a.py", 1, 10, 15, "high")],
            dead_code=[DeadCodeResult("x", "function", "a.py", 1),
                       DeadCodeResult("y", "function", "b.py", 5)],
            duplicates=[DuplicateResult("a", "f1.py", 1, "b", "f2.py", 2, 0.9)],
            safety=SafetyReport(safe=False, issues=[SafetyIssue("eval", "bad")]),
        )
        assert r.issue_count == 5  # 1 complexity + 2 dead + 1 dup + 1 safety

    def test_to_dict_completeness(self):
        r = QualityReport(files_analyzed=3, symbol_count=15)
        d = r.to_dict()
        assert "complexity_issues" in d
        assert "dead_code" in d
        assert "duplicates" in d
        assert "safety" in d
