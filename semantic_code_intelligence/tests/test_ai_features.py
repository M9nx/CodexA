"""Tests for AI features — repository summary, AI context, code explanations."""

import json

import pytest

from semantic_code_intelligence.analysis.ai_features import (
    CodeExplanation,
    LanguageStats,
    RepoSummary,
    explain_file,
    explain_symbol,
    generate_ai_context,
    summarize_repository,
)
from semantic_code_intelligence.context.engine import ContextBuilder


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
# RepoSummary
# ---------------------------------------------------------------------------

class TestRepoSummary:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.builder = ContextBuilder()
        self.builder.index_file("app.py", PYTHON_SAMPLE)
        self.builder.index_file("app.js", JS_SAMPLE)
        self.summary = summarize_repository(self.builder)

    def test_total_files(self):
        assert self.summary.total_files == 2

    def test_total_symbols(self):
        assert self.summary.total_symbols > 0

    def test_total_functions(self):
        assert self.summary.total_functions >= 2  # helper, main, parse, load

    def test_total_classes(self):
        assert self.summary.total_classes >= 2  # Worker, DataLoader

    def test_total_methods(self):
        assert self.summary.total_methods >= 2

    def test_total_imports(self):
        assert self.summary.total_imports >= 2

    def test_languages_listed(self):
        lang_names = {l.language for l in self.summary.languages}
        assert "python" in lang_names
        assert "javascript" in lang_names

    def test_top_functions(self):
        assert len(self.summary.top_functions) > 0
        assert "name" in self.summary.top_functions[0]

    def test_top_classes(self):
        assert len(self.summary.top_classes) > 0
        assert "name" in self.summary.top_classes[0]

    def test_to_dict(self):
        d = self.summary.to_dict()
        assert "total_files" in d
        assert "languages" in d
        assert "top_functions" in d

    def test_to_json(self):
        j = self.summary.to_json()
        parsed = json.loads(j)
        assert parsed["total_files"] == 2

    def test_render(self):
        text = self.summary.render()
        assert "Repository Summary" in text
        assert "Files:" in text
        assert "Languages" in text


class TestLanguageStats:
    def test_to_dict(self):
        stats = LanguageStats(
            language="python",
            file_count=5,
            function_count=10,
            class_count=3,
        )
        d = stats.to_dict()
        assert d["language"] == "python"
        assert d["file_count"] == 5
        assert d["function_count"] == 10
        assert d["class_count"] == 3


class TestRepoSummaryEmpty:
    def test_empty_builder(self):
        builder = ContextBuilder()
        summary = summarize_repository(builder)
        assert summary.total_files == 0
        assert summary.total_symbols == 0
        assert summary.languages == []

    def test_single_file(self):
        builder = ContextBuilder()
        builder.index_file("app.py", PYTHON_SAMPLE)
        summary = summarize_repository(builder)
        assert summary.total_files == 1
        lang_names = {l.language for l in summary.languages}
        assert "python" in lang_names


# ---------------------------------------------------------------------------
# AI Context Generation
# ---------------------------------------------------------------------------

class TestGenerateAIContext:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.builder = ContextBuilder()
        self.builder.index_file("app.py", PYTHON_SAMPLE)
        self.builder.index_file("app.js", JS_SAMPLE)

    def test_basic_context(self):
        ctx = generate_ai_context(self.builder)
        assert "summary" in ctx
        assert "call_graph" in ctx
        assert "dependencies" in ctx

    def test_context_with_symbol_focus(self):
        ctx = generate_ai_context(self.builder, symbol_name="helper")
        assert "focused_contexts" in ctx
        assert len(ctx["focused_contexts"]) >= 1

    def test_context_with_file_focus(self):
        ctx = generate_ai_context(self.builder, file_path="app.py")
        assert "file_symbols" in ctx
        assert len(ctx["file_symbols"]) > 0

    def test_context_without_call_graph(self):
        ctx = generate_ai_context(self.builder, include_call_graph=False)
        assert "call_graph" not in ctx

    def test_context_without_dependencies(self):
        ctx = generate_ai_context(self.builder, include_dependencies=False)
        assert "dependencies" not in ctx

    def test_context_is_json_serializable(self):
        ctx = generate_ai_context(self.builder)
        j = json.dumps(ctx)
        assert len(j) > 0

    def test_call_graph_has_edges(self):
        ctx = generate_ai_context(self.builder)
        assert ctx["call_graph"]["edge_count"] > 0

    def test_dependencies_has_files(self):
        ctx = generate_ai_context(self.builder)
        assert "app.py" in ctx["dependencies"]


# ---------------------------------------------------------------------------
# Code Explanation
# ---------------------------------------------------------------------------

class TestExplainSymbol:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.builder = ContextBuilder()
        self.builder.index_file("app.py", PYTHON_SAMPLE)
        self.symbols = self.builder.get_all_symbols()

    def test_explain_function(self):
        func = next(s for s in self.symbols if s.name == "helper")
        explanation = explain_symbol(func)
        assert explanation.symbol_name == "helper"
        assert explanation.symbol_kind == "function"
        assert "Function" in explanation.summary
        assert "helper" in explanation.summary

    def test_explain_class(self):
        cls = next(s for s in self.symbols if s.name == "Worker")
        explanation = explain_symbol(cls)
        assert explanation.symbol_name == "Worker"
        assert "Class" in explanation.summary

    def test_explain_method(self):
        method = next(s for s in self.symbols if s.name == "process")
        explanation = explain_symbol(method)
        assert explanation.symbol_name == "process"
        assert "Method" in explanation.summary
        assert "Worker" in explanation.summary

    def test_explain_import(self):
        imp = next(s for s in self.symbols if s.kind == "import")
        explanation = explain_symbol(imp)
        assert "Import" in explanation.summary

    def test_explain_with_builder_context(self):
        func = next(s for s in self.symbols if s.name == "main")
        explanation = explain_symbol(func, self.builder)
        assert "related_symbols" in explanation.details or "file_imports" in explanation.details

    def test_explanation_to_dict(self):
        func = next(s for s in self.symbols if s.name == "helper")
        explanation = explain_symbol(func)
        d = explanation.to_dict()
        assert "symbol_name" in d
        assert "summary" in d
        assert "details" in d

    def test_explanation_render(self):
        func = next(s for s in self.symbols if s.name == "helper")
        explanation = explain_symbol(func)
        text = explanation.render()
        assert "helper" in text
        assert "File:" in text

    def test_explanation_render_with_details(self):
        func = next(s for s in self.symbols if s.name == "main")
        explanation = explain_symbol(func, self.builder)
        text = explanation.render()
        assert "main" in text


class TestExplainFile:
    def test_explain_python_file(self):
        explanations = explain_file("app.py", PYTHON_SAMPLE)
        assert len(explanations) > 0
        # Should not include imports
        for e in explanations:
            assert e.symbol_kind != "import"

    def test_explain_js_file(self):
        explanations = explain_file("app.js", JS_SAMPLE)
        assert len(explanations) > 0

    def test_explain_empty_file(self):
        explanations = explain_file("empty.py", "")
        assert explanations == []

    def test_explain_unsupported_file(self):
        explanations = explain_file("style.css", "body { color: red; }")
        assert explanations == []

    def test_each_explanation_has_name(self):
        explanations = explain_file("app.py", PYTHON_SAMPLE)
        for e in explanations:
            assert e.symbol_name
            assert e.file_path == "app.py"


class TestCodeExplanation:
    def test_dataclass_fields(self):
        exp = CodeExplanation(
            symbol_name="foo",
            symbol_kind="function",
            file_path="test.py",
            summary="A test function.",
            details={"parameters": "a, b"},
        )
        assert exp.symbol_name == "foo"
        assert exp.details["parameters"] == "a, b"

    def test_render_empty_details(self):
        exp = CodeExplanation(
            symbol_name="foo",
            symbol_kind="function",
            file_path="test.py",
            summary="A test function.",
        )
        text = exp.render()
        assert "foo" in text
        assert "Function" in text


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestAIFeaturesEdgeCases:
    def test_summary_single_symbol(self):
        builder = ContextBuilder()
        builder.index_file("one.py", "def single(): pass\n")
        summary = summarize_repository(builder)
        assert summary.total_functions == 1
        assert summary.total_files == 1

    def test_ai_context_empty_builder(self):
        builder = ContextBuilder()
        ctx = generate_ai_context(builder)
        assert ctx["summary"]["total_files"] == 0

    def test_ai_context_nonexistent_symbol(self):
        builder = ContextBuilder()
        builder.index_file("app.py", PYTHON_SAMPLE)
        ctx = generate_ai_context(builder, symbol_name="nonexistent")
        assert ctx["focused_contexts"] == []

    def test_ai_context_nonexistent_file(self):
        builder = ContextBuilder()
        builder.index_file("app.py", PYTHON_SAMPLE)
        ctx = generate_ai_context(builder, file_path="nonexistent.py")
        assert ctx["file_symbols"] == []
