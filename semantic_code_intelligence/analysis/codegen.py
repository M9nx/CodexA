"""Code generation — RAG-grounded scaffolding using codebase context.

Generates code scaffolds, tests, and documentation grounded in the
actual codebase via retrieval-augmented generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("codegen")


@dataclass
class CodeGenRequest:
    """A request for code generation."""

    prompt: str
    kind: str = "scaffold"  # scaffold, test, docstring, refactor
    target_file: str | None = None
    target_symbol: str | None = None
    language: str | None = None
    max_context_chunks: int = 5

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "kind": self.kind,
            "target_file": self.target_file,
            "target_symbol": self.target_symbol,
            "language": self.language,
            "max_context_chunks": self.max_context_chunks,
        }


@dataclass
class CodeGenResult:
    """Result of a code generation request."""

    generated_code: str = ""
    context_used: list[dict[str, Any]] = field(default_factory=list)
    model_used: str = ""
    prompt_tokens: int = 0
    success: bool = True
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_code": self.generated_code,
            "context_used": self.context_used,
            "model_used": self.model_used,
            "prompt_tokens": self.prompt_tokens,
            "success": self.success,
            "error": self.error,
        }


class CodeGenerator:
    """RAG-grounded code generator.

    Retrieves relevant context from the indexed codebase, assembles a
    prompt, and sends it to the configured LLM provider.
    """

    def __init__(self, project_root: str) -> None:
        from pathlib import Path
        self._project_root = Path(project_root).resolve()

    def generate(self, request: CodeGenRequest) -> CodeGenResult:
        """Generate code using RAG context + LLM."""
        from pathlib import Path

        from semantic_code_intelligence.config.settings import load_config
        from semantic_code_intelligence.services.search_service import search_codebase

        config = load_config(self._project_root)
        result = CodeGenResult()

        # Step 1: Retrieve relevant context
        try:
            search_results = search_codebase(
                query=request.prompt,
                project_root=self._project_root,
                top_k=request.max_context_chunks,
                mode="hybrid",
            )
            context_chunks = []
            for sr in search_results:
                context_chunks.append({
                    "file_path": sr.file_path,
                    "start_line": sr.start_line,
                    "content": sr.content[:500],
                    "score": round(sr.score, 3),
                })
            result.context_used = context_chunks
        except Exception as exc:
            logger.warning("Context retrieval failed: %s", exc)
            context_chunks = []

        # Step 2: Build the prompt
        context_text = ""
        for chunk in context_chunks:
            context_text += f"\n--- {chunk['file_path']}:{chunk['start_line']} ---\n"
            context_text += chunk["content"] + "\n"

        system_prompt = (
            "You are a code generator. Generate code based on the user's request, "
            "grounded in the provided codebase context. Follow the existing code style "
            "and patterns. Only output the code, no explanations."
        )

        user_prompt = f"Request: {request.prompt}\n"
        if request.kind:
            user_prompt += f"Type: {request.kind}\n"
        if request.target_file:
            user_prompt += f"Target file: {request.target_file}\n"
        if request.language:
            user_prompt += f"Language: {request.language}\n"
        if context_text:
            user_prompt += f"\nRelevant codebase context:\n{context_text}"

        # Step 3: Send to LLM
        try:
            from semantic_code_intelligence.llm.providers import get_provider

            provider = get_provider(config.llm)
            response = provider.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=config.llm.max_tokens,
            )
            result.generated_code = response.content
            result.model_used = config.llm.model
            result.prompt_tokens = response.prompt_tokens
        except Exception as exc:
            result.success = False
            result.error = str(exc)
            logger.error("Code generation failed: %s", exc)

        return result
