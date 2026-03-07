"""Tests for the context engine — ContextBuilder, CallGraph, DependencyMap."""

import pytest

from semantic_code_intelligence.context.engine import (
    CallGraph,
    ContextBuilder,
    ContextWindow,
    DependencyMap,
    FileDependency,
)
from semantic_code_intelligence.parsing.parser import Symbol


# ---------------------------------------------------------------------------
# Sample code
# ---------------------------------------------------------------------------

PYTHON_SAMPLE = '''\
import os
from pathlib import Path

def helper():
    return 42

def main():
    result = helper()
    print(result)

class Worker:
    def __init__(self):
        self.data = []

    def process(self):
        result = helper()
        return result
'''

JS_SAMPLE = '''\
import { readFile } from 'fs';

function parse(data) {
    return JSON.parse(data);
}

function load(path) {
    const data = readFile(path);
    return parse(data);
}

class DataLoader {
    constructor(path) {
        this.path = path;
    }

    load() {
        return load(this.path);
    }
}
'''


# ---------------------------------------------------------------------------
# ContextBuilder
# ---------------------------------------------------------------------------

class TestContextBuilder:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.builder = ContextBuilder()
        self.builder.index_file("app.py", PYTHON_SAMPLE)

    def test_index_file_returns_symbols(self):
        symbols = self.builder.get_symbols("app.py")
        assert len(symbols) > 0

    def test_get_all_symbols(self):
        self.builder.index_file("app.js", JS_SAMPLE)
        all_syms = self.builder.get_all_symbols()
        assert len(all_syms) > 5  # should have symbols from both files

    def test_find_symbol_by_name(self):
        results = self.builder.find_symbol("helper")
        assert len(results) >= 1
        assert results[0].name == "helper"

    def test_find_symbol_by_name_and_kind(self):
        results = self.builder.find_symbol("Worker", kind="class")
        assert len(results) == 1
        assert results[0].kind == "class"

    def test_find_symbol_not_found(self):
        results = self.builder.find_symbol("nonexistent")
        assert results == []

    def test_build_context(self):
        symbols = self.builder.get_symbols("app.py")
        main_sym = next(s for s in symbols if s.name == "main")
        ctx = self.builder.build_context(main_sym)
        assert isinstance(ctx, ContextWindow)
        assert ctx.focal_symbol.name == "main"

    def test_context_has_imports(self):
        symbols = self.builder.get_symbols("app.py")
        main_sym = next(s for s in symbols if s.name == "main")
        ctx = self.builder.build_context(main_sym)
        assert len(ctx.imports) >= 2

    def test_context_has_related_symbols(self):
        symbols = self.builder.get_symbols("app.py")
        main_sym = next(s for s in symbols if s.name == "main")
        ctx = self.builder.build_context(main_sym)
        related_names = {s.name for s in ctx.related_symbols}
        assert "helper" in related_names

    def test_context_to_dict(self):
        symbols = self.builder.get_symbols("app.py")
        main_sym = next(s for s in symbols if s.name == "main")
        ctx = self.builder.build_context(main_sym)
        d = ctx.to_dict()
        assert "focal_symbol" in d
        assert "related_symbols" in d
        assert "imports" in d
        assert d["focal_symbol"]["name"] == "main"

    def test_context_render(self):
        symbols = self.builder.get_symbols("app.py")
        main_sym = next(s for s in symbols if s.name == "main")
        ctx = self.builder.build_context(main_sym)
        text = ctx.render()
        assert "main" in text
        assert "File:" in text
        assert "Lines:" in text

    def test_context_render_with_max_lines(self):
        symbols = self.builder.get_symbols("app.py")
        main_sym = next(s for s in symbols if s.name == "main")
        ctx = self.builder.build_context(main_sym)
        text = ctx.render(max_lines=1)
        assert "main" in text

    def test_build_context_for_name(self):
        contexts = self.builder.build_context_for_name("helper")
        assert len(contexts) >= 1
        assert contexts[0].focal_symbol.name == "helper"

    def test_build_context_for_name_not_found(self):
        contexts = self.builder.build_context_for_name("nonexistent")
        assert contexts == []

    def test_get_symbols_unknown_file(self):
        assert self.builder.get_symbols("unknown.py") == []

    def test_index_multiple_files(self):
        self.builder.index_file("app.js", JS_SAMPLE)
        py_symbols = self.builder.get_symbols("app.py")
        js_symbols = self.builder.get_symbols("app.js")
        assert len(py_symbols) > 0
        assert len(js_symbols) > 0


# ---------------------------------------------------------------------------
# CallGraph
# ---------------------------------------------------------------------------

class TestCallGraph:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.builder = ContextBuilder()
        self.builder.index_file("app.py", PYTHON_SAMPLE)
        self.symbols = self.builder.get_all_symbols()
        self.graph = CallGraph()
        self.graph.build(self.symbols)

    def test_edges_found(self):
        assert len(self.graph.edges) > 0

    def test_main_calls_helper(self):
        callers = self.graph.callers_of("helper")
        caller_names = {e.caller for e in callers}
        assert any("main" in c for c in caller_names)

    def test_process_calls_helper(self):
        callers = self.graph.callers_of("helper")
        caller_names = {e.caller for e in callers}
        assert any("process" in c for c in caller_names)

    def test_callees_of_main(self):
        callees = self.graph.callees_of("app.py:main")
        callee_names = {e.callee for e in callees}
        assert "helper" in callee_names

    def test_no_self_references(self):
        for edge in self.graph.edges:
            # Caller key includes file path, callee is just name
            assert edge.callee not in edge.caller or edge.callee != edge.caller.split(":")[-1]

    def test_callers_of_unknown(self):
        assert self.graph.callers_of("nonexistent") == []

    def test_callees_of_unknown(self):
        assert self.graph.callees_of("nonexistent") == []

    def test_to_dict(self):
        d = self.graph.to_dict()
        assert "edges" in d
        assert "node_count" in d
        assert "edge_count" in d
        assert d["edge_count"] == len(self.graph.edges)

    def test_build_clears_previous(self):
        """Build should reset the graph."""
        initial_count = len(self.graph.edges)
        self.graph.build([])  # rebuild with no symbols
        assert len(self.graph.edges) == 0

    def test_edge_to_dict(self):
        if self.graph.edges:
            d = self.graph.edges[0].to_dict()
            assert "caller" in d
            assert "callee" in d
            assert "file_path" in d
            assert "line" in d

    def test_js_call_graph(self):
        builder = ContextBuilder()
        builder.index_file("app.js", JS_SAMPLE)
        symbols = builder.get_all_symbols()
        graph = CallGraph()
        graph.build(symbols)
        callers = graph.callers_of("parse")
        assert any("load" in e.caller for e in callers)


# ---------------------------------------------------------------------------
# DependencyMap
# ---------------------------------------------------------------------------

class TestDependencyMap:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.dep_map = DependencyMap()

    def test_add_python_file(self):
        deps = self.dep_map.add_file("app.py", PYTHON_SAMPLE)
        assert len(deps) >= 2  # import os, from pathlib import Path

    def test_add_js_file(self):
        deps = self.dep_map.add_file("app.js", JS_SAMPLE)
        assert len(deps) >= 1

    def test_get_dependencies(self):
        self.dep_map.add_file("app.py", PYTHON_SAMPLE)
        deps = self.dep_map.get_dependencies("app.py")
        assert len(deps) >= 2

    def test_get_dependencies_unknown(self):
        assert self.dep_map.get_dependencies("unknown.py") == []

    def test_get_all_files(self):
        self.dep_map.add_file("app.py", PYTHON_SAMPLE)
        self.dep_map.add_file("app.js", JS_SAMPLE)
        files = self.dep_map.get_all_files()
        assert "app.py" in files
        assert "app.js" in files

    def test_get_dependents(self):
        self.dep_map.add_file("app.py", PYTHON_SAMPLE)
        dependents = self.dep_map.get_dependents("os")
        assert len(dependents) >= 1
        assert dependents[0].source_file == "app.py"

    def test_get_dependents_pathlib(self):
        self.dep_map.add_file("app.py", PYTHON_SAMPLE)
        dependents = self.dep_map.get_dependents("pathlib")
        assert len(dependents) >= 1

    def test_get_dependents_not_found(self):
        self.dep_map.add_file("app.py", PYTHON_SAMPLE)
        assert self.dep_map.get_dependents("nonexistent_module") == []

    def test_dependency_to_dict(self):
        deps = self.dep_map.add_file("app.py", PYTHON_SAMPLE)
        if deps:
            d = deps[0].to_dict()
            assert "source_file" in d
            assert "import_text" in d
            assert "line" in d

    def test_to_dict(self):
        self.dep_map.add_file("app.py", PYTHON_SAMPLE)
        d = self.dep_map.to_dict()
        assert "app.py" in d
        assert isinstance(d["app.py"], list)

    def test_dependency_line_numbers(self):
        deps = self.dep_map.add_file("app.py", PYTHON_SAMPLE)
        lines = [d.line for d in deps]
        assert 1 in lines  # 'import os' is line 1
        assert 2 in lines  # 'from pathlib...' is line 2


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestContextEdgeCases:
    def test_builder_nonexistent_file(self, tmp_path):
        builder = ContextBuilder()
        syms = builder.index_file(str(tmp_path / "nope.py"))
        assert syms == []

    def test_builder_empty_content(self):
        builder = ContextBuilder()
        syms = builder.index_file("empty.py", "")
        assert syms == []

    def test_builder_unsupported_extension(self):
        builder = ContextBuilder()
        syms = builder.index_file("style.css", "body { color: red; }")
        assert syms == []

    def test_call_graph_empty(self):
        graph = CallGraph()
        graph.build([])
        assert graph.edges == []

    def test_dep_map_empty_file(self):
        dep_map = DependencyMap()
        deps = dep_map.add_file("empty.py", "")
        assert deps == []

    def test_dep_map_unsupported_extension(self):
        dep_map = DependencyMap()
        deps = dep_map.add_file("style.css", "body { color: red; }")
        assert deps == []


# ---------------------------------------------------------------------------
# Integration: builder -> call graph -> dependency map
# ---------------------------------------------------------------------------

class TestContextIntegration:
    def test_full_pipeline(self):
        builder = ContextBuilder()
        builder.index_file("app.py", PYTHON_SAMPLE)
        builder.index_file("app.js", JS_SAMPLE)

        # Build call graph from all symbols
        all_symbols = builder.get_all_symbols()
        graph = CallGraph()
        graph.build(all_symbols)
        assert len(graph.edges) > 0

        # Build dependency map
        dep_map = DependencyMap()
        dep_map.add_file("app.py", PYTHON_SAMPLE)
        dep_map.add_file("app.js", JS_SAMPLE)
        assert len(dep_map.get_all_files()) == 2

        # Build context for a symbol
        helpers = builder.find_symbol("helper")
        assert len(helpers) >= 1
        ctx = builder.build_context(helpers[0])
        assert ctx.focal_symbol.name == "helper"
        assert len(ctx.imports) >= 2

    def test_cross_file_symbol_search(self):
        builder = ContextBuilder()
        builder.index_file("app.py", PYTHON_SAMPLE)
        builder.index_file("app.js", JS_SAMPLE)

        # "parse" exists in the JS file
        results = builder.find_symbol("parse")
        assert len(results) >= 1
        assert any(r.file_path == "app.js" for r in results)

        # "helper" exists in the Python file
        results = builder.find_symbol("helper")
        assert len(results) >= 1
        assert any(r.file_path == "app.py" for r in results)
