"""Tests for Phase 16 — Advanced AI Workflows.

Covers: conversation sessions, session store, investigation chains,
cross-repo refactoring, streaming LLM, CLI commands, router, version, docs.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from semantic_code_intelligence.llm.provider import LLMMessage, LLMResponse, MessageRole


# =========================================================================
# Conversation session tests
# =========================================================================


class TestConversationSession:
    """Tests for ConversationSession data model."""

    def test_create_session(self):
        from semantic_code_intelligence.llm.conversation import ConversationSession

        session = ConversationSession()
        assert len(session.session_id) == 12
        assert session.messages == []
        assert session.turn_count == 0

    def test_add_messages(self):
        from semantic_code_intelligence.llm.conversation import ConversationSession

        session = ConversationSession()
        session.add_system("You are a helper.")
        session.add_user("Hello")
        session.add_assistant("Hi!")

        assert len(session.messages) == 3
        assert session.messages[0].role == MessageRole.SYSTEM
        assert session.messages[1].role == MessageRole.USER
        assert session.messages[2].role == MessageRole.ASSISTANT
        assert session.turn_count == 2  # user + assistant

    def test_last_message(self):
        from semantic_code_intelligence.llm.conversation import ConversationSession

        session = ConversationSession()
        assert session.last_message is None
        session.add_user("Hello")
        assert session.last_message.content == "Hello"

    def test_get_messages_for_llm_no_limit(self):
        from semantic_code_intelligence.llm.conversation import ConversationSession

        session = ConversationSession()
        session.add_system("sys")
        session.add_user("Q1")
        session.add_assistant("A1")
        session.add_user("Q2")

        msgs = session.get_messages_for_llm()
        assert len(msgs) == 4
        assert msgs[0].role == MessageRole.SYSTEM

    def test_get_messages_for_llm_with_limit(self):
        from semantic_code_intelligence.llm.conversation import ConversationSession

        session = ConversationSession()
        session.add_system("sys")
        for i in range(10):
            session.add_user(f"Q{i}")
            session.add_assistant(f"A{i}")

        msgs = session.get_messages_for_llm(max_turns=2)
        # 1 system + 4 recent messages (2 turns × 2)
        assert len(msgs) == 5
        assert msgs[0].role == MessageRole.SYSTEM

    def test_serialization_roundtrip(self):
        from semantic_code_intelligence.llm.conversation import ConversationSession

        session = ConversationSession(title="Test")
        session.add_system("sys")
        session.add_user("Hello")
        session.add_assistant("Hi!")

        data = session.to_dict()
        restored = ConversationSession.from_dict(data)

        assert restored.session_id == session.session_id
        assert restored.title == "Test"
        assert len(restored.messages) == 3
        assert restored.messages[1].content == "Hello"

    def test_title_setting(self):
        from semantic_code_intelligence.llm.conversation import ConversationSession

        session = ConversationSession(title="My Chat")
        assert session.title == "My Chat"


# =========================================================================
# Session store tests
# =========================================================================


class TestSessionStore:
    """Tests for persistent SessionStore."""

    def test_create_store(self, tmp_path):
        from semantic_code_intelligence.llm.conversation import SessionStore

        store = SessionStore(tmp_path)
        assert (tmp_path / ".codex" / "sessions").is_dir()

    def test_save_and_load(self, tmp_path):
        from semantic_code_intelligence.llm.conversation import (
            ConversationSession,
            SessionStore,
        )

        store = SessionStore(tmp_path)
        session = ConversationSession(title="Test Chat")
        session.add_user("Hello")
        session.add_assistant("Hi!")

        store.save(session)
        loaded = store.load(session.session_id)

        assert loaded is not None
        assert loaded.session_id == session.session_id
        assert loaded.title == "Test Chat"
        assert len(loaded.messages) == 2

    def test_load_nonexistent(self, tmp_path):
        from semantic_code_intelligence.llm.conversation import SessionStore

        store = SessionStore(tmp_path)
        assert store.load("nonexistent") is None

    def test_list_sessions(self, tmp_path):
        from semantic_code_intelligence.llm.conversation import (
            ConversationSession,
            SessionStore,
        )

        store = SessionStore(tmp_path)
        s1 = ConversationSession(title="Chat 1")
        s1.add_user("Hello")
        s2 = ConversationSession(title="Chat 2")
        s2.add_user("Hey")

        store.save(s1)
        store.save(s2)

        sessions = store.list_sessions()
        assert len(sessions) == 2
        ids = {s["session_id"] for s in sessions}
        assert s1.session_id in ids
        assert s2.session_id in ids

    def test_delete_session(self, tmp_path):
        from semantic_code_intelligence.llm.conversation import (
            ConversationSession,
            SessionStore,
        )

        store = SessionStore(tmp_path)
        session = ConversationSession()
        store.save(session)
        assert store.delete(session.session_id) is True
        assert store.load(session.session_id) is None
        assert store.delete(session.session_id) is False

    def test_get_or_create_new(self, tmp_path):
        from semantic_code_intelligence.llm.conversation import SessionStore

        store = SessionStore(tmp_path)
        session = store.get_or_create()
        assert session is not None
        assert len(session.messages) == 0

    def test_get_or_create_existing(self, tmp_path):
        from semantic_code_intelligence.llm.conversation import (
            ConversationSession,
            SessionStore,
        )

        store = SessionStore(tmp_path)
        original = ConversationSession(title="Existing")
        original.add_user("Test")
        store.save(original)

        resumed = store.get_or_create(original.session_id)
        assert resumed.title == "Existing"
        assert len(resumed.messages) == 1

    def test_path_traversal_prevention(self, tmp_path):
        from semantic_code_intelligence.llm.conversation import SessionStore

        store = SessionStore(tmp_path)
        # Attempt path traversal — should be sanitised
        path = store._session_path("../../../etc/passwd")
        assert ".." not in str(path.name)
        assert "passwd" in str(path.name)


# =========================================================================
# Investigation chain tests
# =========================================================================


class TestInvestigationChain:
    """Tests for autonomous investigation chains."""

    def test_simple_conclude(self, tmp_path):
        from semantic_code_intelligence.llm.investigation import InvestigationChain
        from semantic_code_intelligence.llm.mock_provider import MockProvider

        provider = MockProvider()
        provider.enqueue_response(json.dumps({
            "thought": "I can answer directly.",
            "action": "conclude",
            "action_input": "The answer is 42.",
        }))

        chain = InvestigationChain(provider, tmp_path, max_steps=3)
        result = chain.investigate("What is the answer?")

        assert result.conclusion == "The answer is 42."
        assert result.total_steps == 1
        assert result.chain_id != ""

    def test_search_then_conclude(self, tmp_path):
        from semantic_code_intelligence.llm.investigation import InvestigationChain
        from semantic_code_intelligence.llm.mock_provider import MockProvider

        provider = MockProvider()
        # Step 1: search
        provider.enqueue_response(json.dumps({
            "thought": "Need to search for context.",
            "action": "search",
            "action_input": "authentication logic",
        }))
        # Step 2: conclude
        provider.enqueue_response(json.dumps({
            "thought": "Found it.",
            "action": "conclude",
            "action_input": "Auth logic is in auth.py",
        }))

        chain = InvestigationChain(provider, tmp_path, max_steps=5)
        result = chain.investigate("Where is authentication?")

        assert result.total_steps == 2
        assert "auth.py" in result.conclusion

    def test_max_steps_forces_conclusion(self, tmp_path):
        from semantic_code_intelligence.llm.investigation import InvestigationChain
        from semantic_code_intelligence.llm.mock_provider import MockProvider

        provider = MockProvider()
        # Always want to search — never conclude
        for _ in range(5):
            provider.enqueue_response(json.dumps({
                "thought": "Keep searching.",
                "action": "search",
                "action_input": "something",
            }))
        # Forced conclusion response
        provider.enqueue_response("Forced final answer.")

        chain = InvestigationChain(provider, tmp_path, max_steps=3)
        result = chain.investigate("Tell me everything")

        # Should have 3 search steps, then forced conclusion
        assert result.total_steps == 3

    def test_result_to_dict(self, tmp_path):
        from semantic_code_intelligence.llm.investigation import InvestigationResult

        result = InvestigationResult(
            question="Why?",
            conclusion="Because.",
            chain_id="abc",
            total_steps=2,
            steps=[{"step": 1, "action": "search"}],
        )
        d = result.to_dict()
        assert d["question"] == "Why?"
        assert d["total_steps"] == 2

    def test_parse_fallback(self, tmp_path):
        from semantic_code_intelligence.llm.investigation import InvestigationChain
        from semantic_code_intelligence.llm.mock_provider import MockProvider

        provider = MockProvider()
        # Non-JSON response — should fallback to conclude
        provider.enqueue_response("Just a plain text answer.")

        chain = InvestigationChain(provider, tmp_path, max_steps=3)
        result = chain.investigate("Question?")

        assert result.conclusion == "Just a plain text answer."
        assert result.total_steps == 1


# =========================================================================
# Cross-repo refactoring tests
# =========================================================================


class TestCrossRefactor:
    """Tests for cross-repo refactoring analysis."""

    def test_empty_workspace(self, tmp_path):
        from semantic_code_intelligence.llm.cross_refactor import analyze_cross_repo

        result = analyze_cross_repo(tmp_path)
        assert result.repos_analyzed == []
        assert result.total_symbols == 0
        assert result.matches == []

    def test_result_to_dict(self):
        from semantic_code_intelligence.llm.cross_refactor import (
            CrossRefactorResult,
            CrossRepoMatch,
        )

        match = CrossRepoMatch(
            repo_a="backend",
            symbol_a="validate",
            file_a="auth.py",
            repo_b="frontend",
            symbol_b="validate",
            file_b="auth.ts",
            similarity_note="Jaccard: 0.85",
        )
        result = CrossRefactorResult(
            repos_analyzed=["backend", "frontend"],
            total_symbols=10,
            matches=[match],
        )
        d = result.to_dict()
        assert d["repos_analyzed"] == ["backend", "frontend"]
        assert len(d["matches"]) == 1
        assert d["matches"][0]["symbol_a"] == "validate"

    def test_cross_repo_match_to_dict(self):
        from semantic_code_intelligence.llm.cross_refactor import CrossRepoMatch

        m = CrossRepoMatch(
            repo_a="a", symbol_a="foo", file_a="a.py",
            repo_b="b", symbol_b="bar", file_b="b.py",
        )
        d = m.to_dict()
        assert d["repo_a"] == "a"
        assert d["file_b"] == "b.py"


class TestCrossRepoDuplicates:
    """Tests for cross-repo duplicate detection internals."""

    def test_find_cross_duplicates_same_repo_excluded(self):
        from semantic_code_intelligence.llm.cross_refactor import _find_cross_duplicates

        body = "def f(x):\n    y = x + 1\n    z = y * 2\n    return z\n    # pad\n"
        repo_symbols = {
            "repoA": [
                {"name": "f1", "kind": "function", "file": "a.py", "lines": 5, "body": body},
                {"name": "f2", "kind": "function", "file": "b.py", "lines": 5, "body": body},
            ],
        }
        matches = _find_cross_duplicates(repo_symbols)
        assert len(matches) == 0  # Same repo — excluded

    def test_find_cross_duplicates_across_repos(self):
        from semantic_code_intelligence.llm.cross_refactor import _find_cross_duplicates

        body = "def f(x):\n    y = x + 1\n    z = y * 2\n    return z\n    # extra\n"
        repo_symbols = {
            "repoA": [{"name": "compute", "kind": "function", "file": "a.py", "lines": 5, "body": body}],
            "repoB": [{"name": "calc", "kind": "function", "file": "b.py", "lines": 5, "body": body}],
        }
        matches = _find_cross_duplicates(repo_symbols, threshold=0.5)
        assert len(matches) == 1
        assert matches[0].repo_a != matches[0].repo_b


# =========================================================================
# Streaming LLM tests
# =========================================================================


class TestStreaming:
    """Tests for streaming LLM support."""

    def test_stream_mock(self):
        from semantic_code_intelligence.llm.mock_provider import MockProvider
        from semantic_code_intelligence.llm.streaming import stream_chat, StreamEvent

        provider = MockProvider(default_response="Hello world test")
        messages = [LLMMessage(role=MessageRole.USER, content="Hi")]

        events = list(stream_chat(provider, messages))
        kinds = [e.kind for e in events]

        assert "start" in kinds
        assert "token" in kinds
        assert "done" in kinds

        # Accumulate tokens
        text = "".join(e.content for e in events if e.kind == "token")
        assert text == "Hello world test"

    def test_stream_mock_with_custom_response(self):
        from semantic_code_intelligence.llm.mock_provider import MockProvider
        from semantic_code_intelligence.llm.streaming import stream_chat

        provider = MockProvider()
        provider.enqueue_response("Custom streaming response")
        messages = [LLMMessage(role=MessageRole.USER, content="Test")]

        events = list(stream_chat(provider, messages))
        text = "".join(e.content for e in events if e.kind == "token")
        assert text == "Custom streaming response"

    def test_stream_event_to_dict(self):
        from semantic_code_intelligence.llm.streaming import StreamEvent

        event = StreamEvent(kind="token", content="hello", metadata={"pos": 1})
        d = event.to_dict()
        assert d["kind"] == "token"
        assert d["content"] == "hello"

    def test_stream_event_to_sse(self):
        from semantic_code_intelligence.llm.streaming import StreamEvent

        event = StreamEvent(kind="token", content="hi")
        sse = event.to_sse()
        assert sse.startswith("data: ")
        assert sse.endswith("\n\n")
        payload = json.loads(sse[len("data: "):])
        assert payload["kind"] == "token"

    def test_stream_with_plugin_manager(self):
        from semantic_code_intelligence.llm.mock_provider import MockProvider
        from semantic_code_intelligence.llm.streaming import stream_chat
        from semantic_code_intelligence.plugins import PluginManager

        provider = MockProvider(default_response="Token test")
        pm = PluginManager()
        messages = [LLMMessage(role=MessageRole.USER, content="Test")]

        events = list(stream_chat(provider, messages, plugin_manager=pm))
        assert any(e.kind == "token" for e in events)

    def test_fallback_non_standard_provider(self):
        """Test that a non-standard provider falls back to single-token emit."""
        from semantic_code_intelligence.llm.streaming import stream_chat

        class CustomProvider:
            name = "custom"

            def chat(self, messages, **kwargs):
                return LLMResponse(content="Custom response", model="custom", provider="custom")

        provider = CustomProvider()
        messages = [LLMMessage(role=MessageRole.USER, content="Test")]

        events = list(stream_chat(provider, messages))
        kinds = [e.kind for e in events]
        assert "start" in kinds
        assert "token" in kinds
        assert "done" in kinds
        assert events[1].content == "Custom response"


# =========================================================================
# CLI command tests
# =========================================================================


class TestChatCLI:
    """Tests for the `codex chat` command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def _extract_json(self, output: str) -> dict:
        """Extract JSON object from CLI output, skipping any log noise."""
        # Find the first '{' and parse from there
        start = output.index("{")
        return json.loads(output[start:])

    def test_help(self, runner):
        from semantic_code_intelligence.cli.commands.chat_cmd import chat_cmd

        result = runner.invoke(chat_cmd, ["--help"])
        assert result.exit_code == 0
        assert "chat" in result.output.lower() or "conversation" in result.output.lower()

    def test_has_session_option(self, runner):
        from semantic_code_intelligence.cli.commands.chat_cmd import chat_cmd

        result = runner.invoke(chat_cmd, ["--help"])
        assert "--session" in result.output

    def test_has_list_sessions(self, runner):
        from semantic_code_intelligence.cli.commands.chat_cmd import chat_cmd

        result = runner.invoke(chat_cmd, ["--help"])
        assert "--list-sessions" in result.output

    def test_has_max_turns(self, runner):
        from semantic_code_intelligence.cli.commands.chat_cmd import chat_cmd

        result = runner.invoke(chat_cmd, ["--help"])
        assert "--max-turns" in result.output

    def test_json_output(self, runner, tmp_path):
        from semantic_code_intelligence.cli.commands.chat_cmd import chat_cmd

        result = runner.invoke(chat_cmd, [
            "Hello", "--json", "--path", str(tmp_path)
        ], obj={"pipe": False})
        assert result.exit_code == 0
        data = self._extract_json(result.output)
        assert "session_id" in data
        assert "answer" in data

    def test_pipe_mode(self, runner, tmp_path):
        from semantic_code_intelligence.cli.commands.chat_cmd import chat_cmd

        result = runner.invoke(chat_cmd, [
            "Hello", "--pipe", "--path", str(tmp_path)
        ], obj={"pipe": False})
        assert result.exit_code == 0
        assert len(result.output.strip()) > 0

    def test_list_sessions_json(self, runner, tmp_path):
        from semantic_code_intelligence.cli.commands.chat_cmd import chat_cmd

        result = runner.invoke(chat_cmd, [
            "x", "--list-sessions", "--json", "--path", str(tmp_path)
        ], obj={"pipe": False})
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)


class TestInvestigateCLI:
    """Tests for the `codex investigate` command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_help(self, runner):
        from semantic_code_intelligence.cli.commands.investigate_cmd import investigate_cmd

        result = runner.invoke(investigate_cmd, ["--help"])
        assert result.exit_code == 0
        assert "investigate" in result.output.lower() or "investigation" in result.output.lower()

    def test_has_max_steps(self, runner):
        from semantic_code_intelligence.cli.commands.investigate_cmd import investigate_cmd

        result = runner.invoke(investigate_cmd, ["--help"])
        assert "--max-steps" in result.output

    def test_json_output(self, runner, tmp_path):
        from semantic_code_intelligence.cli.commands.investigate_cmd import investigate_cmd

        result = runner.invoke(investigate_cmd, [
            "What is this?", "--json", "--path", str(tmp_path)
        ], obj={"pipe": False})
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "question" in data
        assert "conclusion" in data
        assert "steps" in data

    def test_pipe_mode(self, runner, tmp_path):
        from semantic_code_intelligence.cli.commands.investigate_cmd import investigate_cmd

        result = runner.invoke(investigate_cmd, [
            "What is this?", "--pipe", "--path", str(tmp_path)
        ], obj={"pipe": False})
        assert result.exit_code == 0
        assert "Conclusion:" in result.output


class TestCrossRefactorCLI:
    """Tests for the `codex cross-refactor` command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_help(self, runner):
        from semantic_code_intelligence.cli.commands.cross_refactor_cmd import cross_refactor_cmd

        result = runner.invoke(cross_refactor_cmd, ["--help"])
        assert result.exit_code == 0
        assert "cross-refactor" in result.output.lower() or "refactor" in result.output.lower()

    def test_has_threshold(self, runner):
        from semantic_code_intelligence.cli.commands.cross_refactor_cmd import cross_refactor_cmd

        result = runner.invoke(cross_refactor_cmd, ["--help"])
        assert "--threshold" in result.output

    def test_json_empty_workspace(self, runner, tmp_path):
        from semantic_code_intelligence.cli.commands.cross_refactor_cmd import cross_refactor_cmd

        result = runner.invoke(cross_refactor_cmd, [
            "--json", "--path", str(tmp_path)
        ], obj={"pipe": False})
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["repos_analyzed"] == []

    def test_pipe_mode(self, runner, tmp_path):
        from semantic_code_intelligence.cli.commands.cross_refactor_cmd import cross_refactor_cmd

        result = runner.invoke(cross_refactor_cmd, [
            "--pipe", "--path", str(tmp_path)
        ], obj={"pipe": False})
        assert result.exit_code == 0
        assert "Repos:" in result.output


# =========================================================================
# Router, version, and module structure tests
# =========================================================================


class TestRouterPhase16:
    """Tests for CLI router registration."""

    def test_register_commands_count(self):
        import click
        from semantic_code_intelligence.cli.router import register_commands

        group = click.Group("test")
        register_commands(group)
        assert len(group.commands) == 37

    def test_chat_command_registered(self):
        from semantic_code_intelligence.cli.main import cli

        assert "chat" in cli.commands

    def test_investigate_command_registered(self):
        from semantic_code_intelligence.cli.main import cli

        assert "investigate" in cli.commands

    def test_cross_refactor_command_registered(self):
        from semantic_code_intelligence.cli.main import cli

        assert "cross-refactor" in cli.commands


class TestVersionBump:
    """Test version is 0.19.0."""

    def test_version_is_016(self):
        from semantic_code_intelligence import __version__

        assert __version__ == "0.28.0"


class TestPhase16ModuleStructure:
    """Tests for module import structure."""

    def test_import_conversation(self):
        from semantic_code_intelligence.llm.conversation import (
            ConversationSession,
            SessionStore,
        )

    def test_import_investigation(self):
        from semantic_code_intelligence.llm.investigation import (
            InvestigationChain,
            InvestigationResult,
        )

    def test_import_streaming(self):
        from semantic_code_intelligence.llm.streaming import (
            stream_chat,
            StreamEvent,
        )

    def test_import_cross_refactor(self):
        from semantic_code_intelligence.llm.cross_refactor import (
            analyze_cross_repo,
            CrossRefactorResult,
            CrossRepoMatch,
        )

    def test_llm_package_exports(self):
        from semantic_code_intelligence.llm import (
            ConversationSession,
            SessionStore,
            InvestigationChain,
            InvestigationResult,
            stream_chat,
            StreamEvent,
            analyze_cross_repo,
            CrossRefactorResult,
        )


class TestDocsGenerator:
    """Tests for AI workflows doc generation."""

    def test_generate_ai_workflows_reference(self):
        from semantic_code_intelligence.docs import generate_ai_workflows_reference

        md = generate_ai_workflows_reference()
        assert "AI Workflows" in md
        assert "codex chat" in md
        assert "codex investigate" in md
        assert "codex cross-refactor" in md
        assert "stream_chat" in md
        assert "ON_STREAM" in md

    def test_generate_all_docs_includes_ai(self, tmp_path):
        from semantic_code_intelligence.docs import generate_all_docs

        generated = generate_all_docs(tmp_path)
        assert "AI_WORKFLOWS.md" in generated


# =========================================================================
# Backward compatibility tests
# =========================================================================


class TestBackwardCompatibility:
    """Ensure Phase 14 and Phase 15 modules still work."""

    def test_ci_module_imports(self):
        from semantic_code_intelligence.ci.quality import analyze_project, QualityReport
        from semantic_code_intelligence.ci.pr import generate_pr_report, PRReport
        from semantic_code_intelligence.ci.templates import get_template
        from semantic_code_intelligence.ci.hooks import run_precommit_check

    def test_web_module_imports(self):
        from semantic_code_intelligence.web.api import APIHandler
        from semantic_code_intelligence.web.ui import page_search
        from semantic_code_intelligence.web.visualize import render_call_graph

    def test_reasoning_engine_intact(self):
        from semantic_code_intelligence.llm.reasoning import (
            ReasoningEngine,
            AskResult,
            ReviewResult,
            RefactorResult,
            SuggestResult,
        )

    def test_plugin_hooks_intact(self):
        from semantic_code_intelligence.plugins import PluginHook

        assert PluginHook.ON_STREAM.value == "on_stream"
        assert PluginHook.CUSTOM_VALIDATION.value == "custom_validation"

    def test_safety_validator_intact(self):
        from semantic_code_intelligence.llm.safety import SafetyValidator

        v = SafetyValidator()
        assert v.validate("x = 1\n").safe is True

    def test_session_memory_intact(self):
        from semantic_code_intelligence.context.memory import SessionMemory, ReasoningStep

        mem = SessionMemory()
        mem.start_chain("test")
        mem.add_step("test", "search", "query", "results")
        chain = mem.get_chain("test")
        assert len(chain) == 1
        assert chain[0].action == "search"
