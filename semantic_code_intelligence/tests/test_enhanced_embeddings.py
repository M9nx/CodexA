"""Tests for the enhanced embedding pipeline."""

from __future__ import annotations

import pytest

from semantic_code_intelligence.embeddings.enhanced import (
    preprocess_code_for_embedding,
    prepare_semantic_texts,
)
from semantic_code_intelligence.indexing.semantic_chunker import SemanticChunk


# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------

class TestPreprocessCodeForEmbedding:
    def test_strips_trailing_whitespace(self):
        text = "def foo():   \n    pass   \n"
        result = preprocess_code_for_embedding(text)
        for line in result.splitlines():
            assert line == line.rstrip()

    def test_collapses_blank_lines(self):
        text = "a\n\n\n\n\nb\n"
        result = preprocess_code_for_embedding(text)
        assert "\n\n\n" not in result

    def test_prepends_semantic_label(self):
        result = preprocess_code_for_embedding("x = 1", "[python] function foo")
        assert result.startswith("[python] function foo\n")

    def test_empty_label(self):
        result = preprocess_code_for_embedding("x = 1", "")
        assert not result.startswith("\n")

    def test_empty_content(self):
        result = preprocess_code_for_embedding("")
        assert result == ""

    def test_preserves_meaningful_content(self):
        code = "def hello():\n    return 'world'"
        result = preprocess_code_for_embedding(code)
        assert "def hello():" in result
        assert "return 'world'" in result


# ---------------------------------------------------------------------------
# Batch preparation
# ---------------------------------------------------------------------------

class TestPrepareSemanticTexts:
    def test_empty_list(self):
        assert prepare_semantic_texts([]) == []

    def test_single_chunk(self):
        chunk = SemanticChunk(
            file_path="t.py", content="def foo(): pass",
            start_line=1, end_line=1, chunk_index=0,
            language="python", symbol_name="foo",
            symbol_kind="function",
            semantic_label="[python] function foo",
        )
        texts = prepare_semantic_texts([chunk])
        assert len(texts) == 1
        assert "[python] function foo" in texts[0]

    def test_multiple_chunks(self):
        chunks = [
            SemanticChunk(
                file_path="t.py", content=f"line{i}",
                start_line=i, end_line=i, chunk_index=i,
                language="python",
            )
            for i in range(3)
        ]
        texts = prepare_semantic_texts(chunks)
        assert len(texts) == 3

    def test_preserves_content_order(self):
        chunks = [
            SemanticChunk(
                file_path="t.py", content=f"content_{i}",
                start_line=i, end_line=i, chunk_index=i,
                language="python",
            )
            for i in range(3)
        ]
        texts = prepare_semantic_texts(chunks)
        for i, text in enumerate(texts):
            assert f"content_{i}" in text
