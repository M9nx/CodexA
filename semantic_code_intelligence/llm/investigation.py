"""Autonomous investigation chains — multi-step code exploration.

An **InvestigationChain** drives an iterative loop:

1. Formulate a search query from the user's question.
2. Gather context (semantic search, symbol lookup, dependency analysis).
3. Ask the LLM to evaluate what was found and decide the next action.
4. Repeat until the LLM signals "conclude" or a step limit is reached.

Each step is recorded as a ``ReasoningStep`` in ``SessionMemory`` so
the chain is fully transparent and reproducible.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from semantic_code_intelligence.context.engine import ContextBuilder
from semantic_code_intelligence.context.memory import ReasoningStep, SessionMemory
from semantic_code_intelligence.llm.provider import LLMMessage, LLMProvider, MessageRole
from semantic_code_intelligence.llm.rag import RAGPipeline, RetrievalStrategy
from semantic_code_intelligence.services.search_service import search_codebase
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("llm.investigation")


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class InvestigationResult:
    """Final result of an investigation chain."""

    question: str
    conclusion: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    chain_id: str = ""
    total_steps: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Action helpers
# ---------------------------------------------------------------------------

def _action_search(query: str, project_root: Path, top_k: int = 5, *, rag: RAGPipeline | None = None) -> str:
    """Run search and return a text summary. Uses RAG pipeline when available."""
    if rag is not None:
        try:
            ctx = rag.retrieve_and_assemble(
                query,
                strategy=RetrievalStrategy.HYBRID,
                top_k=top_k,
                include_repo_summary=False,
            )
            if ctx.citations:
                parts: list[str] = []
                for chunk, cite in zip(ctx.chunks, ctx.citations):
                    content = chunk.get("content", chunk.get("chunk", ""))[:500]
                    parts.append(
                        f"{cite.label()} [{cite.file_path}:{cite.start_line}-{cite.end_line}] "
                        f"(score {cite.score:.2f})\n{content}"
                    )
                return "\n---\n".join(parts)
        except Exception:
            pass  # Fall back to direct search

    try:
        results = search_codebase(query, project_root, top_k=top_k, threshold=0.2)
        if not results:
            return "No results found."
        parts_fallback: list[str] = []
        for r in results:
            d = r.to_dict()
            parts_fallback.append(
                f"[{d.get('file_path', '?')}] (score {d.get('score', 0):.2f})\n"
                f"{d.get('content', d.get('chunk', ''))[:500]}"
            )
        return "\n---\n".join(parts_fallback)
    except Exception:
        return "Semantic search unavailable."


def _action_analyze(symbol_name: str, builder: ContextBuilder) -> str:
    """Look up a symbol and return its context."""
    matches = builder.find_symbol(symbol_name)
    if not matches:
        return f"Symbol '{symbol_name}' not found."
    parts: list[str] = []
    for s in matches[:3]:
        parts.append(
            f"{s.kind} {s.name} in {s.file_path} (L{s.start_line}-{s.end_line})\n"
            f"{s.body[:400]}"
        )
    return "\n---\n".join(parts)


def _action_deps(file_path: str, builder: ContextBuilder, project_root: Path) -> str:
    """Gather dependency info for a file."""
    from semantic_code_intelligence.context.engine import DependencyMap

    dm = DependencyMap()
    full = project_root / file_path if not Path(file_path).is_absolute() else Path(file_path)
    if full.exists():
        deps = dm.add_file(str(full))
        parts = [f"{d.import_text} (L{d.line})" for d in deps]
        return "Dependencies: " + ", ".join(parts) if parts else "No dependencies found."
    return f"File not found: {file_path}"


# ---------------------------------------------------------------------------
# Investigation chain
# ---------------------------------------------------------------------------

_PLANNER_SYSTEM = """\
You are CodexA, an autonomous code investigation agent. Your task is to
answer the user's question by systematically exploring the codebase.

On each turn you will receive context gathered from the previous action.
Respond with a JSON object with exactly these keys:
- "thought": one sentence about what you learned and what to do next
- "action": one of "search", "analyze", "deps", "conclude"
- "action_input": the argument for the action (search query, symbol name, file path, or final answer)

When you have enough information, use action "conclude" and put your
final answer in "action_input".
"""


class InvestigationChain:
    """Drives an iterative search-analyze-conclude loop via LLM."""

    def __init__(
        self,
        provider: LLMProvider,
        project_root: Path,
        *,
        builder: ContextBuilder | None = None,
        memory: SessionMemory | None = None,
        max_steps: int = 6,
    ) -> None:
        self._provider = provider
        self._root = project_root.resolve()
        self._builder = builder or ContextBuilder()
        self._memory = memory or SessionMemory()
        self._max_steps = max_steps
        self._indexed = False
        self._rag = RAGPipeline(self._root, budget_tokens=2000)

    def _ensure_indexed(self) -> None:
        if self._indexed:
            return
        from semantic_code_intelligence.config.settings import load_config
        from semantic_code_intelligence.indexing.scanner import scan_repository

        config = load_config(self._root)
        for sf in scan_repository(self._root, config.index):
            try:
                self._builder.index_file(str(self._root / sf.relative_path))
            except Exception:
                logger.debug("Skip unindexable file: %s", sf.relative_path)
        self._indexed = True

    def _run_action(self, action: str, action_input: str) -> str:
        """Execute an action and return its text output."""
        if action == "search":
            return _action_search(action_input, self._root, rag=self._rag)
        elif action == "analyze":
            self._ensure_indexed()
            return _action_analyze(action_input, self._builder)
        elif action == "deps":
            self._ensure_indexed()
            return _action_deps(action_input, self._builder, self._root)
        return action_input

    def _parse_plan(self, text: str) -> dict[str, str]:
        """Parse the LLM planner response into {thought, action, action_input}."""
        # Try JSON first
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and "action" in parsed:
                return {
                    "thought": str(parsed.get("thought", "")),
                    "action": str(parsed.get("action", "conclude")),
                    "action_input": str(parsed.get("action_input", text)),
                }
        except (json.JSONDecodeError, TypeError):
            pass
        # Fallback — treat entire response as conclusion
        return {"thought": "", "action": "conclude", "action_input": text}

    def _conclude_streaming(self, messages: list[LLMMessage]) -> str:
        """Stream the final conclusion tokens to stdout, return accumulated text."""
        from semantic_code_intelligence.llm.streaming import stream_chat

        gen = stream_chat(self._provider, messages)
        accumulated = ""
        import sys
        for event in gen:
            if event.kind == "token":
                accumulated += event.content
                sys.stdout.write(event.content)
                sys.stdout.flush()
        sys.stdout.write("\n")
        return accumulated

    def investigate(self, question: str, *, stream_conclusion: bool = False) -> InvestigationResult:
        """Run a full investigation loop and return the result.

        Args:
            question: The question to investigate.
            stream_conclusion: If True, yield the conclusion token-by-token
                via ``stream_chat`` and print incrementally.
        """
        chain_id = uuid.uuid4().hex[:10]
        self._memory.start_chain(chain_id)

        messages: list[LLMMessage] = [
            LLMMessage(role=MessageRole.SYSTEM, content=_PLANNER_SYSTEM),
            LLMMessage(role=MessageRole.USER, content=f"Question: {question}"),
        ]

        steps: list[dict[str, Any]] = []
        conclusion = ""

        for step_num in range(1, self._max_steps + 1):
            # Ask the planner
            resp = self._provider.chat(messages)
            plan = self._parse_plan(resp.content)

            action = plan["action"]
            action_input = plan["action_input"]
            thought = plan["thought"]

            if action == "conclude":
                conclusion = action_input
                self._memory.add_step(chain_id, "conclude", question, conclusion)
                steps.append({
                    "step": step_num,
                    "action": "conclude",
                    "thought": thought,
                    "output": conclusion,
                })
                break

            # Execute the action
            output = self._run_action(action, action_input)
            self._memory.add_step(chain_id, action, action_input, output)
            steps.append({
                "step": step_num,
                "action": action,
                "action_input": action_input,
                "thought": thought,
                "output": output[:500],
            })

            # Feed result back to planner
            messages.append(LLMMessage(role=MessageRole.ASSISTANT, content=resp.content))
            messages.append(LLMMessage(
                role=MessageRole.USER,
                content=f"Action result:\n{output[:2000]}",
            ))
        else:
            # Exhausted steps — ask for final conclusion
            messages.append(LLMMessage(
                role=MessageRole.USER,
                content="You have reached the step limit. Please provide your best conclusion now.",
            ))
            if stream_conclusion:
                conclusion = self._conclude_streaming(messages)
            else:
                resp = self._provider.chat(messages)
            conclusion = resp.content
            self._memory.add_step(chain_id, "conclude", "forced", conclusion)

        return InvestigationResult(
            question=question,
            conclusion=conclusion,
            steps=steps,
            chain_id=chain_id,
            total_steps=len(steps),
        )
