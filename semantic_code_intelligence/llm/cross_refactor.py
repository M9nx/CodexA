"""Cross-repo refactoring suggestions.

Compares symbols across workspace repositories to find:
- Duplicate or near-duplicate logic that could be shared
- Inconsistent API patterns across repos
- Refactoring opportunities informed by cross-repo dependency analysis

Uses the Workspace multi-repo search and per-repo ContextBuilder to
gather symbols, then asks the LLM for actionable suggestions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from semantic_code_intelligence.context.engine import ContextBuilder
from semantic_code_intelligence.llm.provider import LLMMessage, LLMProvider, MessageRole
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("llm.cross_refactor")


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class CrossRepoMatch:
    """A pair of similar symbols found across repos."""

    repo_a: str
    symbol_a: str
    file_a: str
    repo_b: str
    symbol_b: str
    file_b: str
    similarity_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo_a": self.repo_a,
            "symbol_a": self.symbol_a,
            "file_a": self.file_a,
            "repo_b": self.repo_b,
            "symbol_b": self.symbol_b,
            "file_b": self.file_b,
            "similarity_note": self.similarity_note,
        }


@dataclass
class CrossRefactorResult:
    """Result of cross-repo refactoring analysis."""

    repos_analyzed: list[str] = field(default_factory=list)
    total_symbols: int = 0
    matches: list[CrossRepoMatch] = field(default_factory=list)
    suggestions: list[dict[str, Any]] = field(default_factory=list)
    llm_used: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "repos_analyzed": self.repos_analyzed,
            "total_symbols": self.total_symbols,
            "matches": [m.to_dict() for m in self.matches],
            "suggestions": self.suggestions,
            "llm_used": self.llm_used,
        }


# ---------------------------------------------------------------------------
# Cross-repo symbol collection
# ---------------------------------------------------------------------------

def _collect_repo_symbols(
    repo_name: str,
    repo_path: Path,
) -> list[dict[str, Any]]:
    """Index a single repo and return a flat list of symbol dicts."""
    builder = ContextBuilder()
    from semantic_code_intelligence.config.settings import load_config
    from semantic_code_intelligence.indexing.scanner import scan_repository

    config = load_config(repo_path)
    for sf in scan_repository(repo_path, config.index):
        try:
            builder.index_file(str(repo_path / sf.relative_path))
        except Exception:
            logger.debug("Skip unindexable file: %s", sf.relative_path)

    symbols = builder.get_all_symbols()
    result: list[dict[str, Any]] = []
    for s in symbols:
        if s.kind in ("function", "method", "class"):
            result.append({
                "repo": repo_name,
                "name": s.name,
                "kind": s.kind,
                "file": s.file_path,
                "lines": s.end_line - s.start_line + 1,
                "body": s.body[:600] if s.body else "",
            })
    return result


# ---------------------------------------------------------------------------
# Duplicate detection across repos
# ---------------------------------------------------------------------------

def _find_cross_duplicates(
    repo_symbols: dict[str, list[dict[str, Any]]],
    threshold: float = 0.70,
    min_lines: int = 4,
) -> list[CrossRepoMatch]:
    """Find near-duplicate symbols across different repos via trigram Jaccard."""
    from semantic_code_intelligence.ci.quality import _normalize_body, _trigram_set, _jaccard

    # Build (repo, sym_dict, trigrams) for each candidate
    candidates: list[tuple[str, dict[str, Any], set[str]]] = []
    for repo_name, syms in repo_symbols.items():
        for s in syms:
            if s["lines"] < min_lines or not s["body"].strip():
                continue
            norm = _normalize_body(s["body"])
            tris = _trigram_set(norm)
            if tris:
                candidates.append((repo_name, s, tris))

    matches: list[CrossRepoMatch] = []
    seen: set[tuple[str, str]] = set()

    for i, (repo_a, sym_a, tris_a) in enumerate(candidates):
        for j in range(i + 1, len(candidates)):
            repo_b, sym_b, tris_b = candidates[j]
            if repo_a == repo_b:
                continue  # Only cross-repo
            sim = _jaccard(tris_a, tris_b)
            if sim >= threshold:
                _sorted = sorted([f"{repo_a}:{sym_a['name']}", f"{repo_b}:{sym_b['name']}"])
                pair_key = (_sorted[0], _sorted[1])
                if pair_key in seen:
                    continue
                seen.add(pair_key)
                matches.append(CrossRepoMatch(
                    repo_a=repo_a,
                    symbol_a=sym_a["name"],
                    file_a=sym_a["file"],
                    repo_b=repo_b,
                    symbol_b=sym_b["name"],
                    file_b=sym_b["file"],
                    similarity_note=f"Jaccard similarity: {sim:.2f}",
                ))

    matches.sort(key=lambda m: m.similarity_note, reverse=True)
    return matches


# ---------------------------------------------------------------------------
# LLM-powered suggestion generation
# ---------------------------------------------------------------------------

def _generate_suggestions(
    matches: list[CrossRepoMatch],
    repo_symbols: dict[str, list[dict[str, Any]]],
    provider: LLMProvider,
) -> list[dict[str, Any]]:
    """Ask the LLM for refactoring suggestions based on cross-repo matches."""
    if not matches:
        return []

    # Build a concise summary for the LLM
    match_text = ""
    for m in matches[:10]:
        match_text += (
            f"- {m.repo_a}/{m.symbol_a} ({m.file_a}) ↔ "
            f"{m.repo_b}/{m.symbol_b} ({m.file_b}) — {m.similarity_note}\n"
        )

    repo_summary = ""
    for repo, syms in repo_symbols.items():
        repo_summary += f"- {repo}: {len(syms)} symbols\n"

    system = (
        "You are CodexA, a cross-repository refactoring advisor. Given a list of "
        "similar symbols found across different repositories, suggest refactoring "
        "opportunities. Return a JSON list of objects with keys: 'title', "
        "'description', 'affected_repos', 'priority' (high/medium/low)."
    )
    user_msg = (
        f"Repositories:\n{repo_summary}\n"
        f"Similar symbols across repos:\n{match_text}\n"
        "Suggest refactoring strategies (e.g., extract shared lib, unify APIs)."
    )

    import json

    messages = [
        LLMMessage(role=MessageRole.SYSTEM, content=system),
        LLMMessage(role=MessageRole.USER, content=user_msg),
    ]
    resp = provider.chat(messages)

    try:
        parsed = json.loads(resp.content)
        if isinstance(parsed, list):
            result: list[dict[str, Any]] = parsed
            return result
        if isinstance(parsed, dict) and "suggestions" in parsed:
            suggestions: list[dict[str, Any]] = parsed["suggestions"]
            return suggestions
    except (json.JSONDecodeError, TypeError):
        pass

    return [{"title": "See raw analysis", "description": resp.content, "priority": "medium"}]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_cross_repo(
    workspace_root: Path,
    *,
    provider: LLMProvider | None = None,
    threshold: float = 0.70,
    repos: list[str] | None = None,
) -> CrossRefactorResult:
    """Analyse a workspace for cross-repo refactoring opportunities.

    Args:
        workspace_root: Workspace root containing ``.codexa/workspace.json``.
        provider: Optional LLM provider for generating suggestions.
        threshold: Jaccard similarity threshold for duplicate detection.
        repos: Restrict to these repo names. None = all registered repos.

    Returns:
        CrossRefactorResult with matches and optional LLM suggestions.
    """
    from semantic_code_intelligence.workspace import Workspace

    try:
        ws = Workspace.load(workspace_root)
    except FileNotFoundError:
        return CrossRefactorResult()

    targets = repos or [r.name for r in ws.repos]
    repo_symbols: dict[str, list[dict[str, Any]]] = {}

    for rname in targets:
        entry = ws.get_repo(rname)
        if entry is None:
            continue
        repo_symbols[rname] = _collect_repo_symbols(rname, Path(entry.path))

    total_symbols = sum(len(s) for s in repo_symbols.values())
    matches = _find_cross_duplicates(repo_symbols, threshold=threshold)

    suggestions: list[dict[str, Any]] = []
    llm_used = False
    if provider and matches:
        suggestions = _generate_suggestions(matches, repo_symbols, provider)
        llm_used = True

    return CrossRefactorResult(
        repos_analyzed=targets,
        total_symbols=total_symbols,
        matches=matches,
        suggestions=suggestions,
        llm_used=llm_used,
    )
