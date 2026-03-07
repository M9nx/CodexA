"""Tests for the AST-aware semantic chunker."""

from __future__ import annotations

from pathlib import Path

import pytest

from semantic_code_intelligence.indexing.semantic_chunker import (
    SemanticChunk,
    _build_semantic_label,
    _extract_uncovered_blocks,
    _symbols_to_chunks,
    semantic_chunk_code,
    semantic_chunk_file,
)


SAMPLE_PYTHON = """\
import os
import sys

def hello(name):
    \"\"\"Say hello.\"\"\"
    return f"Hello, {name}!"

class Greeter:
    def __init__(self, prefix):
        self.prefix = prefix

    def greet(self, name):
        return f"{self.prefix} {name}"

x = 42
"""

SAMPLE_JS = """\
const fs = require('fs');

function add(a, b) {
    return a + b;
}

class Calculator {
    constructor() {
        this.result = 0;
    }
    add(value) {
        this.result += value;
    }
}
"""


# ---------------------------------------------------------------------------
# SemanticChunk dataclass
# ---------------------------------------------------------------------------

class TestSemanticChunk:
    def test_creation(self):
        sc = SemanticChunk(
            file_path="test.py",
            content="def foo(): pass",
            start_line=1,
            end_line=1,
            chunk_index=0,
            language="python",
            symbol_name="foo",
            symbol_kind="function",
        )
        assert sc.symbol_name == "foo"
        assert sc.symbol_kind == "function"

    def test_to_dict(self):
        sc = SemanticChunk(
            file_path="test.py",
            content="class Bar: pass",
            start_line=1,
            end_line=1,
            chunk_index=0,
            language="python",
            symbol_name="Bar",
            symbol_kind="class",
            parameters=["x", "y"],
        )
        d = sc.to_dict()
        assert d["symbol_name"] == "Bar"
        assert d["symbol_kind"] == "class"
        assert d["parameters"] == ["x", "y"]

    def test_defaults(self):
        sc = SemanticChunk(
            file_path="t.py", content="x=1", start_line=1,
            end_line=1, chunk_index=0, language="python",
        )
        assert sc.symbol_name == ""
        assert sc.parent_symbol == ""
        assert sc.parameters == []


# ---------------------------------------------------------------------------
# Semantic label builder
# ---------------------------------------------------------------------------

class TestBuildSemanticLabel:
    def test_function(self):
        sc = SemanticChunk(
            file_path="t.py", content="", start_line=1, end_line=1,
            chunk_index=0, language="python",
            symbol_name="foo", symbol_kind="function", parameters=["x"],
        )
        label = _build_semantic_label(sc)
        assert "[python]" in label
        assert "function" in label
        assert "foo" in label
        assert "(x)" in label

    def test_method_with_parent(self):
        sc = SemanticChunk(
            file_path="t.py", content="", start_line=1, end_line=1,
            chunk_index=0, language="python",
            symbol_name="greet", symbol_kind="method",
            parent_symbol="Greeter",
        )
        label = _build_semantic_label(sc)
        assert "Greeter.greet" in label

    def test_empty_kind(self):
        sc = SemanticChunk(
            file_path="t.py", content="x=1", start_line=1, end_line=1,
            chunk_index=0, language="python",
        )
        label = _build_semantic_label(sc)
        assert "[python]" in label


# ---------------------------------------------------------------------------
# Uncovered blocks extraction
# ---------------------------------------------------------------------------

class TestExtractUncoveredBlocks:
    def test_all_covered(self):
        lines = ["a\n", "b\n", "c\n"]
        covered = {1, 2, 3}
        assert _extract_uncovered_blocks(lines, covered) == []

    def test_none_covered(self):
        lines = ["a\n", "b\n"]
        blocks = _extract_uncovered_blocks(lines, set())
        assert len(blocks) == 1
        assert blocks[0][0] == 1  # start_line
        assert blocks[0][1] == 2  # end_line

    def test_gap_in_middle(self):
        lines = ["a\n", "b\n", "c\n", "d\n", "e\n"]
        covered = {1, 2, 5}
        blocks = _extract_uncovered_blocks(lines, covered)
        assert len(blocks) == 1
        assert blocks[0][0] == 3
        assert blocks[0][1] == 4

    def test_multiple_gaps(self):
        lines = [f"line{i}\n" for i in range(1, 8)]
        covered = {2, 5}
        blocks = _extract_uncovered_blocks(lines, covered)
        assert len(blocks) == 3  # lines 1, 3-4, 6-7


# ---------------------------------------------------------------------------
# semantic_chunk_code
# ---------------------------------------------------------------------------

class TestSemanticChunkCode:
    def test_empty_content(self):
        result = semantic_chunk_code("", "test.py")
        assert result == []

    def test_whitespace_only(self):
        result = semantic_chunk_code("   \n  ", "test.py")
        assert result == []

    def test_python_produces_chunks(self):
        chunks = semantic_chunk_code(SAMPLE_PYTHON, "test.py")
        assert len(chunks) > 0
        assert all(isinstance(c, SemanticChunk) for c in chunks)

    def test_python_has_function_chunks(self):
        chunks = semantic_chunk_code(SAMPLE_PYTHON, "test.py")
        func_chunks = [c for c in chunks if c.symbol_kind == "function"]
        assert len(func_chunks) >= 1
        names = [c.symbol_name for c in func_chunks]
        assert "hello" in names

    def test_python_has_class_chunks(self):
        chunks = semantic_chunk_code(SAMPLE_PYTHON, "test.py")
        class_chunks = [c for c in chunks if c.symbol_kind == "class"]
        assert len(class_chunks) >= 1
        assert any(c.symbol_name == "Greeter" for c in class_chunks)

    def test_javascript_produces_chunks(self):
        chunks = semantic_chunk_code(SAMPLE_JS, "test.js")
        assert len(chunks) > 0

    def test_unsupported_language_fallback(self):
        code = "some random code\nanother line\n"
        chunks = semantic_chunk_code(code, "test.xyz")
        assert len(chunks) >= 1
        # Fallback chunks are "block" kind
        assert all(c.symbol_kind == "block" for c in chunks)

    def test_chunk_indices_sequential(self):
        chunks = semantic_chunk_code(SAMPLE_PYTHON, "test.py")
        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks)))

    def test_chunks_have_content(self):
        chunks = semantic_chunk_code(SAMPLE_PYTHON, "test.py")
        for c in chunks:
            assert c.content.strip() != ""

    def test_large_function_gets_split(self):
        # Generate a big function
        big_body = "\n".join(f"    x{i} = {i}" for i in range(100))
        code = f"def big_func():\n{big_body}\n"
        chunks = semantic_chunk_code(code, "big.py", chunk_size=200)
        func_chunks = [c for c in chunks if c.symbol_name == "big_func"]
        assert len(func_chunks) > 1

    def test_semantic_labels_populated(self):
        chunks = semantic_chunk_code(SAMPLE_PYTHON, "test.py")
        labeled = [c for c in chunks if c.semantic_label]
        assert len(labeled) > 0


# ---------------------------------------------------------------------------
# semantic_chunk_file
# ---------------------------------------------------------------------------

class TestSemanticChunkFile:
    def test_existing_file(self, tmp_path):
        f = tmp_path / "sample.py"
        f.write_text(SAMPLE_PYTHON, encoding="utf-8")
        chunks = semantic_chunk_file(f)
        assert len(chunks) > 0

    def test_nonexistent_file(self, tmp_path):
        f = tmp_path / "nope.py"
        chunks = semantic_chunk_file(f)
        assert chunks == []

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.py"
        f.write_text("", encoding="utf-8")
        chunks = semantic_chunk_file(f)
        assert chunks == []
