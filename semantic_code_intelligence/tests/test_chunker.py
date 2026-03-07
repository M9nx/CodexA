"""Tests for the code chunker."""

from __future__ import annotations

from pathlib import Path

import pytest

from semantic_code_intelligence.indexing.chunker import (
    CodeChunk,
    chunk_code,
    chunk_file,
    detect_language,
)


class TestDetectLanguage:
    """Tests for language detection."""

    def test_python(self):
        assert detect_language("main.py") == "python"

    def test_javascript(self):
        assert detect_language("app.js") == "javascript"

    def test_typescript(self):
        assert detect_language("component.tsx") == "typescript"

    def test_java(self):
        assert detect_language("Main.java") == "java"

    def test_unknown(self):
        assert detect_language("data.xyz") == "unknown"

    def test_path_with_directory(self):
        assert detect_language("/some/path/file.py") == "python"
        assert detect_language("C:\\code\\file.js") == "javascript"


class TestChunkCode:
    """Tests for code chunking logic."""

    def test_empty_content(self):
        chunks = chunk_code("", "test.py")
        assert chunks == []

    def test_whitespace_only(self):
        chunks = chunk_code("   \n  \n ", "test.py")
        assert chunks == []

    def test_small_file_single_chunk(self):
        code = "def hello():\n    return 'world'\n"
        chunks = chunk_code(code, "test.py", chunk_size=1000)
        assert len(chunks) == 1
        assert chunks[0].content == code
        assert chunks[0].start_line == 1
        assert chunks[0].end_line == 2
        assert chunks[0].language == "python"
        assert chunks[0].chunk_index == 0

    def test_large_file_multiple_chunks(self):
        lines = [f"line_{i} = {i}\n" for i in range(100)]
        code = "".join(lines)
        chunks = chunk_code(code, "test.py", chunk_size=200, chunk_overlap=50)
        assert len(chunks) > 1

    def test_chunks_cover_all_content(self):
        lines = [f"x_{i} = {i}\n" for i in range(50)]
        code = "".join(lines)
        chunks = chunk_code(code, "test.py", chunk_size=100, chunk_overlap=20)
        # Every line should appear in at least one chunk
        all_chunk_text = "".join(c.content for c in chunks)
        for line in lines:
            assert line in all_chunk_text

    def test_chunk_index_sequential(self):
        lines = [f"var_{i} = {i}\n" for i in range(100)]
        code = "".join(lines)
        chunks = chunk_code(code, "test.py", chunk_size=150, chunk_overlap=30)
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_chunk_metadata(self):
        code = "function hello() { return 1; }\n"
        chunks = chunk_code(code, "app.js", chunk_size=1000)
        assert chunks[0].file_path == "app.js"
        assert chunks[0].language == "javascript"

    def test_overlap_between_chunks(self):
        lines = [f"line_{i:03d} = {i}\n" for i in range(100)]
        code = "".join(lines)
        chunks = chunk_code(code, "test.py", chunk_size=200, chunk_overlap=50)
        if len(chunks) >= 2:
            # Last lines of chunk N should appear in chunk N+1
            chunk0_lines = set(chunks[0].content.splitlines())
            chunk1_lines = set(chunks[1].content.splitlines())
            overlap = chunk0_lines & chunk1_lines
            assert len(overlap) > 0


class TestChunkFile:
    """Tests for file-based chunking."""

    def test_chunk_existing_file(self, tmp_path: Path):
        f = tmp_path / "test.py"
        f.write_text("def hello():\n    pass\n", encoding="utf-8")
        chunks = chunk_file(f, chunk_size=1000)
        assert len(chunks) == 1

    def test_chunk_nonexistent_file(self, tmp_path: Path):
        f = tmp_path / "missing.py"
        chunks = chunk_file(f)
        assert chunks == []

    def test_chunk_empty_file(self, tmp_path: Path):
        f = tmp_path / "empty.py"
        f.write_text("", encoding="utf-8")
        chunks = chunk_file(f)
        assert chunks == []
