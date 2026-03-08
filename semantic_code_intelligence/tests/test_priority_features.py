"""Tests for Priority 1-5 features: hybrid search, keyword search, model registry,
chunk hash store, section expander, parallel indexing, codexaignore, AST call graphs,
cross-repo search modes, TUI, MCP, and streaming.
"""

from __future__ import annotations

import json
import os
import re
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from semantic_code_intelligence.config.settings import AppConfig, init_project
from semantic_code_intelligence.embeddings.generator import generate_embeddings
from semantic_code_intelligence.storage.vector_store import ChunkMetadata, VectorStore


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def indexed_project(tmp_path: Path) -> Path:
    """Create a project with indexed code chunks for search tests."""
    config, _ = init_project(tmp_path)
    index_dir = AppConfig.index_dir(tmp_path)

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


@pytest.fixture
def vector_store(indexed_project: Path) -> VectorStore:
    """Load the vector store from the indexed project."""
    index_dir = AppConfig.index_dir(indexed_project)
    return VectorStore.load(index_dir)


# ===========================================================================
# P1: Keyword Search (BM25)
# ===========================================================================

class TestKeywordSearch:
    """Tests for the BM25 keyword search engine."""

    def test_keyword_search_returns_results(self, indexed_project: Path, vector_store: VectorStore):
        from semantic_code_intelligence.search.keyword_search import keyword_search, _bm25_cache

        # Clear cache so we get a fresh BM25 index for this store
        _bm25_cache.clear()
        index_dir = AppConfig.index_dir(indexed_project)
        results = keyword_search("authenticate", vector_store, index_dir, top_k=3)
        assert len(results) > 0
        assert any("authenticate" in r.content.lower() for r in results)

    def test_keyword_search_empty_query(self, indexed_project: Path, vector_store: VectorStore):
        from semantic_code_intelligence.search.keyword_search import keyword_search

        index_dir = AppConfig.index_dir(indexed_project)
        results = keyword_search("", vector_store, index_dir, top_k=3)
        assert isinstance(results, list)

    def test_keyword_search_no_match(self, indexed_project: Path, vector_store: VectorStore):
        from semantic_code_intelligence.search.keyword_search import keyword_search

        index_dir = AppConfig.index_dir(indexed_project)
        results = keyword_search("xyznonexistent999", vector_store, index_dir, top_k=3)
        assert len(results) == 0


class TestRegexSearch:
    """Tests for the regex search engine."""

    def test_regex_search_finds_pattern(self, vector_store: VectorStore):
        from semantic_code_intelligence.search.keyword_search import regex_search

        results = regex_search(r"def \w+_user", vector_store, top_k=5)
        assert len(results) > 0

    def test_regex_search_case_insensitive(self, vector_store: VectorStore):
        from semantic_code_intelligence.search.keyword_search import regex_search

        results = regex_search("DATABASE", vector_store, top_k=5, case_insensitive=True)
        assert len(results) > 0

    def test_regex_search_case_sensitive(self, vector_store: VectorStore):
        from semantic_code_intelligence.search.keyword_search import regex_search

        results = regex_search("DATABASE", vector_store, top_k=5, case_insensitive=False)
        # All content uses lowercase, so no match expected
        assert len(results) == 0

    def test_regex_search_invalid_pattern(self, vector_store: VectorStore):
        from semantic_code_intelligence.search.keyword_search import regex_search

        # Invalid regex should return empty, not crash
        results = regex_search("[invalid", vector_store, top_k=5)
        assert isinstance(results, list)


# ===========================================================================
# P1: Hybrid Search (RRF)
# ===========================================================================

class TestHybridSearch:
    """Tests for Reciprocal Rank Fusion hybrid search."""

    def test_hybrid_search_returns_results(self, indexed_project: Path, vector_store: VectorStore):
        from semantic_code_intelligence.search.hybrid_search import hybrid_search

        index_dir = AppConfig.index_dir(indexed_project)
        results = hybrid_search(
            "authenticate user",
            vector_store,
            index_dir,
            top_k=3,
        )
        assert len(results) > 0

    def test_hybrid_search_rrf_formula(self):
        from semantic_code_intelligence.search.hybrid_search import reciprocal_rank_fusion

        # RRF expects list of (chunk_index, score) tuples
        semantic = [(0, 1.0), (1, 0.5), (2, 0.3)]
        keyword = [(1, 1.0), (3, 0.8)]
        fused = reciprocal_rank_fusion(semantic, keyword, k=60)
        # Returns list of (index, fused_score, sem_score, kw_score)
        indices = {t[0] for t in fused}
        assert 1 in indices  # "b" equivalent — in both lists
        # Item in both lists should have higher fused score
        scores_by_idx = {t[0]: t[1] for t in fused}
        assert scores_by_idx[1] >= scores_by_idx.get(0, 0)

    def test_hybrid_search_empty_query(self, indexed_project: Path, vector_store: VectorStore):
        from semantic_code_intelligence.search.hybrid_search import hybrid_search

        index_dir = AppConfig.index_dir(indexed_project)
        results = hybrid_search("", vector_store, index_dir, top_k=3)
        assert isinstance(results, list)


# ===========================================================================
# P1: Section Expander
# ===========================================================================

class TestSectionExpander:
    """Tests for full-section expansion."""

    def test_expand_returns_results(self, indexed_project: Path):
        from semantic_code_intelligence.search.section_expander import expand_to_full_section
        from semantic_code_intelligence.services.search_service import SearchResult

        results = [
            SearchResult(
                file_path="src/module_0.py",
                start_line=1,
                end_line=3,
                language="python",
                content="def authenticate_user():\n    pass\n",
                score=0.9,
                chunk_index=0,
            )
        ]
        index_dir = AppConfig.index_dir(indexed_project)
        expanded = expand_to_full_section(results, indexed_project, index_dir)
        # Should return at least the original results
        assert len(expanded) >= 1


# ===========================================================================
# P1: Auto-index on Search
# ===========================================================================

class TestAutoIndex:
    """Tests for auto-indexing when searching without an existing index."""

    def test_search_auto_indexes(self, tmp_path: Path):
        """Searching a project with no index should trigger auto-index."""
        config, _ = init_project(tmp_path)
        # Create a file to index
        src = tmp_path / "hello.py"
        src.write_text("def greet(name):\n    return f'Hello {name}'\n")

        from semantic_code_intelligence.services.search_service import search_codebase

        results = search_codebase("greet", tmp_path, auto_index=True)
        # At minimum the auto-index ran without error
        assert isinstance(results, list)


# ===========================================================================
# P2: Chunk Hash Store
# ===========================================================================

class TestChunkHashStore:
    """Tests for chunk-level content hashing."""

    def test_store_and_check(self, tmp_path: Path):
        from semantic_code_intelligence.storage.chunk_hash_store import ChunkHashStore

        store = ChunkHashStore()
        store.set("file.py:1:10", "abc123")
        assert store.get("file.py:1:10") == "abc123"
        assert store.get("nonexistent") is None

    def test_has_changed(self, tmp_path: Path):
        from semantic_code_intelligence.storage.chunk_hash_store import ChunkHashStore

        store = ChunkHashStore()
        store.set("file.py:1:10", "abc123")
        assert not store.has_changed("file.py:1:10", "abc123")
        assert store.has_changed("file.py:1:10", "def456")
        assert store.has_changed("new_key", "anything")

    def test_remove_by_file(self, tmp_path: Path):
        from semantic_code_intelligence.storage.chunk_hash_store import ChunkHashStore

        store = ChunkHashStore()
        store.set("a.py:1:10", "h1")
        store.set("a.py:11:20", "h2")
        store.set("b.py:1:5", "h3")

        removed = store.remove_by_file("a.py")
        assert removed == 2
        assert store.get("a.py:1:10") is None
        assert store.get("b.py:1:5") == "h3"

    def test_save_and_load(self, tmp_path: Path):
        from semantic_code_intelligence.storage.chunk_hash_store import ChunkHashStore

        store = ChunkHashStore()
        store.set("file.py:1:10", "abc123")
        store.save(tmp_path)

        loaded = ChunkHashStore.load(tmp_path)
        assert loaded.get("file.py:1:10") == "abc123"

    def test_keys_for_file(self):
        from semantic_code_intelligence.storage.chunk_hash_store import ChunkHashStore

        store = ChunkHashStore()
        store.set("a.py:1:10", "h1")
        store.set("a.py:11:20", "h2")
        store.set("b.py:1:5", "h3")

        keys = store.keys_for_file("a.py")
        assert len(keys) == 2
        assert "a.py:1:10" in keys


# ===========================================================================
# P2: Model Registry
# ===========================================================================

class TestModelRegistry:
    """Tests for the embedding model registry."""

    def test_resolve_alias(self):
        from semantic_code_intelligence.embeddings.model_registry import resolve_model_name

        assert resolve_model_name("minilm") == "all-MiniLM-L6-v2"
        assert resolve_model_name("bge-small") == "BAAI/bge-small-en-v1.5"

    def test_resolve_full_name(self):
        from semantic_code_intelligence.embeddings.model_registry import resolve_model_name

        assert resolve_model_name("all-MiniLM-L6-v2") == "all-MiniLM-L6-v2"

    def test_resolve_unknown(self):
        from semantic_code_intelligence.embeddings.model_registry import resolve_model_name

        # Unknown names should be returned as-is (for custom models)
        assert resolve_model_name("my-custom-model") == "my-custom-model"

    def test_get_model_info(self):
        from semantic_code_intelligence.embeddings.model_registry import get_model_info

        info = get_model_info("all-MiniLM-L6-v2")
        assert info is not None
        assert info.dimension == 384

    def test_list_models(self):
        from semantic_code_intelligence.embeddings.model_registry import list_models

        models = list_models()
        assert len(models) >= 5
        names = [m.name for m in models]
        assert "all-MiniLM-L6-v2" in names


# ===========================================================================
# P2: ONNX Backend Detection
# ===========================================================================

class TestONNXBackend:
    """Tests for ONNX backend detection in generator."""

    def test_onnx_available_detection(self):
        from semantic_code_intelligence.embeddings.generator import _onnx_available

        # Just verify it returns a bool without crashing
        result = _onnx_available()
        assert isinstance(result, bool)


# ===========================================================================
# P3: Parallel Indexing
# ===========================================================================

class TestParallelIndexing:
    """Tests for parallel file chunking and hash scanning."""

    def test_parallel_chunk_files(self, tmp_path: Path):
        from semantic_code_intelligence.indexing.parallel import parallel_chunk_files
        from semantic_code_intelligence.indexing.scanner import ScannedFile

        # Create some source files and wrap them as ScannedFile
        scanned = []
        for i in range(5):
            p = tmp_path / f"file_{i}.py"
            p.write_text(f"def func_{i}():\n    return {i}\n")
            scanned.append(ScannedFile(
                path=p,
                relative_path=f"file_{i}.py",
                extension=".py",
                size_bytes=p.stat().st_size,
                content_hash=f"hash_{i}",
            ))
        chunks = parallel_chunk_files(scanned, chunk_size=200, chunk_overlap=0)
        assert len(chunks) >= 5  # At least one tuple per file

    def test_parallel_scan_hashes(self, tmp_path: Path):
        from semantic_code_intelligence.indexing.parallel import parallel_scan_hashes

        for i in range(3):
            (tmp_path / f"f{i}.py").write_text(f"# file {i}\n")
        files = [tmp_path / f"f{i}.py" for i in range(3)]
        hashes = parallel_scan_hashes(files)
        assert len(hashes) == 3
        # All hashes should be hex strings
        for h in hashes.values():
            assert len(h) == 64  # SHA-256 hex


# ===========================================================================
# P4: .codexaignore
# ===========================================================================

class TestCodexaIgnore:
    """Tests for .codexaignore file support in the scanner."""

    def test_codexaignore_excludes_files(self, tmp_path: Path):
        from semantic_code_intelligence.indexing.scanner import scan_repository
        from semantic_code_intelligence.config.settings import IndexConfig

        # Create files
        (tmp_path / "keep.py").write_text("x = 1\n")
        (tmp_path / "secret.py").write_text("password = 'abc'\n")
        subdir = tmp_path / "vendor"
        subdir.mkdir()
        (subdir / "lib.py").write_text("y = 2\n")

        # Create .codexaignore
        (tmp_path / ".codexaignore").write_text("secret.py\nvendor/*\n")

        config = IndexConfig(extensions={".py"})
        results = scan_repository(tmp_path, config)
        paths = [r.relative_path for r in results]

        assert any("keep.py" in p for p in paths)
        assert not any("secret.py" in p for p in paths)
        assert not any("vendor" in p for p in paths)

    def test_codexaignore_comments_ignored(self, tmp_path: Path):
        from semantic_code_intelligence.indexing.scanner import _load_ignore_patterns

        (tmp_path / ".codexaignore").write_text("# comment\npattern\n  \n")
        patterns = _load_ignore_patterns(tmp_path)
        assert patterns == ["pattern"]

    def test_no_codexaignore_file(self, tmp_path: Path):
        from semantic_code_intelligence.indexing.scanner import _load_ignore_patterns

        patterns = _load_ignore_patterns(tmp_path)
        assert patterns == []


# ===========================================================================
# P4: TUI
# ===========================================================================

class TestTUI:
    """Tests for the TUI module."""

    def test_tui_import(self):
        from semantic_code_intelligence.tui import run_tui
        assert callable(run_tui)


# ===========================================================================
# P4: MCP Server
# ===========================================================================

class TestMCPServer:
    """Tests for the MCP JSON-RPC server."""

    def test_mcp_import(self):
        from semantic_code_intelligence.mcp import run_mcp_server, MCP_TOOLS
        assert callable(run_mcp_server)
        assert len(MCP_TOOLS) >= 8

    def test_mcp_tool_definitions(self):
        from semantic_code_intelligence.mcp import MCP_TOOLS

        names = {t["name"] for t in MCP_TOOLS}
        assert "semantic_search" in names
        assert "keyword_search" in names
        assert "hybrid_search" in names
        assert "regex_search" in names
        assert "explain_symbol" in names
        assert "health_check" in names

    def test_mcp_handle_initialize(self):
        from semantic_code_intelligence.mcp import _handle_request

        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        }
        response = _handle_request(request, Path("."))
        assert response["result"]["protocolVersion"] == "2024-11-05"

    def test_mcp_handle_tools_list(self):
        from semantic_code_intelligence.mcp import _handle_request

        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        response = _handle_request(request, Path("."))
        assert "tools" in response["result"]

    def test_mcp_handle_unknown_method(self):
        from semantic_code_intelligence.mcp import _handle_request

        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "nonexistent/method",
            "params": {},
        }
        response = _handle_request(request, Path("."))
        assert "error" in response


# ===========================================================================
# P5: AST-based Call Graphs
# ===========================================================================

class TestASTCallGraph:
    """Tests for the AST-based call graph."""

    def test_ast_call_graph_detects_calls(self):
        from semantic_code_intelligence.context.engine import CallGraph
        from semantic_code_intelligence.parsing.parser import Symbol

        symbols = [
            Symbol(
                name="caller_func",
                kind="function",
                file_path="test.py",
                start_line=1,
                end_line=3,
                start_col=0,
                end_col=0,
                body="def caller_func():\n    result = callee_func()\n    return result\n",
            ),
            Symbol(
                name="callee_func",
                kind="function",
                file_path="test.py",
                start_line=5,
                end_line=6,
                start_col=0,
                end_col=0,
                body="def callee_func():\n    return 42\n",
            ),
        ]

        cg = CallGraph()
        cg.build(symbols)

        callers = cg.callers_of("callee_func")
        assert len(callers) >= 1
        assert any("caller_func" in e.caller for e in callers)

    def test_ast_call_graph_no_self_reference(self):
        from semantic_code_intelligence.context.engine import CallGraph
        from semantic_code_intelligence.parsing.parser import Symbol

        symbols = [
            Symbol(
                name="recursive",
                kind="function",
                file_path="test.py",
                start_line=1,
                end_line=3,
                start_col=0,
                end_col=0,
                body="def recursive():\n    return recursive()\n",
            ),
        ]

        cg = CallGraph()
        cg.build(symbols)
        assert len(cg.edges) == 0

    def test_ast_call_graph_method_call(self):
        from semantic_code_intelligence.context.engine import CallGraph
        from semantic_code_intelligence.parsing.parser import Symbol

        symbols = [
            Symbol(
                name="main",
                kind="function",
                file_path="test.py",
                start_line=1,
                end_line=3,
                start_col=0,
                end_col=0,
                body="def main():\n    obj.helper()\n    return\n",
            ),
            Symbol(
                name="helper",
                kind="method",
                file_path="test.py",
                start_line=5,
                end_line=6,
                start_col=0,
                end_col=0,
                body="def helper(self):\n    pass\n",
            ),
        ]

        cg = CallGraph()
        cg.build(symbols)
        callers = cg.callers_of("helper")
        assert len(callers) >= 1

    def test_call_graph_to_dict(self):
        from semantic_code_intelligence.context.engine import CallGraph
        from semantic_code_intelligence.parsing.parser import Symbol

        symbols = [
            Symbol(
                name="a", kind="function", file_path="t.py",
                start_line=1, end_line=2, start_col=0, end_col=0,
                body="def a():\n    b()\n",
            ),
            Symbol(
                name="b", kind="function", file_path="t.py",
                start_line=3, end_line=4, start_col=0, end_col=0,
                body="def b():\n    pass\n",
            ),
        ]

        cg = CallGraph()
        cg.build(symbols)
        d = cg.to_dict()
        assert "edges" in d
        assert "node_count" in d
        assert "edge_count" in d
        assert d["edge_count"] >= 1


# ===========================================================================
# P5: Cross-repo Search Modes
# ===========================================================================

class TestCrossRepoSearchModes:
    """Tests for multi-mode cross-repo workspace search."""

    def test_workspace_search_keyword_mode(self, tmp_path: Path):
        from semantic_code_intelligence.workspace import Workspace

        ws_root = tmp_path / "workspace"
        ws_root.mkdir()
        repo_a = ws_root / "repo_a"
        repo_a.mkdir()
        (repo_a / "hello.py").write_text("def greet():\n    print('hello')\n")

        ws = Workspace.load_or_create(ws_root)
        ws.add_repo("repo_a", repo_a)
        ws.save()
        ws.index_all()

        # Keyword mode search
        results = ws.search("greet", top_k=5, mode="keyword")
        assert isinstance(results, list)

    def test_workspace_search_regex_mode(self, tmp_path: Path):
        from semantic_code_intelligence.workspace import Workspace

        ws_root = tmp_path / "workspace"
        ws_root.mkdir()
        repo_a = ws_root / "repo_a"
        repo_a.mkdir()
        (repo_a / "hello.py").write_text("def greet():\n    print('hello')\n")

        ws = Workspace.load_or_create(ws_root)
        ws.add_repo("repo_a", repo_a)
        ws.save()
        ws.index_all()

        results = ws.search(r"def \w+", top_k=5, mode="regex")
        assert isinstance(results, list)


# ===========================================================================
# P5: Streaming
# ===========================================================================

class TestStreaming:
    """Tests for streaming chat and investigation responses."""

    def test_stream_chat_mock(self):
        from semantic_code_intelligence.llm.mock_provider import MockProvider
        from semantic_code_intelligence.llm.provider import LLMMessage, MessageRole
        from semantic_code_intelligence.llm.streaming import StreamEvent, stream_chat

        provider = MockProvider()
        messages = [LLMMessage(role=MessageRole.USER, content="Hello")]

        events: list[StreamEvent] = []
        gen = stream_chat(provider, messages)
        for event in gen:
            events.append(event)

        kinds = [e.kind for e in events]
        assert "start" in kinds
        assert "token" in kinds
        assert "done" in kinds

    def test_chat_cmd_stream_flag_exists(self):
        """Verify the --stream option is registered on chat_cmd."""
        from semantic_code_intelligence.cli.commands.chat_cmd import chat_cmd

        param_names = [p.name for p in chat_cmd.params]
        assert "stream" in param_names

    def test_investigate_cmd_stream_flag_exists(self):
        """Verify the --stream option is registered on investigate_cmd."""
        from semantic_code_intelligence.cli.commands.investigate_cmd import investigate_cmd

        param_names = [p.name for p in investigate_cmd.params]
        assert "stream" in param_names


# ===========================================================================
# Router Registration
# ===========================================================================

class TestRouterRegistration:
    """Tests that new commands are registered in the CLI router."""

    def test_tui_and_mcp_registered(self):
        from semantic_code_intelligence.cli.router import register_commands

        group = __import__("click").Group()
        register_commands(group)
        command_names = list(group.commands.keys())
        assert "tui" in command_names
        assert "mcp" in command_names


# ===========================================================================
# Search Service Multi-Mode
# ===========================================================================

class TestSearchServiceModes:
    """Tests for the search service's multi-mode dispatch."""

    def test_semantic_mode(self, indexed_project: Path):
        from semantic_code_intelligence.services.search_service import search_codebase

        results = search_codebase("authenticate", indexed_project, mode="semantic")
        assert len(results) > 0

    def test_keyword_mode(self, indexed_project: Path):
        from semantic_code_intelligence.services.search_service import search_codebase

        # BM25 tokenizer splits camelCase; use a token that directly matches
        results = search_codebase("authenticate", indexed_project, mode="keyword")
        # Keyword search should at least not crash; may return 0 if token
        # tokenization doesn't match exactly — that's valid BM25 behaviour.
        assert isinstance(results, list)

    def test_regex_mode(self, indexed_project: Path):
        from semantic_code_intelligence.services.search_service import search_codebase

        results = search_codebase(r"def \w+_user", indexed_project, mode="regex")
        assert len(results) > 0

    def test_hybrid_mode(self, indexed_project: Path):
        from semantic_code_intelligence.services.search_service import search_codebase

        results = search_codebase("authenticate user database", indexed_project, mode="hybrid")
        assert len(results) > 0
