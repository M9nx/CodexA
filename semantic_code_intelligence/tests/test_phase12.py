"""Tests for Phase 12 — Platform Enhancements.

Covers: new plugin hooks (ON_STREAM, CUSTOM_VALIDATION), reasoning engine
improvements (context pruning, priority scoring, explainability), enhanced
security validator patterns, and VSCode streaming context.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# =========================================================================
# Plugin hook tests
# =========================================================================

from semantic_code_intelligence.plugins import (
    PluginBase,
    PluginHook,
    PluginManager,
    PluginMetadata,
)


class TestNewPluginHooks:
    def test_on_stream_exists(self):
        assert PluginHook.ON_STREAM == "on_stream"

    def test_custom_validation_exists(self):
        assert PluginHook.CUSTOM_VALIDATION == "custom_validation"

    def test_all_hooks_count(self):
        # 11 original + 2 new = 13
        assert len(PluginHook) == 13

    def test_hook_registry_has_new_hooks(self):
        mgr = PluginManager()
        assert PluginHook.ON_STREAM in mgr._hook_registry
        assert PluginHook.CUSTOM_VALIDATION in mgr._hook_registry

    def test_dispatch_on_stream(self):
        """ON_STREAM hook should dispatch to active plugins."""

        class StreamPlugin(PluginBase):
            def metadata(self):
                return PluginMetadata(name="streamer", hooks=[PluginHook.ON_STREAM])

            def on_hook(self, hook, data):
                data["streamed"] = True
                return data

        mgr = PluginManager()
        plugin = StreamPlugin()
        mgr.register(plugin)
        mgr.activate("streamer")
        result = mgr.dispatch(PluginHook.ON_STREAM, {"token": "hello"})
        assert result["streamed"] is True
        assert result["token"] == "hello"

    def test_dispatch_custom_validation(self):
        """CUSTOM_VALIDATION hook should allow custom validation rules."""

        class ValidatorPlugin(PluginBase):
            def metadata(self):
                return PluginMetadata(name="validator", hooks=[PluginHook.CUSTOM_VALIDATION])

            def on_hook(self, hook, data):
                code = data.get("code", "")
                issues = data.get("issues", [])
                if "TODO" in code:
                    issues.append({"description": "TODO found", "severity": "info"})
                data["issues"] = issues
                return data

        mgr = PluginManager()
        plugin = ValidatorPlugin()
        mgr.register(plugin)
        mgr.activate("validator")
        result = mgr.dispatch(PluginHook.CUSTOM_VALIDATION, {"code": "x = 1  # TODO fix", "issues": []})
        assert len(result["issues"]) == 1
        assert result["issues"][0]["description"] == "TODO found"


# =========================================================================
# Reasoning engine tests
# =========================================================================

from semantic_code_intelligence.llm.reasoning import (
    AskResult,
    ReasoningEngine,
    RefactorResult,
    ReviewResult,
    SuggestResult,
)


class TestExplainabilityMetadata:
    def test_ask_result_has_explainability(self):
        r = AskResult(question="q", answer="a", explainability={"method": "test"})
        d = r.to_dict()
        assert "explainability" in d
        assert d["explainability"]["method"] == "test"

    def test_review_result_has_explainability(self):
        r = ReviewResult(file_path="f.py", explainability={"x": 1})
        assert r.to_dict()["explainability"] == {"x": 1}

    def test_refactor_result_has_explainability(self):
        r = RefactorResult(file_path="f.py", explainability={"x": 2})
        assert r.to_dict()["explainability"] == {"x": 2}

    def test_suggest_result_has_explainability(self):
        r = SuggestResult(target="t", explainability={"x": 3})
        assert r.to_dict()["explainability"] == {"x": 3}

    def test_default_empty_explainability(self):
        r = AskResult(question="q", answer="a")
        assert r.explainability == {}
        assert r.to_dict()["explainability"] == {}


class TestContextPruning:
    def test_score_snippet_base(self):
        snip = {"score": 0.85, "content": "def hello(): pass"}
        score = ReasoningEngine._score_snippet(snip, "hello function")
        assert score >= 0.85

    def test_score_snippet_keyword_bonus(self):
        snip = {"score": 0.5, "content": "def authenticate_user(username): pass"}
        score_relevant = ReasoningEngine._score_snippet(snip, "authenticate user")
        score_irrelevant = ReasoningEngine._score_snippet(snip, "database migration")
        assert score_relevant > score_irrelevant

    def test_score_snippet_no_content(self):
        snip = {"score": 0.3, "content": ""}
        score = ReasoningEngine._score_snippet(snip, "query")
        assert score == 0.3

    def test_prune_context_limits_chars(self):
        provider = MagicMock()
        engine = ReasoningEngine(provider, Path("."), max_context_chars=100)
        snippets = [
            {"score": 0.9, "content": "A" * 60},
            {"score": 0.8, "content": "B" * 60},
            {"score": 0.7, "content": "C" * 60},
        ]
        pruned = engine._prune_context(snippets, "query")
        total = sum(len(s["content"]) for s in pruned)
        assert total <= 120  # first snippet always kept; second may push over

    def test_prune_context_preserves_order(self):
        provider = MagicMock()
        engine = ReasoningEngine(provider, Path("."), max_context_chars=10000)
        snippets = [
            {"score": 0.5, "content": "low"},
            {"score": 0.9, "content": "high"},
            {"score": 0.7, "content": "mid"},
        ]
        pruned = engine._prune_context(snippets, "test")
        scores = [s.get("priority_score", 0) for s in pruned]
        assert scores == sorted(scores, reverse=True)

    def test_prune_context_adds_priority_score(self):
        provider = MagicMock()
        engine = ReasoningEngine(provider, Path("."))
        snippets = [{"score": 0.6, "content": "test data here"}]
        pruned = engine._prune_context(snippets, "test")
        assert "priority_score" in pruned[0]

    def test_prune_context_empty(self):
        provider = MagicMock()
        engine = ReasoningEngine(provider, Path("."))
        assert engine._prune_context([], "query") == []


class TestReasoningEngineMaxContext:
    def test_default_max_context(self):
        provider = MagicMock()
        engine = ReasoningEngine(provider, Path("."))
        assert engine._max_ctx == ReasoningEngine.DEFAULT_MAX_CONTEXT_CHARS

    def test_custom_max_context(self):
        provider = MagicMock()
        engine = ReasoningEngine(provider, Path("."), max_context_chars=2000)
        assert engine._max_ctx == 2000


# =========================================================================
# Security validator tests
# =========================================================================

from semantic_code_intelligence.llm.safety import SafetyValidator


class TestEnhancedSafetyPatterns:
    def setup_method(self):
        self.validator = SafetyValidator()

    # Original patterns still work
    def test_os_system(self):
        assert not self.validator.is_safe("os.system('ls')")

    def test_eval(self):
        assert not self.validator.is_safe("result = eval(user_input)")

    def test_subprocess_shell(self):
        assert not self.validator.is_safe("subprocess.run(cmd, shell=True)")

    def test_drop_table(self):
        assert not self.validator.is_safe("DROP TABLE users")

    # New Phase 12 patterns
    def test_path_traversal(self):
        assert not self.validator.is_safe("open('../../etc/passwd')")

    def test_hardcoded_password(self):
        assert not self.validator.is_safe('password = "mysecretpassword123"')

    def test_hardcoded_api_key(self):
        assert not self.validator.is_safe('api_key = "sk-proj-1234567890abcdef"')

    def test_innerhtml_xss(self):
        assert not self.validator.is_safe('element.innerHTML = userInput')

    def test_document_write_xss(self):
        assert not self.validator.is_safe('document.write(data)')

    def test_md5_insecure(self):
        assert not self.validator.is_safe("hash = MD5(data)")

    def test_sha1_insecure(self):
        assert not self.validator.is_safe("hash = sha1(data)")

    def test_http_insecure(self):
        assert not self.validator.is_safe("url = 'http://example.com/api'")

    def test_http_localhost_allowed(self):
        assert self.validator.is_safe("url = 'http://localhost:8080'")

    def test_ssl_verify_disabled(self):
        assert not self.validator.is_safe("requests.get(url, verify=False)")

    def test_safe_code_passes(self):
        safe = """
import hashlib
from pathlib import Path

def get_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

config = Path("config.yaml").read_text()
"""
        assert self.validator.is_safe(safe)

    def test_validate_report_details(self):
        report = self.validator.validate("el.innerHTML = x\nMD5(y)")
        assert not report.safe
        assert len(report.issues) >= 2
        descs = [i.description for i in report.issues]
        assert any("XSS" in d for d in descs)
        assert any("MD5" in d for d in descs)


# =========================================================================
# VSCode streaming context tests
# =========================================================================

from semantic_code_intelligence.bridge.vscode import (
    StreamChunk,
    VSCodeBridge,
    build_streaming_context,
)


class TestStreamChunk:
    def test_to_dict(self):
        chunk = StreamChunk(kind="token", content="hello")
        d = chunk.to_dict()
        assert d["kind"] == "token"
        assert d["content"] == "hello"
        assert d["metadata"] == {}

    def test_to_dict_with_metadata(self):
        chunk = StreamChunk(kind="context", content="info", metadata={"count": 3})
        d = chunk.to_dict()
        assert d["metadata"]["count"] == 3

    def test_to_sse(self):
        chunk = StreamChunk(kind="done", content="")
        sse = chunk.to_sse()
        assert sse.startswith("data: ")
        assert sse.endswith("\n\n")
        parsed = json.loads(sse[6:].strip())
        assert parsed["kind"] == "done"

    def test_kind_values(self):
        for kind in ("token", "context", "done", "error"):
            chunk = StreamChunk(kind=kind)
            assert chunk.kind == kind


class TestBuildStreamingContext:
    def test_basic_structure(self):
        provider = MagicMock()
        provider.context_for_query.return_value = {
            "results": [
                {"content": "def foo(): pass", "file_path": "a.py", "score": 0.9},
                {"content": "def bar(): pass", "file_path": "b.py", "score": 0.7},
            ]
        }
        chunks = build_streaming_context("test query", provider, top_k=5)
        # First chunk should be context
        assert chunks[0].kind == "context"
        assert "2" in chunks[0].content  # "Found 2 relevant snippets"
        # Middle chunks should be tokens
        assert chunks[1].kind == "token"
        assert chunks[2].kind == "token"
        # Last chunk should be done
        assert chunks[-1].kind == "done"

    def test_empty_results(self):
        provider = MagicMock()
        provider.context_for_query.return_value = {"results": []}
        chunks = build_streaming_context("nothing", provider)
        assert len(chunks) == 2  # context + done
        assert chunks[0].kind == "context"
        assert chunks[1].kind == "done"

    def test_token_metadata_has_file_path(self):
        provider = MagicMock()
        provider.context_for_query.return_value = {
            "results": [{"content": "code", "file_path": "x.py", "score": 0.8}]
        }
        chunks = build_streaming_context("q", provider)
        token_chunk = chunks[1]
        assert token_chunk.metadata["file_path"] == "x.py"
        assert token_chunk.metadata["score"] == 0.8

    def test_all_chunks_serializable(self):
        provider = MagicMock()
        provider.context_for_query.return_value = {
            "results": [{"content": "test", "file_path": "f.py", "score": 0.5}]
        }
        chunks = build_streaming_context("q", provider)
        for chunk in chunks:
            # Must be JSON-serializable
            serialized = json.dumps(chunk.to_dict())
            assert serialized  # non-empty


# =========================================================================
# Integration: existing Phase 9 features still work
# =========================================================================


class TestExistingBridgeFeaturesIntact:
    def test_vscode_bridge_hover_method_exists(self):
        assert hasattr(VSCodeBridge, "hover")

    def test_vscode_bridge_diagnostics_method_exists(self):
        assert hasattr(VSCodeBridge, "diagnostics")

    def test_vscode_bridge_completions_method_exists(self):
        assert hasattr(VSCodeBridge, "completions")

    def test_vscode_bridge_code_actions_method_exists(self):
        assert hasattr(VSCodeBridge, "code_actions")

    def test_vscode_bridge_file_summary_method_exists(self):
        assert hasattr(VSCodeBridge, "file_summary")
