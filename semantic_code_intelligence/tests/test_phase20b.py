"""Phase 20b — Extended deep coverage tests (targeting 2000+ total).

Covers configuration, services, protocol, reasoning, investigation,
analysis, context engine, memory, conversation, streaming, storage,
chunking, scanning, parsing, and CLI helpers.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch


# ==========================================================================
#  Config / Settings
# ==========================================================================

from semantic_code_intelligence.config.settings import (
    AppConfig,
    EmbeddingConfig,
    IndexConfig,
    LLMConfig,
    QualityConfig,
    SearchConfig,
    DEFAULT_EXTENSIONS,
    DEFAULT_IGNORE_DIRS,
    load_config,
    save_config,
    init_project,
)


class TestEmbeddingConfig:
    def test_defaults(self):
        ec = EmbeddingConfig()
        assert ec.model_name == "all-MiniLM-L6-v2"
        assert ec.chunk_size == 512
        assert ec.chunk_overlap == 64

    def test_custom(self):
        ec = EmbeddingConfig(model_name="custom", chunk_size=256, chunk_overlap=32)
        assert ec.model_name == "custom"
        assert ec.chunk_size == 256

    def test_model_dump(self):
        ec = EmbeddingConfig()
        d = ec.model_dump()
        assert "model_name" in d
        assert "chunk_size" in d


class TestSearchConfig:
    def test_defaults(self):
        sc = SearchConfig()
        assert sc.top_k == 10
        assert sc.similarity_threshold == 0.3

    def test_custom(self):
        sc = SearchConfig(top_k=5, similarity_threshold=0.5)
        assert sc.top_k == 5
        assert sc.similarity_threshold == 0.5

    def test_model_dump(self):
        d = SearchConfig().model_dump()
        assert "top_k" in d
        assert "similarity_threshold" in d


class TestIndexConfig:
    def test_defaults(self):
        ic = IndexConfig()
        assert ".git" in ic.ignore_dirs
        assert ".py" in ic.extensions
        assert ic.use_incremental is True

    def test_custom_ignore(self):
        ic = IndexConfig(ignore_dirs={"custom_dir"})
        assert "custom_dir" in ic.ignore_dirs

    def test_custom_extensions(self):
        ic = IndexConfig(extensions={".xyz"})
        assert ".xyz" in ic.extensions

    def test_model_dump(self):
        d = IndexConfig().model_dump()
        assert "ignore_dirs" in d
        assert "extensions" in d
        assert "use_incremental" in d


class TestLLMConfig:
    def test_defaults(self):
        lc = LLMConfig()
        assert lc.provider == "mock"
        assert lc.model == "gpt-3.5-turbo"
        assert lc.temperature == 0.2
        assert lc.max_tokens == 2048

    def test_custom(self):
        lc = LLMConfig(provider="openai", api_key="key123", temperature=0.8)
        assert lc.provider == "openai"
        assert lc.api_key == "key123"
        assert lc.temperature == 0.8

    def test_model_dump(self):
        d = LLMConfig().model_dump()
        assert "provider" in d
        assert "model" in d
        assert "api_key" in d


class TestQualityConfig:
    def test_defaults(self):
        qc = QualityConfig()
        assert qc.complexity_threshold == 10
        assert qc.min_maintainability == 40.0
        assert qc.max_issues == 20
        assert qc.snapshot_on_index is False
        assert qc.history_limit == 50

    def test_custom(self):
        qc = QualityConfig(complexity_threshold=15, min_maintainability=50.0)
        assert qc.complexity_threshold == 15

    def test_model_dump(self):
        d = QualityConfig().model_dump()
        assert "complexity_threshold" in d
        assert "history_limit" in d


class TestAppConfig:
    def test_defaults(self):
        ac = AppConfig()
        assert ac.project_root == "."
        assert ac.verbose is False
        assert isinstance(ac.embedding, EmbeddingConfig)
        assert isinstance(ac.search, SearchConfig)
        assert isinstance(ac.index, IndexConfig)
        assert isinstance(ac.llm, LLMConfig)
        assert isinstance(ac.quality, QualityConfig)

    def test_config_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            cd = AppConfig.config_dir(tmp)
            assert cd.name == ".codex"
            assert cd.parent == Path(tmp).resolve()

    def test_config_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            cp = AppConfig.config_path(tmp)
            assert cp.name == "config.json"

    def test_index_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            idx = AppConfig.index_dir(tmp)
            assert idx.name == "index"

    def test_model_dump_roundtrip(self):
        ac = AppConfig()
        d = ac.model_dump()
        ac2 = AppConfig.model_validate(d)
        assert ac2.project_root == ac.project_root

    def test_nested_configs(self):
        ac = AppConfig()
        d = ac.model_dump()
        assert "embedding" in d
        assert "search" in d
        assert "index" in d
        assert "llm" in d
        assert "quality" in d


class TestLoadConfig:
    def test_load_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = load_config(tmp)
            assert isinstance(cfg, AppConfig)

    def test_load_from_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, path = init_project(tmp)
            loaded = load_config(tmp)
            assert loaded.project_root == cfg.project_root


class TestSaveConfig:
    def test_save_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = AppConfig(project_root=str(Path(tmp).resolve()))
            path = save_config(cfg, tmp)
            assert path.exists()

    def test_save_json_parseable(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = AppConfig(project_root=str(Path(tmp).resolve()))
            path = save_config(cfg, tmp)
            data = json.loads(path.read_text(encoding="utf-8"))
            assert "project_root" in data


class TestInitProject:
    def test_creates_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, path = init_project(tmp)
            assert path.exists()
            assert AppConfig.config_dir(tmp).exists()
            assert AppConfig.index_dir(tmp).exists()

    def test_returns_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, _ = init_project(tmp)
            assert isinstance(cfg, AppConfig)


class TestDefaultSets:
    def test_default_ignore_dirs(self):
        assert ".git" in DEFAULT_IGNORE_DIRS
        assert "__pycache__" in DEFAULT_IGNORE_DIRS
        assert "node_modules" in DEFAULT_IGNORE_DIRS

    def test_default_extensions(self):
        assert ".py" in DEFAULT_EXTENSIONS
        assert ".js" in DEFAULT_EXTENSIONS
        assert ".ts" in DEFAULT_EXTENSIONS
        assert ".java" in DEFAULT_EXTENSIONS


# ==========================================================================
#  Bridge Protocol
# ==========================================================================

from semantic_code_intelligence.bridge.protocol import (
    RequestKind,
    AgentRequest,
    AgentResponse,
)


class TestRequestKind:
    def test_has_semantic_search(self):
        assert RequestKind.SEMANTIC_SEARCH.value == "semantic_search"

    def test_has_explain_symbol(self):
        assert RequestKind.EXPLAIN_SYMBOL.value == "explain_symbol"

    def test_has_explain_file(self):
        assert RequestKind.EXPLAIN_FILE.value == "explain_file"

    def test_has_get_context(self):
        assert RequestKind.GET_CONTEXT.value == "get_context"

    def test_has_get_dependencies(self):
        assert RequestKind.GET_DEPENDENCIES.value == "get_dependencies"

    def test_has_get_call_graph(self):
        assert RequestKind.GET_CALL_GRAPH.value == "get_call_graph"

    def test_has_summarize_repo(self):
        assert RequestKind.SUMMARIZE_REPO.value == "summarize_repo"

    def test_has_find_references(self):
        assert RequestKind.FIND_REFERENCES.value == "find_references"

    def test_has_validate_code(self):
        assert RequestKind.VALIDATE_CODE.value == "validate_code"

    def test_has_list_capabilities(self):
        assert RequestKind.LIST_CAPABILITIES.value == "list_capabilities"

    def test_has_invoke_tool(self):
        assert RequestKind.INVOKE_TOOL.value == "invoke_tool"

    def test_has_list_tools(self):
        assert RequestKind.LIST_TOOLS.value == "list_tools"

    def test_count(self):
        assert len(RequestKind) == 12


class TestAgentRequestProtocol:
    def test_create_minimal(self):
        r = AgentRequest(kind="semantic_search")
        assert r.kind == "semantic_search"
        assert r.params == {}

    def test_create_full(self):
        r = AgentRequest(kind="explain_symbol", params={"name": "foo"},
                         request_id="r1", source="copilot")
        assert r.params["name"] == "foo"
        assert r.request_id == "r1"
        assert r.source == "copilot"

    def test_to_dict(self):
        r = AgentRequest(kind="test", params={"a": 1})
        d = r.to_dict()
        assert d["kind"] == "test"
        assert d["params"]["a"] == 1
        assert "request_id" in d
        assert "source" in d

    def test_to_json(self):
        r = AgentRequest(kind="test")
        j = r.to_json()
        parsed = json.loads(j)
        assert parsed["kind"] == "test"

    def test_from_dict(self):
        data = {"kind": "semantic_search", "params": {"q": "hello"}, "request_id": "x"}
        r = AgentRequest.from_dict(data)
        assert r.kind == "semantic_search"
        assert r.params["q"] == "hello"

    def test_from_json(self):
        j = '{"kind":"explain_symbol","params":{"name":"foo"}}'
        r = AgentRequest.from_json(j)
        assert r.kind == "explain_symbol"
        assert r.params["name"] == "foo"

    def test_roundtrip(self):
        r = AgentRequest(kind="test", params={"x": 42}, request_id="abc")
        r2 = AgentRequest.from_json(r.to_json())
        assert r2.kind == r.kind
        assert r2.params == r.params
        assert r2.request_id == r.request_id

    def test_from_dict_missing_fields(self):
        r = AgentRequest.from_dict({})
        assert r.kind == ""
        assert r.params == {}


class TestAgentResponseProtocol:
    def test_success(self):
        r = AgentResponse(success=True, data={"result": "ok"})
        assert r.success is True
        assert r.data["result"] == "ok"

    def test_error(self):
        r = AgentResponse(success=False, error="not found")
        assert r.success is False
        assert r.error == "not found"

    def test_to_dict_success(self):
        r = AgentResponse(success=True, data={"a": 1}, request_id="r1")
        d = r.to_dict()
        assert d["success"] is True
        assert "data" in d
        assert d["request_id"] == "r1"

    def test_to_dict_error(self):
        r = AgentResponse(success=False, error="boom")
        d = r.to_dict()
        assert "error" in d
        assert d["error"] == "boom"

    def test_to_json(self):
        r = AgentResponse(success=True, data={})
        j = r.to_json()
        parsed = json.loads(j)
        assert parsed["success"] is True

    def test_elapsed_ms(self):
        r = AgentResponse(success=True, data={}, elapsed_ms=12.345)
        d = r.to_dict()
        assert d["elapsed_ms"] == 12.35  # rounded to 2 decimal places

    def test_to_json_with_indent(self):
        r = AgentResponse(success=True, data={"x": 1})
        j = r.to_json(indent=2)
        assert "\n" in j


# ==========================================================================
#  LLM Provider Base & Message
# ==========================================================================

from semantic_code_intelligence.llm.provider import (
    LLMMessage,
    LLMResponse,
    MessageRole,
)


class TestMessageRole:
    def test_system(self):
        assert MessageRole.SYSTEM.value == "system"

    def test_user(self):
        assert MessageRole.USER.value == "user"

    def test_assistant(self):
        assert MessageRole.ASSISTANT.value == "assistant"

    def test_count(self):
        assert len(MessageRole) == 3


class TestLLMMessage:
    def test_create(self):
        m = LLMMessage(role=MessageRole.USER, content="hello")
        assert m.role == MessageRole.USER
        assert m.content == "hello"

    def test_to_dict(self):
        m = LLMMessage(role=MessageRole.SYSTEM, content="prompt")
        d = m.to_dict()
        assert d["role"] == "system"
        assert d["content"] == "prompt"

    def test_is_dataclass(self):
        assert is_dataclass(LLMMessage)

    def test_equality(self):
        m1 = LLMMessage(role=MessageRole.USER, content="hi")
        m2 = LLMMessage(role=MessageRole.USER, content="hi")
        assert m1 == m2

    def test_different(self):
        m1 = LLMMessage(role=MessageRole.USER, content="hi")
        m2 = LLMMessage(role=MessageRole.ASSISTANT, content="hi")
        assert m1 != m2


class TestLLMResponse:
    def test_create(self):
        r = LLMResponse(content="answer")
        assert r.content == "answer"
        assert r.model == ""
        assert r.provider == ""

    def test_to_dict(self):
        r = LLMResponse(content="ans", model="gpt-4", provider="openai",
                        usage={"prompt_tokens": 10, "completion_tokens": 20})
        d = r.to_dict()
        assert d["content"] == "ans"
        assert d["model"] == "gpt-4"
        assert d["provider"] == "openai"
        assert d["usage"]["prompt_tokens"] == 10

    def test_defaults(self):
        r = LLMResponse(content="x")
        assert r.usage == {}
        assert r.raw == {}


# ==========================================================================
#  LLM Safety
# ==========================================================================

from semantic_code_intelligence.llm.safety import SafetyIssue, SafetyReport, SafetyValidator


class TestSafetyIssueDeep:
    def test_create(self):
        si = SafetyIssue(pattern="eval", description="Dangerous eval", line_number=5)
        assert si.pattern == "eval"
        assert si.line_number == 5

    def test_to_dict(self):
        si = SafetyIssue(pattern="exec", description="exec call", severity="error")
        d = si.to_dict()
        assert d["pattern"] == "exec"
        assert d["severity"] == "error"

    def test_default_severity(self):
        si = SafetyIssue(pattern="x", description="y")
        assert si.severity == "warning"


class TestSafetyReportDeep:
    def test_safe(self):
        sr = SafetyReport()
        assert sr.safe is True
        assert sr.issues == []

    def test_unsafe(self):
        sr = SafetyReport(safe=False, issues=[
            SafetyIssue(pattern="eval", description="eval call")
        ])
        assert sr.safe is False
        assert len(sr.issues) == 1

    def test_to_dict(self):
        sr = SafetyReport(safe=True)
        d = sr.to_dict()
        assert d["safe"] is True
        assert d["issues"] == []


class TestSafetyValidatorDeep:
    def test_safe_code(self):
        sv = SafetyValidator()
        report = sv.validate("x = 1 + 2")
        assert report.safe is True

    def test_unsafe_eval(self):
        sv = SafetyValidator()
        report = sv.validate("result = eval(user_input)")
        assert report.safe is False

    def test_unsafe_exec(self):
        sv = SafetyValidator()
        report = sv.validate("exec(code)")
        assert report.safe is False

    def test_is_safe_shorthand(self):
        sv = SafetyValidator()
        assert sv.is_safe("x = 1") is True

    def test_is_safe_unsafe(self):
        sv = SafetyValidator()
        assert sv.is_safe("eval('code')") is False

    def test_extra_patterns(self):
        sv = SafetyValidator(extra_patterns=[("DANGER", "custom danger")])
        report = sv.validate("DANGER this is bad")
        assert report.safe is False
        assert any("DANGER" in i.pattern for i in report.issues)


# ==========================================================================
#  LLM Reasoning Data Types
# ==========================================================================

from semantic_code_intelligence.llm.reasoning import (
    AskResult,
    ReviewResult,
    RefactorResult,
    SuggestResult,
)


class TestAskResult:
    def test_create(self):
        ar = AskResult(question="what?", answer="this")
        assert ar.question == "what?"
        assert ar.answer == "this"

    def test_to_dict(self):
        ar = AskResult(question="q", answer="a")
        d = ar.to_dict()
        assert d["question"] == "q"
        assert d["answer"] == "a"
        assert d["context_snippets"] == []
        assert d["usage"] == {}

    def test_with_context(self):
        ar = AskResult(question="q", answer="a",
                      context_snippets=[{"file": "x.py", "content": "code"}])
        d = ar.to_dict()
        assert len(d["context_snippets"]) == 1

    def test_with_llm_response(self):
        resp = LLMResponse(content="ans", usage={"tokens": 100})
        ar = AskResult(question="q", answer="a", llm_response=resp)
        d = ar.to_dict()
        assert d["usage"]["tokens"] == 100


class TestReviewResult:
    def test_create(self):
        rr = ReviewResult(file_path="test.py")
        assert rr.file_path == "test.py"
        assert rr.issues == []
        assert rr.summary == ""

    def test_to_dict(self):
        rr = ReviewResult(file_path="a.py", summary="looks good",
                         issues=[{"type": "style", "msg": "long line"}])
        d = rr.to_dict()
        assert d["file_path"] == "a.py"
        assert len(d["issues"]) == 1
        assert d["summary"] == "looks good"

    def test_empty_usage(self):
        d = ReviewResult(file_path="x").to_dict()
        assert d["usage"] == {}


class TestRefactorResult:
    def test_create(self):
        rr = RefactorResult(file_path="a.py", original_code="x=1",
                           refactored_code="x = 1", explanation="add spacing")
        assert rr.original_code == "x=1"
        assert rr.refactored_code == "x = 1"

    def test_to_dict(self):
        rr = RefactorResult(file_path="a.py")
        d = rr.to_dict()
        assert "file_path" in d
        assert "original_code" in d
        assert "refactored_code" in d
        assert "explanation" in d

    def test_defaults(self):
        rr = RefactorResult(file_path="b.py")
        assert rr.original_code == ""
        assert rr.refactored_code == ""
        assert rr.explanation == ""


class TestSuggestResult:
    def test_create(self):
        sr = SuggestResult(target="function_name")
        assert sr.target == "function_name"
        assert sr.suggestions == []

    def test_to_dict(self):
        sr = SuggestResult(target="x", suggestions=[{"text": "use typing"}])
        d = sr.to_dict()
        assert d["target"] == "x"
        assert len(d["suggestions"]) == 1

    def test_defaults(self):
        sr = SuggestResult(target="t")
        assert sr.llm_response is None
        assert sr.explainability == {}


# ==========================================================================
#  LLM Investigation Data Types
# ==========================================================================

from semantic_code_intelligence.llm.investigation import InvestigationResult


class TestInvestigationResult:
    def test_create(self):
        ir = InvestigationResult(question="why?", conclusion="because")
        assert ir.question == "why?"
        assert ir.conclusion == "because"

    def test_to_dict(self):
        ir = InvestigationResult(question="q", conclusion="c",
                                chain_id="ch1", total_steps=3,
                                steps=[{"action": "search", "result": "found"}])
        d = ir.to_dict()
        assert d["question"] == "q"
        assert d["conclusion"] == "c"
        assert d["chain_id"] == "ch1"
        assert d["total_steps"] == 3
        assert len(d["steps"]) == 1

    def test_defaults(self):
        ir = InvestigationResult(question="q", conclusion="c")
        assert ir.steps == []
        assert ir.chain_id == ""
        assert ir.total_steps == 0


# ==========================================================================
#  LLM Streaming
# ==========================================================================

from semantic_code_intelligence.llm.streaming import StreamEvent


class TestStreamEventDeep:
    def test_to_dict(self):
        se = StreamEvent(kind="token", content="hello")
        d = se.to_dict()
        assert d["kind"] == "token"
        assert d["content"] == "hello"

    def test_to_sse(self):
        se = StreamEvent(kind="token", content="hi")
        sse = se.to_sse()
        assert isinstance(sse, str)

    def test_metadata(self):
        se = StreamEvent(kind="done", metadata={"model": "gpt-4"})
        d = se.to_dict()
        assert d["metadata"]["model"] == "gpt-4"

    def test_default_content(self):
        se = StreamEvent(kind="start")
        assert se.content == ""

    def test_default_metadata(self):
        se = StreamEvent(kind="end")
        assert se.metadata == {}


# ==========================================================================
#  LLM Conversation
# ==========================================================================

from semantic_code_intelligence.llm.conversation import ConversationSession


class TestConversationSessionDeep:
    def test_create(self):
        cs = ConversationSession()
        assert cs.session_id != ""
        assert cs.messages == []

    def test_add_user(self):
        cs = ConversationSession()
        cs.add_user("hello")
        assert len(cs.messages) == 1
        assert cs.messages[0].role == MessageRole.USER

    def test_add_assistant(self):
        cs = ConversationSession()
        cs.add_assistant("response")
        assert cs.messages[0].role == MessageRole.ASSISTANT

    def test_add_system(self):
        cs = ConversationSession()
        cs.add_system("system prompt")
        assert cs.messages[0].role == MessageRole.SYSTEM

    def test_turn_count(self):
        cs = ConversationSession()
        assert cs.turn_count == 0
        cs.add_user("q1")
        cs.add_assistant("a1")
        assert cs.turn_count == 2  # counts individual user+assistant messages

    def test_last_message(self):
        cs = ConversationSession()
        cs.add_user("first")
        cs.add_assistant("second")
        assert cs.last_message.content == "second"

    def test_last_message_none(self):
        cs = ConversationSession()
        assert cs.last_message is None

    def test_get_messages_for_llm(self):
        cs = ConversationSession()
        cs.add_user("q1")
        cs.add_assistant("a1")
        cs.add_user("q2")
        msgs = cs.get_messages_for_llm()
        assert len(msgs) == 3

    def test_get_messages_for_llm_max_turns(self):
        cs = ConversationSession()
        for i in range(10):
            cs.add_user(f"q{i}")
            cs.add_assistant(f"a{i}")
        msgs = cs.get_messages_for_llm(max_turns=2)
        assert len(msgs) <= 4

    def test_to_dict(self):
        cs = ConversationSession()
        cs.add_user("test")
        d = cs.to_dict()
        assert "session_id" in d
        assert "messages" in d
        assert len(d["messages"]) == 1

    def test_from_dict_roundtrip(self):
        cs = ConversationSession(title="test session")
        cs.add_user("hello")
        cs.add_assistant("world")
        d = cs.to_dict()
        cs2 = ConversationSession.from_dict(d)
        assert cs2.title == "test session"
        assert len(cs2.messages) == 2


# ==========================================================================
#  Context Engine
# ==========================================================================

from semantic_code_intelligence.context.engine import (
    ContextBuilder,
    ContextWindow,
)
from semantic_code_intelligence.parsing.parser import Symbol


def _sym(name="test_fn", kind="function", file_path="test.py",
         start_line=1, end_line=5, body="def test_fn(): pass"):
    return Symbol(
        name=name, kind=kind, file_path=file_path,
        start_line=start_line, end_line=end_line,
        start_col=0, end_col=0, body=body,
    )


class TestContextWindow:
    def test_create(self):
        s = _sym()
        cw = ContextWindow(focal_symbol=s)
        assert cw.focal_symbol.name == "test_fn"

    def test_to_dict(self):
        cw = ContextWindow(focal_symbol=_sym(), related_symbols=[_sym("helper")])
        d = cw.to_dict()
        assert "focal_symbol" in d

    def test_render(self):
        cw = ContextWindow(focal_symbol=_sym(), file_content="def test_fn(): pass")
        text = cw.render()
        assert isinstance(text, str)

    def test_defaults(self):
        cw = ContextWindow(focal_symbol=_sym())
        assert cw.related_symbols == []
        assert cw.imports == []
        assert cw.file_content == ""


class TestContextBuilder:
    def test_create(self):
        cb = ContextBuilder()
        assert cb is not None

    def test_get_symbols_empty(self):
        cb = ContextBuilder()
        syms = cb.get_symbols("nonexistent.py")
        assert syms == []

    def test_get_all_symbols_empty(self):
        cb = ContextBuilder()
        syms = cb.get_all_symbols()
        assert syms == []

    def test_find_symbol_empty(self):
        cb = ContextBuilder()
        matches = cb.find_symbol("nonexistent")
        assert matches == []

    def test_index_file(self):
        cb = ContextBuilder()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py",
                                          delete=False, encoding="utf-8") as f:
            f.write("def hello():\n    pass\n\nclass World:\n    pass\n")
            f.flush()
            syms = cb.index_file(f.name)
        assert isinstance(syms, list)

    def test_find_after_index(self):
        cb = ContextBuilder()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py",
                                          delete=False, encoding="utf-8") as f:
            f.write("def my_unique_fn():\n    return 42\n")
            f.flush()
            cb.index_file(f.name)
        matches = cb.find_symbol("my_unique_fn")
        assert len(matches) >= 1
        assert matches[0].name == "my_unique_fn"


# ==========================================================================
#  Context Memory
# ==========================================================================

from semantic_code_intelligence.context.memory import (
    MemoryEntry,
    ReasoningStep,
    SessionMemory,
)


class TestMemoryEntry:
    def test_create(self):
        me = MemoryEntry(key="k1", content="stuff")
        assert me.key == "k1"
        assert me.content == "stuff"

    def test_to_dict(self):
        me = MemoryEntry(key="k", content="v", kind="fact")
        d = me.to_dict()
        assert d["key"] == "k"
        assert d["kind"] == "fact"

    def test_from_dict(self):
        d = {"key": "a", "content": "b", "kind": "general", "timestamp": 0.0, "metadata": {}}
        me = MemoryEntry.from_dict(d)
        assert me.key == "a"

    def test_default_kind(self):
        me = MemoryEntry(key="x", content="y")
        assert me.kind == "general"


class TestReasoningStep:
    def test_create(self):
        rs = ReasoningStep(step_id=1, action="search", input_text="query",
                          output_text="results")
        assert rs.step_id == 1
        assert rs.action == "search"

    def test_to_dict(self):
        rs = ReasoningStep(step_id=0, action="analyze", input_text="i",
                          output_text="o")
        d = rs.to_dict()
        assert d["step_id"] == 0
        assert d["action"] == "analyze"


class TestSessionMemory:
    def test_create(self):
        sm = SessionMemory()
        assert len(sm.entries) == 0

    def test_add(self):
        sm = SessionMemory()
        entry = sm.add("k1", "content1")
        assert isinstance(entry, MemoryEntry)
        assert len(sm.entries) == 1

    def test_search(self):
        sm = SessionMemory()
        sm.add("python", "Python is a programming language")
        sm.add("java", "Java is a compiled language")
        results = sm.search("python", limit=1)
        assert isinstance(results, list)

    def test_get_recent(self):
        sm = SessionMemory()
        for i in range(5):
            sm.add(f"k{i}", f"content{i}")
        recent = sm.get_recent(limit=3)
        assert len(recent) == 3

    def test_clear(self):
        sm = SessionMemory()
        sm.add("k", "v")
        sm.clear()
        assert len(sm.entries) == 0

    def test_start_chain(self):
        sm = SessionMemory()
        sm.start_chain("ch1")
        # No error means success

    def test_add_step(self):
        sm = SessionMemory()
        sm.start_chain("ch1")
        step = sm.add_step("ch1", "search", "query", "results")
        assert isinstance(step, ReasoningStep)

    def test_get_chain(self):
        sm = SessionMemory()
        sm.start_chain("ch1")
        sm.add_step("ch1", "search", "q", "r")
        sm.add_step("ch1", "analyze", "sym", "ctx")
        chain = sm.get_chain("ch1")
        assert len(chain) == 2

    def test_to_dict(self):
        sm = SessionMemory()
        sm.add("k", "v")
        d = sm.to_dict()
        assert isinstance(d, dict)

    def test_max_entries(self):
        sm = SessionMemory(max_entries=3)
        for i in range(5):
            sm.add(f"k{i}", f"v{i}")
        assert len(sm.entries) <= 3


# ==========================================================================
#  Analysis / AI Features
# ==========================================================================

from semantic_code_intelligence.analysis.ai_features import (
    LanguageStats,
    RepoSummary,
)


class TestLanguageStats:
    def test_create(self):
        ls = LanguageStats(language="python")
        assert ls.language == "python"
        assert ls.file_count == 0

    def test_to_dict(self):
        ls = LanguageStats(language="javascript", file_count=10, function_count=50)
        d = ls.to_dict()
        assert d["language"] == "javascript"
        assert d["file_count"] == 10
        assert d["function_count"] == 50

    def test_defaults(self):
        ls = LanguageStats(language="go")
        assert ls.class_count == 0
        assert ls.method_count == 0
        assert ls.import_count == 0
        assert ls.total_lines == 0


class TestRepoSummary:
    def test_create(self):
        rs = RepoSummary()
        assert rs.total_files == 0
        assert rs.total_symbols == 0

    def test_to_dict(self):
        rs = RepoSummary(total_files=5, total_functions=20)
        d = rs.to_dict()
        assert d["total_files"] == 5
        assert d["total_functions"] == 20

    def test_to_json(self):
        rs = RepoSummary()
        j = rs.to_json()
        parsed = json.loads(j)
        assert "total_files" in parsed

    def test_render(self):
        rs = RepoSummary(total_files=3, total_functions=10)
        text = rs.render()
        assert "3" in text
        assert "Repository Summary" in text

    def test_render_with_languages(self):
        ls = LanguageStats(language="python", file_count=5, function_count=20, class_count=3)
        rs = RepoSummary(total_files=5, languages=[ls])
        text = rs.render()
        assert "python" in text

    def test_defaults(self):
        rs = RepoSummary()
        assert rs.languages == []
        assert rs.top_functions == []
        assert rs.top_classes == []


# ==========================================================================
#  Indexing - Chunker
# ==========================================================================

from semantic_code_intelligence.indexing.chunker import (
    CodeChunk,
    chunk_code,
    detect_language as chunker_detect_language,
)


class TestCodeChunk:
    def test_create(self):
        cc = CodeChunk(file_path="a.py", content="code", start_line=1,
                      end_line=10, chunk_index=0, language="python")
        assert cc.file_path == "a.py"
        assert cc.language == "python"

    def test_is_dataclass(self):
        assert is_dataclass(CodeChunk)

    def test_fields(self):
        names = {f.name for f in fields(CodeChunk)}
        assert "file_path" in names
        assert "content" in names
        assert "start_line" in names
        assert "end_line" in names
        assert "chunk_index" in names
        assert "language" in names


class TestChunkCode:
    def test_basic(self):
        code = "line1\nline2\nline3\nline4\nline5\n" * 50
        chunks = chunk_code(code, "test.py", chunk_size=100, chunk_overlap=10)
        assert len(chunks) >= 1
        assert all(isinstance(c, CodeChunk) for c in chunks)

    def test_empty(self):
        chunks = chunk_code("", "empty.py")
        assert isinstance(chunks, list)

    def test_small_file(self):
        chunks = chunk_code("x = 1\n", "small.py")
        assert len(chunks) >= 1

    def test_chunk_index_sequential(self):
        code = "x = 1\n" * 200
        chunks = chunk_code(code, "test.py", chunk_size=50)
        if len(chunks) > 1:
            for i, c in enumerate(chunks):
                assert c.chunk_index == i

    def test_language_detection(self):
        chunks = chunk_code("def foo(): pass", "test.py")
        if chunks:
            assert chunks[0].language == "python"


class TestChunkerDetectLanguage:
    def test_python(self):
        assert chunker_detect_language("test.py") == "python"

    def test_javascript(self):
        assert chunker_detect_language("app.js") == "javascript"

    def test_typescript(self):
        assert chunker_detect_language("main.ts") == "typescript"

    def test_java(self):
        assert chunker_detect_language("Main.java") == "java"

    def test_go(self):
        assert chunker_detect_language("main.go") == "go"

    def test_rust(self):
        assert chunker_detect_language("lib.rs") == "rust"

    def test_c(self):
        assert chunker_detect_language("main.c") == "c"

    def test_cpp(self):
        assert chunker_detect_language("main.cpp") == "cpp"

    def test_ruby(self):
        assert chunker_detect_language("app.rb") == "ruby"

    def test_php(self):
        assert chunker_detect_language("index.php") == "php"

    def test_csharp(self):
        assert chunker_detect_language("Program.cs") == "csharp"

    def test_swift(self):
        assert chunker_detect_language("vc.swift") == "swift"

    def test_kotlin(self):
        assert chunker_detect_language("Main.kt") == "kotlin"

    def test_scala(self):
        assert chunker_detect_language("App.scala") == "scala"

    def test_unknown(self):
        result = chunker_detect_language("readme.md")
        assert result == "unknown" or result is None


# ==========================================================================
#  Indexing - Scanner
# ==========================================================================

from semantic_code_intelligence.indexing.scanner import (
    ScannedFile,
    compute_file_hash,
    should_ignore,
)


class TestComputeFileHash:
    def test_basic(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py",
                                          delete=False, encoding="utf-8") as f:
            f.write("x = 1\n")
            f.flush()
            h = compute_file_hash(Path(f.name))
        assert isinstance(h, str)
        assert len(h) > 0

    def test_deterministic(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py",
                                          delete=False, encoding="utf-8") as f:
            f.write("deterministic content\n")
            f.flush()
            h1 = compute_file_hash(Path(f.name))
            h2 = compute_file_hash(Path(f.name))
        assert h1 == h2


class TestShouldIgnoreDeep:
    def test_git_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git_file = root / ".git" / "config"
            git_file.parent.mkdir()
            git_file.touch()
            assert should_ignore(git_file, root, {".git"}) is True

    def test_normal_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            f = root / "src" / "main.py"
            f.parent.mkdir()
            f.touch()
            assert should_ignore(f, root, {".git"}) is False

    def test_node_modules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            f = root / "node_modules" / "pkg" / "index.js"
            f.parent.mkdir(parents=True)
            f.touch()
            assert should_ignore(f, root, {"node_modules"}) is True

    def test_pycache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            f = root / "__pycache__" / "mod.pyc"
            f.parent.mkdir()
            f.touch()
            assert should_ignore(f, root, {"__pycache__"}) is True


class TestScannedFileDeep:
    def test_create(self):
        sf = ScannedFile(path=Path("a.py"), relative_path="a.py",
                        extension=".py", size_bytes=100, content_hash="abc")
        assert sf.relative_path == "a.py"
        assert sf.extension == ".py"
        assert sf.size_bytes == 100

    def test_is_dataclass(self):
        assert is_dataclass(ScannedFile)

    def test_fields(self):
        names = {f.name for f in fields(ScannedFile)}
        assert "path" in names
        assert "relative_path" in names
        assert "extension" in names
        assert "size_bytes" in names
        assert "content_hash" in names


# ==========================================================================
#  Parsing - Symbol
# ==========================================================================

from semantic_code_intelligence.parsing.parser import (
    Symbol as ParserSymbol,
    parse_file,
    detect_language as parser_detect_language,
)


class TestParserSymbol:
    def test_create(self):
        s = _sym()
        assert s.name == "test_fn"

    def test_to_dict(self):
        s = _sym(name="foo", kind="class")
        d = s.to_dict()
        assert d["name"] == "foo"
        assert d["kind"] == "class"

    def test_parent(self):
        s = _sym()
        assert s.parent is None

    def test_with_parent(self):
        s = Symbol(name="method", kind="method", file_path="a.py",
                   start_line=5, end_line=10, start_col=4, end_col=0,
                   body="def method(): pass", parent="MyClass")
        assert s.parent == "MyClass"

    def test_decorators(self):
        s = Symbol(name="fn", kind="function", file_path="a.py",
                   start_line=1, end_line=3, start_col=0, end_col=0,
                   body="@staticmethod\ndef fn(): pass",
                   decorators=["staticmethod"])
        assert "staticmethod" in s.decorators

    def test_parameters(self):
        s = Symbol(name="fn", kind="function", file_path="a.py",
                   start_line=1, end_line=2, start_col=0, end_col=0,
                   body="def fn(x, y): pass",
                   parameters=["x", "y"])
        assert s.parameters == ["x", "y"]


class TestParseFile:
    def test_python_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py",
                                          delete=False, encoding="utf-8") as f:
            f.write("def greet(name):\n    print(f'Hello {name}')\n\nclass Greeter:\n    pass\n")
            f.flush()
            symbols = parse_file(f.name)
        assert len(symbols) >= 2
        names = [s.name for s in symbols]
        assert "greet" in names
        assert "Greeter" in names

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py",
                                          delete=False, encoding="utf-8") as f:
            f.write("")
            f.flush()
            symbols = parse_file(f.name)
        assert isinstance(symbols, list)

    def test_with_content(self):
        symbols = parse_file("virtual.py", content="class Foo:\n    pass\n")
        assert any(s.name == "Foo" for s in symbols)


class TestParserDetectLanguage:
    def test_python(self):
        assert parser_detect_language("test.py") == "python"

    def test_javascript(self):
        assert parser_detect_language("app.js") == "javascript"

    def test_none_for_unknown(self):
        result = parser_detect_language("file.xyz123")
        assert result is None or result == "unknown"


# ==========================================================================
#  Storage - Hash Store
# ==========================================================================

from semantic_code_intelligence.storage.hash_store import HashStore


class TestHashStoreExtended:
    def test_get_existing(self):
        hs = HashStore()
        hs.set("a.py", "hash1")
        assert hs.get("a.py") == "hash1"

    def test_get_missing(self):
        hs = HashStore()
        assert hs.get("nonexistent.py") is None

    def test_remove(self):
        hs = HashStore()
        hs.set("a.py", "h1")
        hs.remove("a.py")
        assert hs.get("a.py") is None
        assert hs.count == 0

    def test_remove_nonexistent(self):
        hs = HashStore()
        hs.remove("nope")  # Should not raise

    def test_overwrite(self):
        hs = HashStore()
        hs.set("a.py", "h1")
        hs.set("a.py", "h2")
        assert hs.get("a.py") == "h2"
        assert hs.count == 1

    def test_count(self):
        hs = HashStore()
        assert hs.count == 0
        hs.set("a.py", "h1")
        hs.set("b.py", "h2")
        assert hs.count == 2

    def test_has_changed_new_file(self):
        hs = HashStore()
        assert hs.has_changed("new.py", "anyhash") is True

    def test_has_changed_same_hash(self):
        hs = HashStore()
        hs.set("a.py", "h1")
        assert hs.has_changed("a.py", "h1") is False

    def test_has_changed_different_hash(self):
        hs = HashStore()
        hs.set("a.py", "h1")
        assert hs.has_changed("a.py", "h2") is True

    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            hs = HashStore()
            hs.set("a.py", "h1")
            hs.set("b.py", "h2")
            hs.save(Path(tmp))

            hs2 = HashStore.load(Path(tmp))
            assert hs2.get("a.py") == "h1"
            assert hs2.get("b.py") == "h2"
            assert hs2.count == 2


# ==========================================================================
#  Storage - Vector Store
# ==========================================================================

from semantic_code_intelligence.storage.vector_store import VectorStore
from semantic_code_intelligence.storage.vector_store import ChunkMetadata


class TestVectorStoreExtended:
    def test_create(self):
        vs = VectorStore(dimension=8)
        assert vs.size == 0
        assert vs.dimension == 8

    def test_add_and_size(self):
        import numpy as np
        vs = VectorStore(dimension=4)
        emb = np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32)
        meta = ChunkMetadata(file_path="a.py", start_line=1, end_line=2,
                             chunk_index=0, content="test", language="python")
        vs.add(emb, [meta])
        assert vs.size == 1

    def test_search_returns_list(self):
        import numpy as np
        vs = VectorStore(dimension=4)
        emb = np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32)
        meta = ChunkMetadata(file_path="a.py", start_line=1, end_line=2,
                             chunk_index=0, content="code", language="python")
        vs.add(emb, [meta])
        query = np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32)
        results = vs.search(query, top_k=1)
        assert isinstance(results, list)
        assert len(results) >= 1

    def test_search_empty(self):
        import numpy as np
        vs = VectorStore(dimension=4)
        query = np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32)
        results = vs.search(query, top_k=5)
        assert results == []

    def test_save_load(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as tmp:
            vs = VectorStore(dimension=4)
            emb = np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32)
            meta = ChunkMetadata(file_path="x.py", start_line=1, end_line=5,
                                 chunk_index=0, content="code", language="python")
            vs.add(emb, [meta])
            vs.save(Path(tmp))

            vs2 = VectorStore.load(Path(tmp))
            assert vs2.size == 1
            assert vs2.dimension == 4


# ==========================================================================
#  Workspace
# ==========================================================================

from semantic_code_intelligence.workspace import (
    RepoEntry,
    WorkspaceManifest,
    Workspace,
)


class TestRepoEntryExtended:
    def test_from_dict(self):
        d = {"name": "myrepo", "path": "/path"}
        re = RepoEntry.from_dict(d)
        assert re.name == "myrepo"
        assert re.path == "/path"

    def test_from_dict_with_extras(self):
        d = {"name": "r", "path": "/r", "last_indexed": 1.0, "file_count": 5, "vector_count": 10}
        re = RepoEntry.from_dict(d)
        assert re.last_indexed == 1.0
        assert re.file_count == 5
        assert re.vector_count == 10

    def test_roundtrip(self):
        re = RepoEntry(name="test", path="/test", file_count=3)
        d = re.to_dict()
        re2 = RepoEntry.from_dict(d)
        assert re2.name == re.name
        assert re2.file_count == re.file_count


class TestWorkspaceManifestExtended:
    def test_from_dict(self):
        d = {"version": "2.0.0", "repos": [{"name": "r1", "path": "/r1"}]}
        wm = WorkspaceManifest.from_dict(d)
        assert wm.version == "2.0.0"
        assert len(wm.repos) == 1

    def test_roundtrip(self):
        wm = WorkspaceManifest(repos=[RepoEntry(name="a", path="/a")])
        d = wm.to_dict()
        wm2 = WorkspaceManifest.from_dict(d)
        assert len(wm2.repos) == 1
        assert wm2.repos[0].name == "a"


class TestWorkspaceExtended:
    def test_properties(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Workspace(Path(tmp))
            assert ws.root == Path(tmp).resolve()
            assert ws.config_dir.name == ".codex"
            assert ws.repos_dir.name == "repos"

    def test_add_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Workspace(Path(tmp))
            entry = ws.add_repo("myrepo", Path(tmp))
            assert entry.name == "myrepo"
            assert len(ws.repos) == 1

    def test_get_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Workspace(Path(tmp))
            ws.add_repo("r1", Path(tmp))
            found = ws.get_repo("r1")
            assert found is not None
            assert found.name == "r1"

    def test_get_repo_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Workspace(Path(tmp))
            assert ws.get_repo("nonexistent") is None

    def test_add_duplicate_raises(self):
        import pytest
        with tempfile.TemporaryDirectory() as tmp:
            ws = Workspace(Path(tmp))
            ws.add_repo("r1", Path(tmp))
            with pytest.raises(ValueError):
                ws.add_repo("r1", Path(tmp))

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Workspace(Path(tmp))
            ws.add_repo("myrepo", Path(tmp))
            ws.save()

            ws2 = Workspace.load(Path(tmp))
            assert len(ws2.repos) == 1
            assert ws2.repos[0].name == "myrepo"

    def test_load_or_create(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Workspace.load_or_create(Path(tmp))
            assert ws is not None
            assert ws.root == Path(tmp).resolve()


# ==========================================================================
#  Daemon / Watcher
# ==========================================================================

from semantic_code_intelligence.daemon.watcher import FileChangeEvent, FileWatcher


class TestFileChangeEventExtended:
    def test_default_timestamp(self):
        ev = FileChangeEvent(path=Path("a.py"), relative_path="a.py",
                            change_type="created")
        assert ev.timestamp == 0.0

    def test_custom_timestamp(self):
        ev = FileChangeEvent(path=Path("b.py"), relative_path="b.py",
                            change_type="modified", timestamp=123.456)
        assert ev.timestamp == 123.456

    def test_change_types(self):
        for ct in ("created", "modified", "deleted"):
            ev = FileChangeEvent(path=Path("x"), relative_path="x", change_type=ct)
            assert ev.change_type == ct


class TestFileWatcherExtended:
    def test_not_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            fw = FileWatcher(Path(tmp))
            assert fw.is_running is False

    def test_on_change_callback(self):
        with tempfile.TemporaryDirectory() as tmp:
            fw = FileWatcher(Path(tmp))
            callback = MagicMock()
            fw.on_change(callback)
            # Callback registered, no error


# ==========================================================================
#  Semantic Chunker
# ==========================================================================

from semantic_code_intelligence.indexing.semantic_chunker import SemanticChunk


class TestSemanticChunk:
    def test_create(self):
        sc = SemanticChunk(file_path="a.py", content="def foo(): pass",
                          start_line=1, end_line=1, chunk_index=0,
                          language="python", symbol_name="foo",
                          symbol_kind="function", semantic_label="function foo")
        assert sc.symbol_name == "foo"
        assert sc.symbol_kind == "function"
        assert sc.semantic_label == "function foo"

    def test_to_dict(self):
        sc = SemanticChunk(file_path="b.py", content="class Bar: pass",
                          start_line=1, end_line=1, chunk_index=0,
                          language="python", symbol_name="Bar",
                          symbol_kind="class", semantic_label="class Bar")
        d = sc.to_dict()
        assert d["symbol_name"] == "Bar"
        assert d["symbol_kind"] == "class"
        assert d["semantic_label"] == "class Bar"

    def test_inherits_from_code_chunk(self):
        assert issubclass(SemanticChunk, CodeChunk)

    def test_defaults(self):
        sc = SemanticChunk(file_path="c.py", content="x", start_line=1,
                          end_line=1, chunk_index=0, language="python")
        assert sc.symbol_name == ""
        assert sc.symbol_kind == ""
        assert sc.parent_symbol == ""
        assert sc.parameters == []
        assert sc.semantic_label == ""


# ==========================================================================
#  Quality Module Deep Tests
# ==========================================================================

from semantic_code_intelligence.ci.quality import (
    ComplexityResult,
    compute_complexity,
)


class TestComplexityResultDeep:
    def test_create(self):
        cr = ComplexityResult(symbol_name="fn", file_path="a.py",
                             start_line=1, end_line=5, complexity=3, rating="A")
        assert cr.symbol_name == "fn"
        assert cr.complexity == 3
        assert cr.rating == "A"

    def test_to_dict(self):
        cr = ComplexityResult(symbol_name="fn", file_path="a.py",
                             start_line=1, end_line=5, complexity=15, rating="C")
        d = cr.to_dict()
        assert d["symbol_name"] == "fn"
        assert d["complexity"] == 15
        assert d["rating"] == "C"


class TestComputeComplexity:
    def test_simple_function(self):
        s = _sym(name="simple", body="def simple():\n    return 1\n")
        cr = compute_complexity(s)
        assert isinstance(cr, ComplexityResult)
        assert cr.complexity >= 1

    def test_complex_function(self):
        body = "def complex():\n"
        body += "    if True:\n        pass\n"
        body += "    for i in range(10):\n        pass\n"
        body += "    while True:\n        break\n"
        s = _sym(name="complex", body=body)
        cr = compute_complexity(s)
        assert cr.complexity >= 3


# ==========================================================================
#  CI Metrics
# ==========================================================================

from semantic_code_intelligence.ci.metrics import QualitySnapshot


class TestQualitySnapshotExtended:
    def test_to_dict(self):
        qs = QualitySnapshot(
            timestamp=1000.0,
            maintainability_index=75.0,
            total_loc=500,
            total_symbols=50,
            issue_count=0,
            files_analyzed=10,
            avg_complexity=5.0,
            comment_ratio=0.2,
        )
        d = qs.to_dict()
        assert d["maintainability_index"] == 75.0
        assert d["avg_complexity"] == 5.0
        assert d["total_loc"] == 500

    def test_is_dataclass(self):
        assert is_dataclass(QualitySnapshot)


# ==========================================================================
#  Mock Provider
# ==========================================================================

from semantic_code_intelligence.llm.mock_provider import MockProvider


class TestMockProviderExtended:
    def test_name(self):
        p = MockProvider()
        assert p.name == "mock"

    def test_is_available(self):
        p = MockProvider()
        assert p.is_available() is True

    def test_complete(self):
        p = MockProvider()
        resp = p.complete("Hello")
        assert isinstance(resp, LLMResponse)
        assert len(resp.content) > 0

    def test_chat(self):
        p = MockProvider()
        messages = [LLMMessage(role=MessageRole.USER, content="Hi")]
        resp = p.chat(messages)
        assert isinstance(resp, LLMResponse)
        assert len(resp.content) > 0

    def test_response_has_provider(self):
        p = MockProvider()
        resp = p.complete("test")
        assert resp.provider == "mock"


# ==========================================================================
#  Scalability
# ==========================================================================

from semantic_code_intelligence.scalability import BatchProcessor, ParallelScanner


class TestBatchProcessorExtended:
    def test_batch_counting(self):
        bp = BatchProcessor(batch_size=3)
        items = list(range(10))
        _, stats = bp.process(items, lambda batch: batch)
        assert stats.batches_processed >= 4  # ceil(10/3) = 4

    def test_callback(self):
        bp = BatchProcessor(batch_size=2)
        callbacks = []
        items = list(range(5))
        _, stats = bp.process(items, lambda b: b,
                             on_batch=lambda cur, tot: callbacks.append((cur, tot)))
        assert len(callbacks) >= 1

    def test_processor_failure(self):
        bp = BatchProcessor(batch_size=2)
        def failing(batch):
            raise ValueError("boom")
        results, stats = bp.process([1, 2, 3], failing)
        assert stats.items_failed >= 1


class TestParallelScannerExtended:
    def test_process_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(3):
                (Path(tmp) / f"file{i}.txt").write_text(f"content{i}")
            files = list(Path(tmp).glob("*.txt"))
            ps = ParallelScanner(max_workers=2)
            results, errors = ps.scan_and_process(files, lambda fp: fp.name)
            assert len(results) == 3
            assert errors == []

    def test_error_handling(self):
        ps = ParallelScanner(max_workers=1)
        def fail(fp):
            raise ValueError("error")
        results, errors = ps.scan_and_process([Path("fake.txt")], fail)
        assert len(errors) >= 1


# ==========================================================================
#  Plugins
# ==========================================================================

from semantic_code_intelligence.plugins import PluginHook


class TestPluginHookValues:
    def test_pre_index(self):
        assert PluginHook.PRE_INDEX.value == "pre_index"

    def test_post_index(self):
        assert PluginHook.POST_INDEX.value == "post_index"

    def test_pre_search(self):
        assert PluginHook.PRE_SEARCH.value == "pre_search"

    def test_post_search(self):
        assert PluginHook.POST_SEARCH.value == "post_search"

    def test_on_chunk(self):
        assert PluginHook.ON_CHUNK.value == "on_chunk"

    def test_count(self):
        assert len(PluginHook) >= 20


# ==========================================================================
#  Tools
# ==========================================================================

from semantic_code_intelligence.tools import (
    TOOL_DEFINITIONS,
    ToolResult,
    ToolRegistry,
)


class TestToolDefinitionsExtended:
    _names = [t["name"] for t in TOOL_DEFINITIONS]

    def test_explain_symbol(self):
        assert "explain_symbol" in self._names

    def test_get_call_graph(self):
        assert "get_call_graph" in self._names

    def test_get_dependencies(self):
        assert "get_dependencies" in self._names

    def test_find_references(self):
        assert "find_references" in self._names

    def test_get_context(self):
        assert "get_context" in self._names

    def test_summarize_repo(self):
        assert "summarize_repo" in self._names

    def test_explain_file(self):
        assert "explain_file" in self._names

    def test_search(self):
        assert "semantic_search" in self._names

    def test_each_has_description(self):
        for defn in TOOL_DEFINITIONS:
            assert "description" in defn, f"Tool {defn['name']} missing description"

    def test_each_has_parameters(self):
        for defn in TOOL_DEFINITIONS:
            assert "parameters" in defn, f"Tool {defn['name']} missing parameters"


class TestToolResultExtended:
    def test_success(self):
        tr = ToolResult(tool_name="search", success=True, data={"results": []})
        assert tr.tool_name == "search"
        assert tr.success is True

    def test_failure(self):
        tr = ToolResult(tool_name="explain", success=False, error="not found")
        assert tr.success is False
        assert tr.error == "not found"

    def test_to_dict(self):
        tr = ToolResult(tool_name="test", success=True, data={"x": 1})
        d = tr.to_dict()
        assert d["tool"] == "test"
        assert d["success"] is True


class TestToolRegistryExtended:
    def test_create(self):
        with tempfile.TemporaryDirectory() as tmp:
            tr = ToolRegistry(Path(tmp))
            assert tr is not None

    def test_tool_definitions(self):
        with tempfile.TemporaryDirectory() as tmp:
            tr = ToolRegistry(Path(tmp))
            defns = tr.tool_definitions
            assert isinstance(defns, list)
            assert len(defns) >= 8


# ==========================================================================
#  Version
# ==========================================================================

from semantic_code_intelligence import __version__, __app_name__


class TestVersionExtended:
    def test_semver(self):
        parts = __version__.split(".")
        assert len(parts) == 3
        for p in parts:
            assert p.isdigit()

    def test_app_name_value(self):
        assert __app_name__ == "codex"

    def test_version_not_empty(self):
        assert len(__version__) >= 5


# ==========================================================================
#  Bridge Context Provider
# ==========================================================================

from semantic_code_intelligence.bridge.context_provider import ContextProvider


class TestContextProvider:
    def test_create(self):
        with tempfile.TemporaryDirectory() as tmp:
            cp = ContextProvider(Path(tmp))
            assert cp is not None

    def test_repo_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            cp = ContextProvider(Path(tmp))
            summary = cp.context_for_repo()
            assert isinstance(summary, dict)


# ==========================================================================
#  Services - Indexing
# ==========================================================================

from semantic_code_intelligence.services.indexing_service import IndexingResult


class TestIndexingResult:
    def test_create(self):
        ir = IndexingResult()
        assert ir is not None

    def test_repr(self):
        ir = IndexingResult()
        r = repr(ir)
        assert isinstance(r, str)


# ==========================================================================
#  Services - Search  
# ==========================================================================

from semantic_code_intelligence.services.search_service import SearchResult


class TestSearchResultExtended:
    def test_create(self):
        sr = SearchResult(file_path="a.py", start_line=1, end_line=5,
                         language="python", content="code", score=0.95,
                         chunk_index=0)
        assert sr.file_path == "a.py"
        assert sr.score == 0.95

    def test_to_dict(self):
        sr = SearchResult(file_path="b.py", start_line=10, end_line=20,
                         language="js", content="function()", score=0.8,
                         chunk_index=1)
        d = sr.to_dict()
        assert d["file_path"] == "b.py"
        assert d["start_line"] == 10
        assert d["score"] == 0.8

    def test_is_dataclass(self):
        assert is_dataclass(SearchResult)


# ==========================================================================
#  CI Hooks
# ==========================================================================

from semantic_code_intelligence.ci.hooks import run_precommit_check


class TestPrecommitCheck:
    def test_no_git_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            # No .git dir — just verify it's callable
            assert callable(run_precommit_check)


# ==========================================================================
#  CI Templates
# ==========================================================================

from semantic_code_intelligence.ci.templates import get_template, generate_precommit_config


class TestCITemplates:
    def test_get_analysis_template(self):
        tmpl = get_template("analysis")
        assert isinstance(tmpl, str)
        assert len(tmpl) > 0

    def test_get_safety_template(self):
        tmpl = get_template("safety")
        assert isinstance(tmpl, str)
        assert len(tmpl) > 0

    def test_get_precommit_template(self):
        tmpl = get_template("precommit")
        assert isinstance(tmpl, str)

    def test_get_template_invalid(self):
        import pytest
        with pytest.raises(KeyError):
            get_template("nonexistent_template_xyz")

    def test_generate_precommit_config(self):
        config = generate_precommit_config()
        assert isinstance(config, str)


# ==========================================================================
#  CI PR Review
# ==========================================================================

from semantic_code_intelligence.ci.pr import FileChange, ChangeSummary, RiskScore, PRReport


class TestFileChange:
    def test_is_dataclass(self):
        assert is_dataclass(FileChange)


class TestChangeSummary:
    def test_is_dataclass(self):
        assert is_dataclass(ChangeSummary)


class TestRiskScore:
    def test_is_dataclass(self):
        assert is_dataclass(RiskScore)


class TestPRReport:
    def test_is_dataclass(self):
        assert is_dataclass(PRReport)


# ==========================================================================
#  Docs generators
# ==========================================================================

from semantic_code_intelligence.docs import generate_all_docs


class TestDocsGenerationExtended:
    def test_returns_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = generate_all_docs(Path(tmp))
            assert isinstance(result, list)

    def test_files_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = generate_all_docs(Path(tmp))
            for name in result:
                assert (Path(tmp) / name).exists()

    def test_files_are_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = generate_all_docs(Path(tmp))
            for name in result:
                assert name.endswith(".md")
