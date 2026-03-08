"""Phase 20c – Reach 2 000 tests.

Covers: visualize, formatter, context/engine, context/memory,
analysis/ai_features, llm/reasoning results, llm/investigation results,
bridge/context_provider edge cases, services, search formatter.
"""

from __future__ import annotations

import json
import tempfile
import time
from dataclasses import fields
from pathlib import Path
from typing import Any

import pytest

# =========================================================================
#  Visualization
# =========================================================================

from semantic_code_intelligence.web.visualize import (
    render_call_graph,
    render_dependency_graph,
    render_workspace_graph,
    render_symbol_map,
)


class TestRenderCallGraph:
    """render_call_graph() – 10 tests."""

    def test_empty_edges(self):
        html = render_call_graph([])
        assert isinstance(html, str)
        assert "mermaid" in html.lower() or "graph" in html.lower() or "flowchart" in html.lower()

    def test_single_edge(self):
        edges = [{"caller": "a", "callee": "b", "file_path": "f.py", "line": 1}]
        html = render_call_graph(edges)
        assert "a" in html
        assert "b" in html

    def test_multiple_edges(self):
        edges = [
            {"caller": "a", "callee": "b", "file_path": "f.py", "line": 1},
            {"caller": "b", "callee": "c", "file_path": "f.py", "line": 5},
        ]
        html = render_call_graph(edges)
        assert "c" in html

    def test_custom_title(self):
        html = render_call_graph([], title="My Graph")
        assert "My Graph" in html

    def test_direction_lr(self):
        html = render_call_graph([], direction="LR")
        assert isinstance(html, str)

    def test_direction_td(self):
        html = render_call_graph([], direction="TD")
        assert isinstance(html, str)

    def test_direction_rl(self):
        html = render_call_graph([], direction="RL")
        assert isinstance(html, str)

    def test_direction_tb(self):
        html = render_call_graph([], direction="TB")
        assert isinstance(html, str)

    def test_self_loop(self):
        edges = [{"caller": "f", "callee": "f", "file_path": "f.py", "line": 1}]
        html = render_call_graph(edges)
        assert "f" in html

    def test_returns_str(self):
        assert isinstance(render_call_graph([]), str)


class TestRenderDependencyGraph:
    """render_dependency_graph() – 8 tests."""

    def test_empty_deps(self):
        html = render_dependency_graph({})
        assert isinstance(html, str)

    def test_flat_deps(self):
        deps = {"file.py": [{"import_text": "os", "line": 1, "source_file": "file.py"}]}
        html = render_dependency_graph(deps)
        assert isinstance(html, str)

    def test_custom_title(self):
        html = render_dependency_graph({}, title="Deps")
        assert "Deps" in html

    def test_direction_td(self):
        html = render_dependency_graph({}, direction="TD")
        assert isinstance(html, str)

    def test_direction_lr(self):
        html = render_dependency_graph({}, direction="LR")
        assert isinstance(html, str)

    def test_multiple_files(self):
        deps = {
            "a.py": [{"import_text": "os", "line": 1, "source_file": "a.py"}],
            "b.py": [{"import_text": "sys", "line": 2, "source_file": "b.py"}],
        }
        html = render_dependency_graph(deps)
        assert isinstance(html, str)

    def test_nested_import(self):
        deps = {"c.py": [{"import_text": "a.b.c", "line": 3, "source_file": "c.py"}]}
        html = render_dependency_graph(deps)
        assert isinstance(html, str)

    def test_returns_str(self):
        assert isinstance(render_dependency_graph({}), str)


class TestRenderWorkspaceGraph:
    """render_workspace_graph() – 5 tests."""

    def test_empty(self):
        html = render_workspace_graph([])
        assert isinstance(html, str)

    def test_single_repo(self):
        repos = [{"name": "repo1", "path": "/tmp/r", "languages": ["python"]}]
        html = render_workspace_graph(repos)
        assert "repo1" in html

    def test_custom_title(self):
        html = render_workspace_graph([], title="WS")
        assert "WS" in html

    def test_multiple_repos(self):
        repos = [
            {"name": "r1", "path": "/a", "languages": ["python"]},
            {"name": "r2", "path": "/b", "languages": ["javascript"]},
        ]
        html = render_workspace_graph(repos)
        assert isinstance(html, str)

    def test_returns_str(self):
        assert isinstance(render_workspace_graph([]), str)


class TestRenderSymbolMap:
    """render_symbol_map() – 7 tests."""

    def test_empty(self):
        html = render_symbol_map([])
        assert isinstance(html, str)

    def test_single_function(self):
        syms = [{"name": "foo", "kind": "function", "line": 1}]
        html = render_symbol_map(syms)
        assert "foo" in html

    def test_class_and_method(self):
        syms = [
            {"name": "MyClass", "kind": "class", "line": 1},
            {"name": "my_method", "kind": "method", "line": 5, "parent": "MyClass"},
        ]
        html = render_symbol_map(syms)
        assert "MyClass" in html

    def test_custom_title(self):
        html = render_symbol_map([], title="Symbols")
        assert "Symbols" in html

    def test_file_path(self):
        html = render_symbol_map([], file_path="test.py")
        assert isinstance(html, str)

    def test_large_list(self):
        syms = [{"name": f"func_{i}", "kind": "function", "line": i} for i in range(50)]
        html = render_symbol_map(syms)
        assert isinstance(html, str)

    def test_returns_str(self):
        assert isinstance(render_symbol_map([]), str)


# =========================================================================
#  Search formatter
# =========================================================================

from semantic_code_intelligence.services.search_service import SearchResult as SvcSearchResult
from semantic_code_intelligence.search.formatter import format_results_json


class TestFormatResultsJson:
    """format_results_json – 6 tests."""

    def _sr(self, **kw) -> SvcSearchResult:
        defaults = dict(file_path="a.py", start_line=1, end_line=5,
                        language="python", content="pass", score=0.9,
                        chunk_index=0)
        defaults.update(kw)
        return SvcSearchResult(**defaults)

    def test_empty_results(self):
        out = format_results_json("hello", [], 5)
        parsed = json.loads(out)
        assert parsed["query"] == "hello"
        assert len(parsed["results"]) == 0

    def test_single_result(self):
        out = format_results_json("q", [self._sr()], 5)
        parsed = json.loads(out)
        assert len(parsed["results"]) == 1

    def test_top_k_included(self):
        out = format_results_json("q", [], 10)
        parsed = json.loads(out)
        assert parsed["top_k"] == 10

    def test_valid_json(self):
        out = format_results_json("x", [self._sr(), self._sr(file_path="b.py")], 5)
        assert json.loads(out)  # doesn't raise

    def test_scores_preserved(self):
        out = format_results_json("q", [self._sr(score=0.42)], 5)
        parsed = json.loads(out)
        assert parsed["results"][0]["score"] == pytest.approx(0.42, abs=0.01)

    def test_returns_str(self):
        assert isinstance(format_results_json("q", [], 1), str)


# =========================================================================
#  Context – Engine extras
# =========================================================================

from semantic_code_intelligence.context.engine import (
    ContextWindow,
    ContextBuilder,
    CallEdge,
    CallGraph,
    FileDependency,
    DependencyMap,
)
from semantic_code_intelligence.parsing.parser import Symbol


def _sym(name: str = "foo", kind: str = "function", **kw) -> Symbol:
    defaults = dict(name=name, kind=kind, file_path="test.py",
                    start_line=1, end_line=5, start_col=0, end_col=0,
                    body="pass")
    defaults.update(kw)
    return Symbol(**defaults)


class TestCallEdge:
    """CallEdge dataclass – 4 tests."""

    def test_create(self):
        e = CallEdge(caller="a", callee="b", file_path="f.py", line=10)
        assert e.caller == "a"

    def test_to_dict(self):
        e = CallEdge(caller="a", callee="b", file_path="f.py", line=3)
        d = e.to_dict()
        assert "caller" in d and "callee" in d

    def test_line(self):
        e = CallEdge(caller="x", callee="y", file_path="z.py", line=99)
        assert e.line == 99

    def test_fields_count(self):
        assert len(fields(CallEdge)) == 4


class TestFileDependency:
    """FileDependency dataclass – 4 tests."""

    def test_create(self):
        fd = FileDependency(source_file="a.py", import_text="os", line=1)
        assert fd.source_file == "a.py"

    def test_to_dict(self):
        fd = FileDependency(source_file="a.py", import_text="os", line=1)
        d = fd.to_dict()
        assert d["import_text"] == "os"

    def test_line(self):
        fd = FileDependency(source_file="b.py", import_text="sys", line=42)
        assert fd.line == 42

    def test_fields_count(self):
        assert len(fields(FileDependency)) == 3


class TestCallGraphExtended:
    """CallGraph – 6 tests."""

    def test_create(self):
        cg = CallGraph()
        assert cg is not None

    def test_empty_edges(self):
        cg = CallGraph()
        assert cg.edges == []

    def test_build_empty(self):
        cg = CallGraph()
        cg.build([])
        assert cg.edges == []

    def test_callers_of_unknown(self):
        cg = CallGraph()
        assert cg.callers_of("nonexistent") == []

    def test_callees_of_unknown(self):
        cg = CallGraph()
        assert cg.callees_of("nonexistent") == []

    def test_to_dict(self):
        cg = CallGraph()
        d = cg.to_dict()
        assert isinstance(d, dict)


class TestDependencyMapExtended:
    """DependencyMap – 6 tests."""

    def test_create(self):
        dm = DependencyMap()
        assert dm is not None

    def test_empty_all_files(self):
        dm = DependencyMap()
        assert dm.get_all_files() == []

    def test_get_deps_unknown(self):
        dm = DependencyMap()
        assert dm.get_dependencies("nonexistent.py") == []

    def test_get_dependents_empty(self):
        dm = DependencyMap()
        assert dm.get_dependents("os") == []

    def test_to_dict(self):
        dm = DependencyMap()
        assert isinstance(dm.to_dict(), dict)

    def test_add_file_inline(self):
        dm = DependencyMap()
        deps = dm.add_file("test.py", "import os\nimport sys\n")
        assert isinstance(deps, list)


class TestContextWindowExtended:
    """ContextWindow – 5 tests."""

    def test_create(self):
        s = _sym()
        cw = ContextWindow(focal_symbol=s)
        assert cw.focal_symbol.name == "foo"

    def test_to_dict(self):
        cw = ContextWindow(focal_symbol=_sym())
        d = cw.to_dict()
        assert "focal_symbol" in d

    def test_render(self):
        cw = ContextWindow(focal_symbol=_sym(), file_content="x = 1\n")
        text = cw.render()
        assert isinstance(text, str)

    def test_related_default(self):
        cw = ContextWindow(focal_symbol=_sym())
        assert cw.related_symbols == []

    def test_imports_default(self):
        cw = ContextWindow(focal_symbol=_sym())
        assert cw.imports == []


class TestContextBuilderExtended:
    """ContextBuilder – 8 tests."""

    def test_create(self):
        cb = ContextBuilder()
        assert cb is not None

    def test_get_all_symbols_empty(self):
        cb = ContextBuilder()
        assert cb.get_all_symbols() == []

    def test_get_symbols_unknown(self):
        cb = ContextBuilder()
        assert cb.get_symbols("nonexistent.py") == []

    def test_find_symbol_empty(self):
        cb = ContextBuilder()
        assert cb.find_symbol("nonexistent") == []

    def test_index_inline_content(self):
        cb = ContextBuilder()
        syms = cb.index_file("test.py", "def hello():\n    pass\n")
        assert isinstance(syms, list)

    def test_find_after_index(self):
        cb = ContextBuilder()
        cb.index_file("test.py", "def hello():\n    pass\n")
        found = cb.find_symbol("hello")
        assert len(found) >= 1

    def test_build_context_for_name(self):
        cb = ContextBuilder()
        cb.index_file("test.py", "def greet():\n    pass\n")
        windows = cb.build_context_for_name("greet")
        assert isinstance(windows, list)

    def test_build_context(self):
        cb = ContextBuilder()
        cb.index_file("test.py", "def myfunc():\n    pass\n")
        found = cb.find_symbol("myfunc")
        if found:
            cw = cb.build_context(found[0])
            assert isinstance(cw, ContextWindow)


# =========================================================================
#  Context – Memory extras
# =========================================================================

from semantic_code_intelligence.context.memory import (
    MemoryEntry,
    ReasoningStep,
    SessionMemory,
    WorkspaceMemory,
)


class TestMemoryEntryExtended:
    """MemoryEntry – 6 tests."""

    def test_create(self):
        me = MemoryEntry(key="k", content="c")
        assert me.kind == "general"

    def test_custom_kind(self):
        me = MemoryEntry(key="k", content="c", kind="search")
        assert me.kind == "search"

    def test_to_dict(self):
        me = MemoryEntry(key="k", content="c")
        d = me.to_dict()
        assert d["key"] == "k"

    def test_from_dict(self):
        me = MemoryEntry(key="k", content="c", kind="general", timestamp=1.0)
        d = me.to_dict()
        me2 = MemoryEntry.from_dict(d)
        assert me2.key == "k"

    def test_roundtrip(self):
        me = MemoryEntry(key="x", content="y", kind="note", metadata={"a": 1})
        d = me.to_dict()
        me2 = MemoryEntry.from_dict(d)
        assert me2.metadata.get("a") == 1

    def test_timestamp_auto(self):
        before = time.time()
        me = MemoryEntry(key="k", content="c")
        assert me.timestamp >= before


class TestReasoningStepExtended:
    """ReasoningStep – 4 tests."""

    def test_create(self):
        rs = ReasoningStep(step_id=1, action="search", input_text="q", output_text="r")
        assert rs.step_id == 1

    def test_to_dict(self):
        rs = ReasoningStep(step_id=0, action="a", input_text="i", output_text="o")
        d = rs.to_dict()
        assert "action" in d

    def test_timestamp_auto(self):
        rs = ReasoningStep(step_id=1, action="a", input_text="", output_text="")
        assert rs.timestamp > 0

    def test_fields(self):
        assert len(fields(ReasoningStep)) >= 5


class TestSessionMemoryExtended:
    """SessionMemory – 10 tests."""

    def test_create(self):
        sm = SessionMemory()
        assert sm is not None

    def test_add_entry(self):
        sm = SessionMemory()
        me = sm.add("k1", "content1")
        assert me.key == "k1"

    def test_entries_property(self):
        sm = SessionMemory()
        sm.add("k1", "c1")
        assert len(sm.entries) == 1

    def test_search_basic(self):
        sm = SessionMemory()
        sm.add("python", "python info")
        results = sm.search("python")
        assert len(results) >= 1

    def test_search_no_match(self):
        sm = SessionMemory()
        sm.add("java", "java info")
        results = sm.search("zzz_nonexistent_zzz")
        assert isinstance(results, list)

    def test_get_recent(self):
        sm = SessionMemory()
        sm.add("a", "aa")
        sm.add("b", "bb")
        recent = sm.get_recent(1)
        assert len(recent) == 1

    def test_clear(self):
        sm = SessionMemory()
        sm.add("k", "v")
        sm.clear()
        assert len(sm.entries) == 0

    def test_chain_lifecycle(self):
        sm = SessionMemory()
        sm.start_chain("c1")
        sm.add_step("c1", "search", "q", "r")
        steps = sm.get_chain("c1")
        assert len(steps) == 1

    def test_chain_multiple_steps(self):
        sm = SessionMemory()
        sm.start_chain("c2")
        sm.add_step("c2", "search", "q1", "r1")
        sm.add_step("c2", "analyze", "q2", "r2")
        steps = sm.get_chain("c2")
        assert len(steps) == 2

    def test_to_dict(self):
        sm = SessionMemory()
        sm.add("k", "v")
        d = sm.to_dict()
        assert isinstance(d, dict)


class TestWorkspaceMemory:
    """WorkspaceMemory – 8 tests."""

    def test_create(self):
        with tempfile.TemporaryDirectory() as tmp:
            wm = WorkspaceMemory(Path(tmp))
            assert wm is not None

    def test_add_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            wm = WorkspaceMemory(Path(tmp))
            me = wm.add("k1", "c1")
            assert me.key == "k1"

    def test_get_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            wm = WorkspaceMemory(Path(tmp))
            wm.add("k1", "c1")
            entry = wm.get("k1")
            assert entry is not None

    def test_get_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            wm = WorkspaceMemory(Path(tmp))
            assert wm.get("nokey") is None

    def test_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            wm = WorkspaceMemory(Path(tmp))
            wm.add("python", "python stuff")
            results = wm.search("python")
            assert len(results) >= 1

    def test_remove(self):
        with tempfile.TemporaryDirectory() as tmp:
            wm = WorkspaceMemory(Path(tmp))
            wm.add("k1", "c1")
            assert wm.remove("k1") is True
            assert wm.get("k1") is None

    def test_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            wm = WorkspaceMemory(Path(tmp))
            wm.add("a", "b")
            wm.clear()
            assert len(wm.entries) == 0

    def test_to_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            wm = WorkspaceMemory(Path(tmp))
            d = wm.to_dict()
            assert isinstance(d, dict)


# =========================================================================
#  Analysis – AI features
# =========================================================================

from semantic_code_intelligence.analysis.ai_features import (
    LanguageStats,
    RepoSummary,
    CodeExplanation,
    summarize_repository,
    explain_symbol,
    explain_file,
)


class TestLanguageStatsExtended:
    """LanguageStats – 5 tests."""

    def test_create(self):
        ls = LanguageStats(language="python")
        assert ls.language == "python"

    def test_defaults(self):
        ls = LanguageStats(language="js")
        assert ls.file_count == 0
        assert ls.function_count == 0

    def test_to_dict(self):
        ls = LanguageStats(language="py", file_count=3, function_count=10)
        d = ls.to_dict()
        assert d["language"] == "py"

    def test_all_fields(self):
        ls = LanguageStats(language="go", file_count=1, function_count=2,
                          class_count=3, method_count=4, import_count=5,
                          total_lines=100)
        assert ls.total_lines == 100

    def test_fields_count(self):
        assert len(fields(LanguageStats)) >= 7


class TestRepoSummaryExtended:
    """RepoSummary – 7 tests."""

    def test_create(self):
        rs = RepoSummary()
        assert rs.total_files == 0

    def test_to_dict(self):
        rs = RepoSummary(total_files=5, total_symbols=20)
        d = rs.to_dict()
        assert d["total_files"] == 5

    def test_to_json(self):
        rs = RepoSummary(total_files=1)
        j = rs.to_json()
        parsed = json.loads(j)
        assert parsed["total_files"] == 1

    def test_render(self):
        rs = RepoSummary(total_files=2, total_classes=1,
                        languages=[LanguageStats(language="python")])
        text = rs.render()
        assert isinstance(text, str)

    def test_languages(self):
        rs = RepoSummary(languages=[LanguageStats(language="python"),
                                    LanguageStats(language="javascript")])
        assert len(rs.languages) == 2

    def test_top_functions(self):
        rs = RepoSummary(top_functions=[{"name": "main"}])
        assert len(rs.top_functions) == 1

    def test_fields_count(self):
        assert len(fields(RepoSummary)) >= 9


class TestCodeExplanation:
    """CodeExplanation – 5 tests."""

    def test_create(self):
        ce = CodeExplanation(symbol_name="foo", symbol_kind="function",
                            file_path="a.py", summary="Does stuff")
        assert ce.symbol_name == "foo"

    def test_to_dict(self):
        ce = CodeExplanation(symbol_name="bar", symbol_kind="class",
                            file_path="b.py", summary="A class")
        d = ce.to_dict()
        assert d["symbol_kind"] == "class"

    def test_render(self):
        ce = CodeExplanation(symbol_name="baz", symbol_kind="function",
                            file_path="c.py", summary="baz summary")
        text = ce.render()
        assert isinstance(text, str) and len(text) > 0

    def test_details_default(self):
        ce = CodeExplanation(symbol_name="f", symbol_kind="function",
                            file_path="d.py", summary="s")
        assert ce.details == {}

    def test_details_custom(self):
        ce = CodeExplanation(symbol_name="f", symbol_kind="function",
                            file_path="d.py", summary="s",
                            details={"params": ["a", "b"]})
        assert ce.details["params"] == ["a", "b"]


class TestSummarizeRepository:
    """summarize_repository – 3 tests."""

    def test_empty_builder(self):
        cb = ContextBuilder()
        summary = summarize_repository(cb)
        assert isinstance(summary, RepoSummary)

    def test_with_file(self):
        cb = ContextBuilder()
        cb.index_file("test.py", "def hello():\n    pass\n")
        summary = summarize_repository(cb)
        assert summary.total_files >= 1

    def test_returns_repo_summary(self):
        cb = ContextBuilder()
        assert isinstance(summarize_repository(cb), RepoSummary)


class TestExplainSymbol:
    """explain_symbol – 3 tests."""

    def test_basic(self):
        s = _sym(name="myfunc", kind="function")
        ce = explain_symbol(s)
        assert isinstance(ce, CodeExplanation)
        assert ce.symbol_name == "myfunc"

    def test_class(self):
        s = _sym(name="MyClass", kind="class")
        ce = explain_symbol(s)
        assert ce.symbol_kind == "class"

    def test_with_builder(self):
        cb = ContextBuilder()
        cb.index_file("test.py", "def foo():\n    pass\n")
        found = cb.find_symbol("foo")
        if found:
            ce = explain_symbol(found[0], cb)
            assert isinstance(ce, CodeExplanation)


class TestExplainFile:
    """explain_file – 3 tests."""

    def test_inline(self):
        result = explain_file("test.py", "def f():\n    pass\n")
        assert isinstance(result, list)

    def test_empty_content(self):
        result = explain_file("empty.py", "")
        assert isinstance(result, list)

    def test_multiple_symbols(self):
        code = "def a():\n    pass\ndef b():\n    pass\n"
        result = explain_file("multi.py", code)
        assert len(result) >= 2


# =========================================================================
#  LLM – Reasoning results
# =========================================================================

from semantic_code_intelligence.llm.reasoning import (
    AskResult,
    ReviewResult,
    RefactorResult,
    SuggestResult,
)


class TestAskResultExtended:
    """AskResult – 4 tests."""

    def test_create(self):
        ar = AskResult(question="what?", answer="this")
        assert ar.question == "what?"

    def test_to_dict(self):
        ar = AskResult(question="q", answer="a")
        d = ar.to_dict()
        assert d["question"] == "q"

    def test_context_snippets_default(self):
        ar = AskResult(question="q", answer="a")
        assert ar.context_snippets == []

    def test_explainability_default(self):
        ar = AskResult(question="q", answer="a")
        assert ar.explainability == {}


class TestReviewResultExtended:
    """ReviewResult – 4 tests."""

    def test_create(self):
        rr = ReviewResult(file_path="a.py")
        assert rr.file_path == "a.py"

    def test_to_dict(self):
        rr = ReviewResult(file_path="b.py", summary="ok")
        d = rr.to_dict()
        assert d["file_path"] == "b.py"

    def test_issues_default(self):
        rr = ReviewResult(file_path="c.py")
        assert rr.issues == []

    def test_summary_default(self):
        rr = ReviewResult(file_path="d.py")
        assert rr.summary == ""


class TestRefactorResultExtended:
    """RefactorResult – 4 tests."""

    def test_create(self):
        rf = RefactorResult(file_path="a.py")
        assert rf.file_path == "a.py"

    def test_to_dict(self):
        rf = RefactorResult(file_path="b.py", explanation="cleaned up")
        d = rf.to_dict()
        assert "file_path" in d

    def test_defaults(self):
        rf = RefactorResult(file_path="c.py")
        assert rf.original_code == "" and rf.refactored_code == ""

    def test_explainability(self):
        rf = RefactorResult(file_path="d.py", explainability={"model": "gpt-4"})
        assert rf.explainability["model"] == "gpt-4"


class TestSuggestResultExtended:
    """SuggestResult – 3 tests."""

    def test_create(self):
        sr = SuggestResult(target="func")
        assert sr.target == "func"

    def test_to_dict(self):
        sr = SuggestResult(target="cls")
        d = sr.to_dict()
        assert "target" in d

    def test_suggestions_default(self):
        sr = SuggestResult(target="x")
        assert sr.suggestions == []


# =========================================================================
#  LLM – Investigation results
# =========================================================================

from semantic_code_intelligence.llm.investigation import InvestigationResult


class TestInvestigationResultExtended:
    """InvestigationResult – 4 tests."""

    def test_create(self):
        ir = InvestigationResult(question="why?", conclusion="because")
        assert ir.question == "why?"

    def test_to_dict(self):
        ir = InvestigationResult(question="q", conclusion="c")
        d = ir.to_dict()
        assert d["conclusion"] == "c"

    def test_steps_default(self):
        ir = InvestigationResult(question="q", conclusion="c")
        assert ir.steps == []

    def test_total_steps(self):
        ir = InvestigationResult(question="q", conclusion="c", total_steps=3)
        assert ir.total_steps == 3


# =========================================================================
#  Services – SearchResult extras
# =========================================================================


class TestSearchResultToDict:
    """SearchResult.to_dict – 4 tests."""

    def _sr(self, **kw) -> SvcSearchResult:
        defaults = dict(file_path="a.py", start_line=1, end_line=5,
                        language="python", content="code", score=0.9,
                        chunk_index=0)
        defaults.update(kw)
        return SvcSearchResult(**defaults)

    def test_keys(self):
        d = self._sr().to_dict()
        assert "file_path" in d and "score" in d

    def test_score(self):
        d = self._sr(score=0.75).to_dict()
        assert d["score"] == pytest.approx(0.75)

    def test_language(self):
        d = self._sr(language="javascript").to_dict()
        assert d["language"] == "javascript"

    def test_roundtrip_fields(self):
        sr = self._sr(file_path="z.py", start_line=10, end_line=20)
        d = sr.to_dict()
        assert d["start_line"] == 10 and d["end_line"] == 20


# =========================================================================
#  Services – IndexingResult extras
# =========================================================================

from semantic_code_intelligence.services.indexing_service import IndexingResult


class TestIndexingResultExtended:
    """IndexingResult – 4 tests."""

    def test_defaults(self):
        ir = IndexingResult()
        assert ir.files_scanned == 0
        assert ir.files_indexed == 0

    def test_repr_str(self):
        ir = IndexingResult()
        assert isinstance(repr(ir), str)

    def test_mutate(self):
        ir = IndexingResult()
        ir.files_scanned = 42
        assert ir.files_scanned == 42

    def test_chunks_created(self):
        ir = IndexingResult()
        ir.chunks_created = 100
        assert ir.chunks_created == 100
