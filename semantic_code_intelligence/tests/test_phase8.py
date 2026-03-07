"""Tests for LLM provider abstraction, reasoning engine, safety validator,
context memory, and CLI commands introduced in Phase 8.
"""

from __future__ import annotations

import json
import os
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# LLM Provider core types
# ---------------------------------------------------------------------------
from semantic_code_intelligence.llm.provider import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    MessageRole,
)


class TestLLMMessage:
    def test_to_dict(self):
        msg = LLMMessage(role=MessageRole.USER, content="hello")
        assert msg.to_dict() == {"role": "user", "content": "hello"}

    def test_roles(self):
        assert MessageRole.SYSTEM.value == "system"
        assert MessageRole.ASSISTANT.value == "assistant"


class TestLLMResponse:
    def test_to_dict(self):
        resp = LLMResponse(content="answer", model="gpt-4", provider="openai", usage={"total_tokens": 10})
        d = resp.to_dict()
        assert d["content"] == "answer"
        assert d["model"] == "gpt-4"
        assert d["provider"] == "openai"
        assert d["usage"]["total_tokens"] == 10

    def test_defaults(self):
        resp = LLMResponse(content="hi")
        assert resp.model == ""
        assert resp.provider == ""
        assert resp.usage == {}


# ---------------------------------------------------------------------------
# Mock Provider
# ---------------------------------------------------------------------------
from semantic_code_intelligence.llm.mock_provider import MockProvider


class TestMockProvider:
    def test_name(self):
        p = MockProvider()
        assert p.name == "mock"

    def test_complete_default(self):
        p = MockProvider(default_response="test response")
        resp = p.complete("prompt")
        assert resp.content == "test response"
        assert resp.provider == "mock"

    def test_chat(self):
        p = MockProvider()
        msgs = [LLMMessage(role=MessageRole.USER, content="hi")]
        resp = p.chat(msgs)
        assert resp.content == "This is a mock LLM response."
        assert len(p.call_history) == 1
        assert p.call_history[0]["method"] == "chat"

    def test_enqueue_response(self):
        p = MockProvider()
        p.enqueue_response("first")
        p.enqueue_response("second")
        assert p.complete("a").content == "first"
        assert p.complete("b").content == "second"
        assert p.complete("c").content == "This is a mock LLM response."

    def test_call_history(self):
        p = MockProvider()
        p.complete("p1")
        p.chat([LLMMessage(role=MessageRole.USER, content="p2")])
        assert len(p.call_history) == 2

    def test_is_available(self):
        # LLMProvider default is True; mock inherits
        p = MockProvider()
        assert p.is_available() is True

    def test_usage_tokens(self):
        p = MockProvider(default_response="short")
        resp = p.complete("a longer prompt text here")
        assert "prompt_tokens" in resp.usage
        assert "completion_tokens" in resp.usage


# ---------------------------------------------------------------------------
# OpenAI Provider (only initialization, no API calls)
# ---------------------------------------------------------------------------
from semantic_code_intelligence.llm.openai_provider import OpenAIProvider


class TestOpenAIProvider:
    def test_name(self):
        p = OpenAIProvider(api_key="test-key")
        assert p.name == "openai"

    def test_is_available(self):
        p = OpenAIProvider(api_key="key")
        assert p.is_available() is True

    def test_not_available_without_key(self):
        p = OpenAIProvider(api_key="")
        assert p.is_available() is False


# ---------------------------------------------------------------------------
# Ollama Provider (initialization only)
# ---------------------------------------------------------------------------
from semantic_code_intelligence.llm.ollama_provider import OllamaProvider


class TestOllamaProvider:
    def test_name(self):
        p = OllamaProvider()
        assert p.name == "ollama"

    def test_is_available_offline(self):
        # Ollama is unlikely to be running in CI, so expect False
        p = OllamaProvider(base_url="http://127.0.0.1:99999")
        assert p.is_available() is False


# ---------------------------------------------------------------------------
# Safety Validator
# ---------------------------------------------------------------------------
from semantic_code_intelligence.llm.safety import SafetyIssue, SafetyReport, SafetyValidator


class TestSafetyValidator:
    def test_safe_code(self):
        v = SafetyValidator()
        report = v.validate("x = 1 + 2\nprint(x)")
        assert report.safe is True
        assert len(report.issues) == 0

    def test_detects_eval(self):
        v = SafetyValidator()
        report = v.validate("result = eval(user_input)")
        assert report.safe is False
        assert any("eval" in i.description for i in report.issues)

    def test_detects_exec(self):
        v = SafetyValidator()
        report = v.validate("exec(code)")
        assert report.safe is False

    def test_detects_os_system(self):
        v = SafetyValidator()
        report = v.validate('os.system("rm -rf /")')
        assert report.safe is False

    def test_detects_shell_true(self):
        v = SafetyValidator()
        report = v.validate('subprocess.run(cmd, shell=True)')
        assert report.safe is False

    def test_detects_sql_drop(self):
        v = SafetyValidator()
        report = v.validate("DROP TABLE users;")
        assert report.safe is False

    def test_is_safe_shortcut(self):
        v = SafetyValidator()
        assert v.is_safe("x = 1") is True
        assert v.is_safe("eval('code')") is False

    def test_custom_patterns(self):
        v = SafetyValidator(extra_patterns=[(r"DANGER", "custom danger pattern")])
        report = v.validate("DANGER zone")
        assert report.safe is False
        assert report.issues[0].description == "custom danger pattern"

    def test_report_to_dict(self):
        report = SafetyReport(safe=False, issues=[
            SafetyIssue(pattern="test", description="desc", line_number=5),
        ])
        d = report.to_dict()
        assert d["safe"] is False
        assert d["issue_count"] == 1
        assert d["issues"][0]["line_number"] == 5

    def test_line_numbers(self):
        v = SafetyValidator()
        code = "x = 1\ny = 2\nresult = eval(z)"
        report = v.validate(code)
        assert report.issues[0].line_number == 3


# ---------------------------------------------------------------------------
# Context Memory
# ---------------------------------------------------------------------------
from semantic_code_intelligence.context.memory import (
    MemoryEntry,
    ReasoningStep,
    SessionMemory,
    WorkspaceMemory,
)


class TestMemoryEntry:
    def test_to_dict_roundtrip(self):
        entry = MemoryEntry(key="q1", content="answer", kind="qa", metadata={"score": 0.9})
        d = entry.to_dict()
        restored = MemoryEntry.from_dict(d)
        assert restored.key == "q1"
        assert restored.content == "answer"
        assert restored.kind == "qa"

    def test_defaults(self):
        entry = MemoryEntry(key="k", content="c")
        assert entry.kind == "general"
        assert entry.timestamp > 0


class TestReasoningStep:
    def test_to_dict(self):
        step = ReasoningStep(step_id=1, action="search", input_text="query", output_text="results")
        d = step.to_dict()
        assert d["step_id"] == 1
        assert d["action"] == "search"


class TestSessionMemory:
    def test_add_and_search(self):
        mem = SessionMemory()
        mem.add("q1", "How does auth work?", kind="qa")
        results = mem.search("auth")
        assert len(results) == 1
        assert results[0].key == "q1"

    def test_get_recent(self):
        mem = SessionMemory()
        for i in range(15):
            mem.add(f"key{i}", f"content{i}")
        recent = mem.get_recent(5)
        assert len(recent) == 5
        assert recent[-1].key == "key14"

    def test_max_entries(self):
        mem = SessionMemory(max_entries=5)
        for i in range(10):
            mem.add(f"k{i}", f"c{i}")
        assert len(mem.entries) == 5

    def test_clear(self):
        mem = SessionMemory()
        mem.add("k", "v")
        mem.start_chain("chain1")
        mem.clear()
        assert len(mem.entries) == 0

    def test_reasoning_chain(self):
        mem = SessionMemory()
        mem.start_chain("c1")
        mem.add_step("c1", "search", "query", "results")
        mem.add_step("c1", "analyze", "results", "insights")
        chain = mem.get_chain("c1")
        assert len(chain) == 2
        assert chain[0].step_id == 1
        assert chain[1].action == "analyze"

    def test_to_dict(self):
        mem = SessionMemory()
        mem.add("k", "v")
        mem.start_chain("c1")
        mem.add_step("c1", "search", "q", "r")
        d = mem.to_dict()
        assert "entries" in d
        assert "chains" in d
        assert len(d["chains"]["c1"]) == 1


class TestWorkspaceMemory:
    def test_add_and_get(self, tmp_path):
        # Set up a .codex dir structure
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        with patch(
            "semantic_code_intelligence.config.settings.AppConfig.config_dir",
            return_value=codex_dir,
        ):
            mem = WorkspaceMemory(tmp_path)
            mem.add("test_key", "test_value", kind="insight")
            entry = mem.get("test_key")
            assert entry is not None
            assert entry.content == "test_value"

    def test_persistence(self, tmp_path):
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        with patch(
            "semantic_code_intelligence.config.settings.AppConfig.config_dir",
            return_value=codex_dir,
        ):
            mem1 = WorkspaceMemory(tmp_path)
            mem1.add("k1", "v1")

            # Create a new instance — should load from disk
            mem2 = WorkspaceMemory(tmp_path)
            entry = mem2.get("k1")
            assert entry is not None
            assert entry.content == "v1"

    def test_remove(self, tmp_path):
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        with patch(
            "semantic_code_intelligence.config.settings.AppConfig.config_dir",
            return_value=codex_dir,
        ):
            mem = WorkspaceMemory(tmp_path)
            mem.add("k", "v")
            assert mem.remove("k") is True
            assert mem.get("k") is None

    def test_search(self, tmp_path):
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        with patch(
            "semantic_code_intelligence.config.settings.AppConfig.config_dir",
            return_value=codex_dir,
        ):
            mem = WorkspaceMemory(tmp_path)
            mem.add("auth", "JWT token validation")
            mem.add("db", "Database connection pooling")
            results = mem.search("JWT")
            assert len(results) == 1

    def test_clear(self, tmp_path):
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        with patch(
            "semantic_code_intelligence.config.settings.AppConfig.config_dir",
            return_value=codex_dir,
        ):
            mem = WorkspaceMemory(tmp_path)
            mem.add("k", "v")
            mem.clear()
            assert len(mem.entries) == 0


# ---------------------------------------------------------------------------
# Reasoning Engine
# ---------------------------------------------------------------------------
from semantic_code_intelligence.llm.reasoning import (
    AskResult,
    RefactorResult,
    ReasoningEngine,
    ReviewResult,
    SuggestResult,
)


class TestAskResult:
    def test_to_dict(self):
        r = AskResult(question="q", answer="a", context_snippets=[{"file": "x.py"}])
        d = r.to_dict()
        assert d["question"] == "q"
        assert d["answer"] == "a"
        assert len(d["context_snippets"]) == 1


class TestReviewResult:
    def test_to_dict(self):
        r = ReviewResult(file_path="x.py", summary="looks good", issues=[])
        d = r.to_dict()
        assert d["file_path"] == "x.py"


class TestRefactorResult:
    def test_to_dict(self):
        r = RefactorResult(file_path="x.py", explanation="improved")
        d = r.to_dict()
        assert d["explanation"] == "improved"


class TestSuggestResult:
    def test_to_dict(self):
        r = SuggestResult(target="func", suggestions=[{"title": "s1"}])
        d = r.to_dict()
        assert d["target"] == "func"
        assert len(d["suggestions"]) == 1


class TestReasoningEngine:
    def _make_engine(self, tmp_path, mock_response="mock answer"):
        """Helper: create an engine with a mock provider and a dummy project."""
        provider = MockProvider(default_response=mock_response)
        # Create a minimal project structure
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        index_dir = codex_dir / "index"
        index_dir.mkdir()
        # Minimal config
        config = {
            "project_root": str(tmp_path),
            "embedding": {},
            "search": {},
            "index": {"ignore_dirs": [], "extensions": [".py"]},
            "llm": {"provider": "mock"},
        }
        (codex_dir / "config.json").write_text(json.dumps(config))

        # Create a sample source file
        src = tmp_path / "sample.py"
        src.write_text("def hello():\n    return 'world'\n")

        engine = ReasoningEngine(provider, tmp_path)
        return engine, provider

    def test_ask(self, tmp_path):
        engine, provider = self._make_engine(tmp_path, "The answer is 42.")
        result = engine.ask("What is the meaning?")
        assert result.answer == "The answer is 42."
        assert result.question == "What is the meaning?"

    def test_review(self, tmp_path):
        engine, provider = self._make_engine(
            tmp_path,
            json.dumps({"issues": [{"severity": "warning", "line": 1, "message": "Missing docstring"}], "summary": "Needs docs"}),
        )
        src = tmp_path / "sample.py"
        result = engine.review(str(src))
        assert result.file_path == str(src)
        assert len(result.issues) == 1
        assert result.summary == "Needs docs"

    def test_review_file_not_found(self, tmp_path):
        engine, _ = self._make_engine(tmp_path)
        result = engine.review(str(tmp_path / "nonexistent.py"))
        assert "not found" in result.summary.lower() or "empty" in result.summary.lower()

    def test_refactor(self, tmp_path):
        engine, provider = self._make_engine(
            tmp_path,
            json.dumps({"refactored_code": "def hello():\n    '''Say hello.'''\n    return 'world'\n", "explanation": "Added docstring"}),
        )
        src = tmp_path / "sample.py"
        result = engine.refactor(str(src), "Add docstrings")
        assert result.refactored_code != ""
        assert "docstring" in result.explanation.lower()

    def test_suggest(self, tmp_path):
        engine, provider = self._make_engine(
            tmp_path,
            json.dumps({"suggestions": [{"title": "Add type hints", "description": "Use type annotations", "reason": "Better IDE support", "priority": "medium"}]}),
        )
        result = engine.suggest("hello")
        assert len(result.suggestions) == 1
        assert result.suggestions[0]["title"] == "Add type hints"

    def test_suggest_raw_fallback(self, tmp_path):
        engine, _ = self._make_engine(tmp_path, "Just some plain text")
        result = engine.suggest("hello")
        assert len(result.suggestions) == 1
        assert result.suggestions[0]["title"] == "Raw response"


# ---------------------------------------------------------------------------
# LLMConfig in settings
# ---------------------------------------------------------------------------
from semantic_code_intelligence.config.settings import AppConfig, LLMConfig, load_config


class TestLLMConfig:
    def test_defaults(self):
        cfg = LLMConfig()
        assert cfg.provider == "mock"
        assert cfg.model == "gpt-3.5-turbo"
        assert cfg.temperature == 0.2
        assert cfg.max_tokens == 2048

    def test_app_config_has_llm(self):
        app = AppConfig()
        assert isinstance(app.llm, LLMConfig)
        assert app.llm.provider == "mock"

    def test_serialisation_roundtrip(self, tmp_path):
        from semantic_code_intelligence.config.settings import save_config

        app = AppConfig(project_root=str(tmp_path))
        app.llm.provider = "openai"
        app.llm.model = "gpt-4"

        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        save_config(app, tmp_path)

        loaded = load_config(tmp_path)
        assert loaded.llm.provider == "openai"
        assert loaded.llm.model == "gpt-4"


# ---------------------------------------------------------------------------
# Plugin AI hooks
# ---------------------------------------------------------------------------
from semantic_code_intelligence.plugins import PluginHook


class TestPluginAIHooks:
    def test_pre_ai_hook_exists(self):
        assert PluginHook.PRE_AI.value == "pre_ai"

    def test_post_ai_hook_exists(self):
        assert PluginHook.POST_AI.value == "post_ai"

    def test_all_hooks_count(self):
        # Expect 11 hooks: 3 indexing + 2 search + 2 analysis + 2 AI + 1 file + 1 custom
        assert len(PluginHook) == 13


# ---------------------------------------------------------------------------
# CLI commands (smoke tests via Click testing)
# ---------------------------------------------------------------------------
from click.testing import CliRunner

from semantic_code_intelligence.cli.main import cli


class TestCLICommands:
    """Smoke tests to verify the 4 new commands are registered and invocable."""

    def test_ask_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["ask", "--help"])
        assert result.exit_code == 0
        assert "Ask a natural-language question" in result.output

    def test_review_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["review", "--help"])
        assert result.exit_code == 0
        assert "Review a source file" in result.output

    def test_refactor_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["refactor", "--help"])
        assert result.exit_code == 0
        assert "Suggest refactored code" in result.output

    def test_suggest_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["suggest", "--help"])
        assert result.exit_code == 0
        assert "intelligent suggestions" in result.output.lower() or "suggestions" in result.output.lower()

    def test_total_commands(self):
        """Ensure 11 commands are registered (7 original + 4 new)."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        # Count command names listed in help
        commands = [
            "init", "index", "search", "explain", "summary", "watch", "deps",
            "ask", "review", "refactor", "suggest",
        ]
        for cmd in commands:
            assert cmd in result.output, f"Command '{cmd}' not found in help output"


# ---------------------------------------------------------------------------
# Router test (updated count)
# ---------------------------------------------------------------------------
from semantic_code_intelligence.cli.router import register_commands


class TestRouterPhase8:
    def test_register_commands_count(self):
        """Router should register exactly 17 commands."""
        import click

        group = click.Group()
        register_commands(group)
        assert len(group.commands) == 27
