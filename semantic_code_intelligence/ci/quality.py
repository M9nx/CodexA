"""Code quality analyzers — dead code, duplicate logic, complexity, security.

All analyzers operate on parsed ``Symbol`` lists and raw file content,
returning structured reports that are both human-readable (via Rich) and
machine-parsable (``to_dict()`` → JSON).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from semantic_code_intelligence.parsing.parser import Symbol, parse_file
from semantic_code_intelligence.context.engine import CallGraph, ContextBuilder
from semantic_code_intelligence.llm.safety import SafetyValidator, SafetyReport
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("ci.quality")

# ── Cyclomatic complexity ────────────────────────────────────────────

# Decision keywords/patterns that increase cyclomatic complexity.
_DECISION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bif\b"),
    re.compile(r"\belif\b"),
    re.compile(r"\belse\s+if\b"),
    re.compile(r"\bfor\b"),
    re.compile(r"\bwhile\b"),
    re.compile(r"\bcatch\b"),
    re.compile(r"\bexcept\b"),
    re.compile(r"\bcase\b"),
    re.compile(r"\b\?\?"),        # null coalescing
    re.compile(r"\?\s*\."),       # optional chaining counts mildly
    re.compile(r"\band\b"),
    re.compile(r"\bor\b"),
    re.compile(r"&&"),
    re.compile(r"\|\|"),
]


@dataclass
class ComplexityResult:
    """Cyclomatic complexity measurement for a single symbol."""

    symbol_name: str
    file_path: str
    start_line: int
    end_line: int
    complexity: int
    rating: str  # "low", "moderate", "high", "very_high"

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol_name": self.symbol_name,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "complexity": self.complexity,
            "rating": self.rating,
        }


def _rate_complexity(score: int) -> str:
    if score <= 5:
        return "low"
    if score <= 10:
        return "moderate"
    if score <= 20:
        return "high"
    return "very_high"


def compute_complexity(symbol: Symbol) -> ComplexityResult:
    """Compute cyclomatic complexity for a single symbol.

    Counts decision points in the symbol body and returns a structured result.
    """
    body = symbol.body or ""
    score = 1  # base path
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("//"):
            continue
        for pattern in _DECISION_PATTERNS:
            if pattern.search(stripped):
                score += 1

    return ComplexityResult(
        symbol_name=symbol.name,
        file_path=symbol.file_path,
        start_line=symbol.start_line,
        end_line=symbol.end_line,
        complexity=score,
        rating=_rate_complexity(score),
    )


def analyze_complexity(
    symbols: list[Symbol],
    *,
    threshold: int = 10,
) -> list[ComplexityResult]:
    """Analyze all function/method symbols and return those above *threshold*."""
    results: list[ComplexityResult] = []
    for sym in symbols:
        if sym.kind not in ("function", "method"):
            continue
        cr = compute_complexity(sym)
        if cr.complexity >= threshold:
            results.append(cr)
    results.sort(key=lambda r: r.complexity, reverse=True)
    return results


# ── Dead code detection ──────────────────────────────────────────────

@dataclass
class DeadCodeResult:
    """A symbol suspected of being unreferenced."""

    symbol_name: str
    kind: str
    file_path: str
    start_line: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol_name": self.symbol_name,
            "kind": self.kind,
            "file_path": self.file_path,
            "start_line": self.start_line,
        }


# Names that are conventionally always reachable.
_ENTRY_NAMES: set[str] = {
    "main", "__init__", "__new__", "__del__", "__str__", "__repr__",
    "__enter__", "__exit__", "__call__", "__getattr__", "__setattr__",
    "__getitem__", "__setitem__", "__len__", "__iter__", "__next__",
    "__eq__", "__hash__", "__lt__", "__le__", "__gt__", "__ge__",
    "__add__", "__sub__", "__mul__", "__truediv__",
    "setUp", "tearDown", "setUpClass", "tearDownClass",
    "setup_method", "teardown_method",
    "create_plugin",  # CodexA plugin factory
}

# Prefix patterns that indicate entry points / framework hooks.
_ENTRY_PREFIXES: tuple[str, ...] = (
    "test_", "Test",  # pytest
)


def detect_dead_code(
    symbols: list[Symbol],
    call_graph: CallGraph | None = None,
) -> list[DeadCodeResult]:
    """Detect functions/methods that are never referenced.

    Uses the ``CallGraph`` callee set to determine reachability.
    Symbols whose names match known entry-point patterns are excluded.
    """
    if not symbols:
        return []

    # Build reference set from call graph edges
    referenced: set[str] = set()
    if call_graph:
        for edge in call_graph.edges:
            callee = edge.callee
            if ":" in callee:
                callee = callee.rsplit(":", 1)[-1]
            referenced.add(callee)

    # Also scan raw bodies for name mentions (lightweight fallback)
    all_bodies = "\n".join(s.body for s in symbols if s.body)
    name_set = {s.name for s in symbols}

    results: list[DeadCodeResult] = []
    for sym in symbols:
        if sym.kind not in ("function", "method", "class"):
            continue
        if sym.name in _ENTRY_NAMES:
            continue
        if any(sym.name.startswith(p) for p in _ENTRY_PREFIXES):
            continue
        # Private dunder-style names starting and ending with __ handled above
        if sym.name.startswith("_") and sym.name.endswith("_"):
            continue

        # Check call graph
        if sym.name in referenced:
            continue

        # Heuristic: name appears in other symbols' bodies
        # We count occurrences of the name in all bodies excluding the symbol itself.
        body_without_self = all_bodies.replace(sym.body, "", 1) if sym.body else all_bodies
        if re.search(rf"\b{re.escape(sym.name)}\b", body_without_self):
            continue

        results.append(DeadCodeResult(
            symbol_name=sym.name,
            kind=sym.kind,
            file_path=sym.file_path,
            start_line=sym.start_line,
        ))

    return results


# ── Duplicate logic detection ────────────────────────────────────────

@dataclass
class DuplicateResult:
    """A pair of symbols with similar bodies."""

    symbol_a: str
    file_a: str
    line_a: int
    symbol_b: str
    file_b: str
    line_b: int
    similarity: float  # 0.0 – 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol_a": self.symbol_a,
            "file_a": self.file_a,
            "line_a": self.line_a,
            "symbol_b": self.symbol_b,
            "file_b": self.file_b,
            "line_b": self.line_b,
            "similarity": round(self.similarity, 3),
        }


def _normalize_body(body: str) -> str:
    """Strip whitespace and comments for comparison."""
    lines: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("//"):
            continue
        lines.append(stripped)
    return "\n".join(lines)


def _trigram_set(text: str) -> set[str]:
    """Return the set of 3-character shingles in *text*."""
    if len(text) < 3:
        return {text} if text else set()
    return {text[i : i + 3] for i in range(len(text) - 2)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def detect_duplicates(
    symbols: list[Symbol],
    *,
    threshold: float = 0.75,
    min_lines: int = 4,
) -> list[DuplicateResult]:
    """Detect similar function/method bodies using trigram Jaccard similarity.

    Only compares symbols whose normalised body has at least *min_lines* lines.
    Pairs with similarity ≥ *threshold* are returned.
    """
    # Pre-filter
    candidates: list[tuple[Symbol, str, set[str]]] = []
    for sym in symbols:
        if sym.kind not in ("function", "method"):
            continue
        norm = _normalize_body(sym.body or "")
        if norm.count("\n") + 1 < min_lines:
            continue
        candidates.append((sym, norm, _trigram_set(norm)))

    results: list[DuplicateResult] = []
    seen: set[tuple[str, str]] = set()

    for i, (sym_a, _norm_a, tri_a) in enumerate(candidates):
        for j in range(i + 1, len(candidates)):
            sym_b, _norm_b, tri_b = candidates[j]
            key = (f"{sym_a.file_path}:{sym_a.name}", f"{sym_b.file_path}:{sym_b.name}")
            if key in seen:
                continue
            sim = _jaccard(tri_a, tri_b)
            if sim >= threshold:
                seen.add(key)
                results.append(DuplicateResult(
                    symbol_a=sym_a.name,
                    file_a=sym_a.file_path,
                    line_a=sym_a.start_line,
                    symbol_b=sym_b.name,
                    file_b=sym_b.file_path,
                    line_b=sym_b.start_line,
                    similarity=sim,
                ))

    results.sort(key=lambda r: r.similarity, reverse=True)
    return results


# ── Quality report (aggregate) ───────────────────────────────────────

@dataclass
class QualityReport:
    """Aggregate quality report for a project or file set."""

    files_analyzed: int = 0
    symbol_count: int = 0
    complexity_issues: list[ComplexityResult] = field(default_factory=list)
    dead_code: list[DeadCodeResult] = field(default_factory=list)
    duplicates: list[DuplicateResult] = field(default_factory=list)
    safety: SafetyReport | None = None

    @property
    def issue_count(self) -> int:
        n = len(self.complexity_issues) + len(self.dead_code) + len(self.duplicates)
        if self.safety:
            n += len(self.safety.issues)
        return n

    def to_dict(self) -> dict[str, Any]:
        return {
            "files_analyzed": self.files_analyzed,
            "symbol_count": self.symbol_count,
            "issue_count": self.issue_count,
            "complexity_issues": [c.to_dict() for c in self.complexity_issues],
            "dead_code": [d.to_dict() for d in self.dead_code],
            "duplicates": [d.to_dict() for d in self.duplicates],
            "safety": self.safety.to_dict() if self.safety else None,
        }


def analyze_project(
    project_root: Path,
    *,
    file_paths: list[str] | None = None,
    complexity_threshold: int = 10,
    duplicate_threshold: float = 0.75,
    run_safety: bool = True,
) -> QualityReport:
    """Run all quality analyzers on a project or a subset of files.

    Args:
        project_root: Repository root directory.
        file_paths: Optional specific file list. If *None*, indexes the whole project.
        complexity_threshold: Minimum complexity score to report.
        duplicate_threshold: Minimum Jaccard similarity to report as duplicate.
        run_safety: Whether to run the safety validator.

    Returns:
        Aggregated ``QualityReport``.
    """
    builder = ContextBuilder()
    all_symbols: list[Symbol] = []
    all_code = ""

    if file_paths:
        files = [str(Path(f).resolve()) for f in file_paths]
    else:
        # Walk project for supported files
        from semantic_code_intelligence.parsing.parser import EXTENSION_TO_LANGUAGE
        files = []
        for f in project_root.rglob("*"):
            if f.is_file() and f.suffix in EXTENSION_TO_LANGUAGE:
                # Skip hidden dirs, .codex, __pycache__, node_modules
                parts = f.relative_to(project_root).parts
                if any(p.startswith(".") or p in ("__pycache__", "node_modules", ".codex") for p in parts):
                    continue
                files.append(str(f))

    for fpath in files:
        try:
            syms = builder.index_file(fpath)
            all_symbols.extend(syms)
            content = Path(fpath).read_text(encoding="utf-8", errors="replace")
            all_code += content + "\n"
        except Exception as exc:
            logger.debug("Skipping %s: %s", fpath, exc)

    # Call graph for dead-code analysis
    call_graph = CallGraph()
    call_graph.build(all_symbols)

    report = QualityReport(
        files_analyzed=len(files),
        symbol_count=len(all_symbols),
    )

    report.complexity_issues = analyze_complexity(
        all_symbols, threshold=complexity_threshold
    )
    report.dead_code = detect_dead_code(all_symbols, call_graph=call_graph)
    report.duplicates = detect_duplicates(
        all_symbols, threshold=duplicate_threshold
    )

    if run_safety:
        validator = SafetyValidator()
        report.safety = validator.validate(all_code)

    return report
