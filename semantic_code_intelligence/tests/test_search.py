"""Tests for the search service and formatter."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from semantic_code_intelligence.config.settings import init_project, save_config, AppConfig
from semantic_code_intelligence.embeddings.generator import generate_embeddings
from semantic_code_intelligence.services.search_service import SearchResult, search_codebase
from semantic_code_intelligence.search.formatter import format_results_json, format_results_rich
from semantic_code_intelligence.storage.vector_store import ChunkMetadata, VectorStore


@pytest.fixture
def indexed_project(tmp_path: Path) -> Path:
    """Create a project with some indexed code chunks."""
    config, _ = init_project(tmp_path)
    index_dir = AppConfig.index_dir(tmp_path)

    # Create code chunks and embed them
    code_snippets = [
        "def authenticate_user(username, password):\n    return check_credentials(username, password)\n",
        "def connect_to_database(host, port):\n    return Database(host=host, port=port)\n",
        "def handle_http_request(request):\n    response = process(request)\n    return response\n",
        "def verify_jwt_token(token):\n    payload = jwt.decode(token, SECRET_KEY)\n    return payload\n",
        "def calculate_statistics(data):\n    mean = sum(data) / len(data)\n    return mean\n",
    ]

    embeddings = generate_embeddings(code_snippets)
    metadata = [
        ChunkMetadata(
            file_path=f"src/module_{i}.py",
            start_line=1,
            end_line=3,
            chunk_index=0,
            language="python",
            content=snippet,
            content_hash=f"hash_{i}",
        )
        for i, snippet in enumerate(code_snippets)
    ]

    store = VectorStore(embeddings.shape[1])
    store.add(embeddings, metadata)
    store.save(index_dir)

    return tmp_path


class TestSearchCodebase:
    """Tests for the search_codebase function."""

    def test_search_returns_results(self, indexed_project: Path):
        results = search_codebase("authentication", indexed_project)
        assert len(results) > 0

    def test_search_result_type(self, indexed_project: Path):
        results = search_codebase("database connection", indexed_project)
        assert all(isinstance(r, SearchResult) for r in results)

    def test_search_results_have_scores(self, indexed_project: Path):
        results = search_codebase("jwt token verification", indexed_project)
        for r in results:
            assert isinstance(r.score, float)
            assert r.score > 0

    def test_search_results_sorted_by_score(self, indexed_project: Path):
        results = search_codebase("authenticate user", indexed_project)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_search_respects_top_k(self, indexed_project: Path):
        results = search_codebase("code", indexed_project, top_k=2)
        assert len(results) <= 2

    def test_search_relevance(self, indexed_project: Path):
        results = search_codebase("jwt token", indexed_project, top_k=1)
        assert len(results) == 1
        assert "jwt" in results[0].content.lower() or "token" in results[0].content.lower()

    def test_search_no_index_raises(self, tmp_path: Path):
        init_project(tmp_path)
        with pytest.raises(FileNotFoundError):
            search_codebase("test", tmp_path)

    def test_search_result_metadata(self, indexed_project: Path):
        results = search_codebase("database", indexed_project, top_k=1)
        r = results[0]
        assert r.file_path.startswith("src/")
        assert r.start_line > 0
        assert r.end_line >= r.start_line
        assert r.language == "python"
        assert len(r.content) > 0


class TestSearchResult:
    """Tests for SearchResult data class."""

    def test_to_dict(self):
        r = SearchResult(
            file_path="test.py",
            start_line=1,
            end_line=5,
            language="python",
            content="def foo(): pass",
            score=0.9534,
            chunk_index=0,
        )
        d = r.to_dict()
        assert d["file_path"] == "test.py"
        assert d["score"] == 0.9534
        assert d["start_line"] == 1
        assert d["language"] == "python"

    def test_to_dict_score_rounding(self):
        r = SearchResult(
            file_path="x.py", start_line=1, end_line=1,
            language="python", content="x", score=0.12345678, chunk_index=0,
        )
        assert r.to_dict()["score"] == 0.1235


class TestFormatResultsJson:
    """Tests for JSON formatter."""

    def test_valid_json(self):
        results = [
            SearchResult("a.py", 1, 5, "python", "code", 0.95, 0),
            SearchResult("b.py", 10, 20, "python", "more code", 0.80, 1),
        ]
        output = format_results_json("test query", results, 10)
        data = json.loads(output)
        assert data["query"] == "test query"
        assert data["top_k"] == 10
        assert data["result_count"] == 2
        assert len(data["results"]) == 2

    def test_empty_results(self):
        output = format_results_json("nope", [], 5)
        data = json.loads(output)
        assert data["result_count"] == 0
        assert data["results"] == []


class TestFormatResultsRich:
    """Tests for rich formatter (smoke tests — output to console)."""

    def test_no_crash_with_results(self):
        results = [
            SearchResult("test.py", 1, 3, "python", "def hello(): pass", 0.9, 0),
        ]
        # Should not raise
        format_results_rich("hello", results)

    def test_no_crash_empty_results(self):
        format_results_rich("nothing", [])
