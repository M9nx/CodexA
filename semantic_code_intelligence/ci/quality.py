"""Code quality analyzers — dead code, duplicate logic, complexity, security.

All analyzers operate on parsed ``Symbol`` lists and raw file content,
returning structured reports that are both human-readable (via Rich) and
machine-parsable (``to_dict()`` → JSON).

Uses `radon <https://radon.readthedocs.io/>`_ for AST-based cyclomatic
complexity analysis on Python files, with a regex fallback for other languages.
Optionally integrates `bandit <https://bandit.readthedocs.io/>`_ for Python
security linting.
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

# ── Radon (optional — used for Python AST-based complexity) ──────────

try:
    from radon.complexity import cc_visit
    from radon.metrics import mi_visit

    _HAS_RADON = True
except ImportError:  # pragma: no cover
    _HAS_RADON = False

# ── Cyclomatic complexity ────────────────────────────────────────────

# Decision keywords/patterns — used as fallback for non-Python files.
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


def _compute_complexity_regex(symbol: Symbol) -> ComplexityResult:
    """Regex-based fallback for non-Python files."""
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


def _compute_complexity_radon(symbol: Symbol) -> ComplexityResult:
    """AST-based complexity via radon for Python symbols."""
    body = symbol.body or ""

    # If the body is not a complete function/class definition, wrap it so
    # radon can parse it.  Symbols store the body content which may or may
    # not include the ``def`` line.
    code = body
    if not body.lstrip().startswith(("def ", "class ", "async def ")):
        # Indent all body lines and wrap in a temporary function
        indented = "\n".join("    " + ln for ln in body.splitlines())
        code = f"def _wrapper():\n{indented}\n"

    try:
        results = cc_visit(code)
        # Sum complexities from all top-level blocks (usually 1 function).
        score = max((r.complexity for r in results), default=1)
    except SyntaxError:
        # If radon can't parse the snippet, fall back to regex
        return _compute_complexity_regex(symbol)

    return ComplexityResult(
        symbol_name=symbol.name,
        file_path=symbol.file_path,
        start_line=symbol.start_line,
        end_line=symbol.end_line,
        complexity=score,
        rating=_rate_complexity(score),
    )


def compute_complexity(symbol: Symbol) -> ComplexityResult:
    """Compute cyclomatic complexity for a single symbol.

    Uses radon's AST analysis for Python files, falling back to regex-based
    counting for other languages.
    """
    if _HAS_RADON and symbol.file_path.endswith(".py"):
        return _compute_complexity_radon(symbol)
    return _compute_complexity_regex(symbol)


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


# ── Bandit security linting (optional) ───────────────────────────────

try:
    from bandit.core import manager as _bandit_manager
    from bandit.core import config as _bandit_config

    _HAS_BANDIT = True
except ImportError:  # pragma: no cover
    _HAS_BANDIT = False


@dataclass
class BanditIssue:
    """A security issue found by Bandit."""

    test_id: str
    severity: str       # LOW / MEDIUM / HIGH
    confidence: str     # LOW / MEDIUM / HIGH
    text: str
    file_path: str
    line: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_id": self.test_id,
            "severity": self.severity,
            "confidence": self.confidence,
            "text": self.text,
            "file_path": self.file_path,
            "line": self.line,
        }


def run_bandit_scan(file_paths: list[str]) -> list[BanditIssue]:
    """Run Bandit static analysis on the given Python files.

    Returns an empty list when Bandit is not installed or when no
    Python files are provided.
    """
    if not _HAS_BANDIT:
        return []

    py_files = [f for f in file_paths if f.endswith(".py")]
    if not py_files:
        return []

    try:
        conf = _bandit_config.BanditConfig()
        mgr = _bandit_manager.BanditManager(conf, "file")
        mgr.discover_files(py_files)
        mgr.run_tests()
        return [
            BanditIssue(
                test_id=iss.test_id,
                severity=str(iss.severity).upper(),
                confidence=str(iss.confidence).upper(),
                text=iss.text,
                file_path=iss.fname,
                line=iss.lineno,
            )
            for iss in mgr.get_issue_list()
        ]
    except Exception as exc:
        logger.debug("Bandit scan failed: %s", exc)
        return []


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
    bandit_issues: list[BanditIssue] = field(default_factory=list)
    maintainability_index: float | None = None

    @property
    def issue_count(self) -> int:
        n = len(self.complexity_issues) + len(self.dead_code) + len(self.duplicates)
        n += len(self.bandit_issues)
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
            "bandit_issues": [b.to_dict() for b in self.bandit_issues],
            "maintainability_index": round(self.maintainability_index, 2) if self.maintainability_index is not None else None,
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
                # Skip hidden dirs, .codexa, __pycache__, node_modules
                parts = f.relative_to(project_root).parts
                if any(p.startswith(".") or p in ("__pycache__", "node_modules", ".codexa") for p in parts):
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

    # Bandit security scan (Python files only)
    report.bandit_issues = run_bandit_scan(files)

    # Maintainability index (average across Python files)
    if _HAS_RADON:
        mi_scores: list[float] = []
        for fpath in files:
            if not fpath.endswith(".py"):
                continue
            try:
                code = Path(fpath).read_text(encoding="utf-8", errors="replace")
                score = mi_visit(code, True)
                if isinstance(score, (int, float)):
                    mi_scores.append(float(score))
            except Exception:
                pass
        if mi_scores:
            report.maintainability_index = sum(mi_scores) / len(mi_scores)

    if run_safety:
        validator = SafetyValidator()
        report.safety = validator.validate(all_code)

    return report
