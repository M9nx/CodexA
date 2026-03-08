"""Impact analysis engine — predicts blast radius of code changes.

Given a file path or symbol name, determines which parts of the codebase
are directly and transitively affected via call graph edges, dependency
map imports, and symbol cross-references.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from semantic_code_intelligence.context.engine import (
    CallGraph,
    DependencyMap,
)
from semantic_code_intelligence.parsing.parser import Symbol
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("ci.impact")


@dataclass
class AffectedSymbol:
    """A symbol affected by a change."""

    name: str
    file_path: str
    kind: str  # "function", "method", "class"
    relationship: str  # "direct_caller", "transitive_caller", "import_dep"
    depth: int  # hops from source

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "file_path": self.file_path,
            "kind": self.kind,
            "relationship": self.relationship,
            "depth": self.depth,
        }


@dataclass
class AffectedModule:
    """A module (file) transitively affected by a change."""

    file_path: str
    relationship: str  # "imports_target", "transitive_import", "contains_caller"
    depth: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "relationship": self.relationship,
            "depth": self.depth,
        }


@dataclass
class DependencyChain:
    """A single dependency chain explaining why a module is affected."""

    path: list[str]  # list of file/symbol names forming the chain

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path}


@dataclass
class ImpactReport:
    """Result of impact analysis."""

    target: str
    target_kind: str  # "file" or "symbol"
    direct_symbols: list[AffectedSymbol] = field(default_factory=list)
    transitive_symbols: list[AffectedSymbol] = field(default_factory=list)
    affected_modules: list[AffectedModule] = field(default_factory=list)
    chains: list[DependencyChain] = field(default_factory=list)

    @property
    def total_affected(self) -> int:
        return len(self.direct_symbols) + len(self.transitive_symbols)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "target_kind": self.target_kind,
            "direct_symbols": [s.to_dict() for s in self.direct_symbols],
            "transitive_symbols": [s.to_dict() for s in self.transitive_symbols],
            "affected_modules": [m.to_dict() for m in self.affected_modules],
            "chains": [c.to_dict() for c in self.chains],
            "total_affected": self.total_affected,
        }


def _resolve_target_symbols(
    target: str,
    symbols: list[Symbol],
    project_root: Path,
) -> tuple[str, list[Symbol]]:
    """Resolve a target (file path or symbol name) to matching symbols.

    Returns (target_kind, matched_symbols).
    """
    root = project_root.resolve()

    # Check if it looks like a file path
    candidate = Path(target)
    if not candidate.is_absolute():
        candidate = root / target

    if candidate.exists() and candidate.is_file():
        resolved = str(candidate.resolve())
        matched = [s for s in symbols if str(Path(s.file_path).resolve()) == resolved]
        return "file", matched

    # Treat as symbol name
    matched = [s for s in symbols if s.name == target and s.kind != "import"]
    return "symbol", matched


def analyze_impact(
    target: str,
    symbols: list[Symbol],
    call_graph: CallGraph,
    dep_map: DependencyMap,
    project_root: Path,
    *,
    max_depth: int = 5,
) -> ImpactReport:
    """Analyze the impact of modifying a file or symbol.

    BFS over call graph callers and dependency map importers to find
    the full blast radius of a change.
    """
    target_kind, target_syms = _resolve_target_symbols(target, symbols, project_root)

    if not target_syms:
        return ImpactReport(target=target, target_kind=target_kind)

    # Collect seed symbol names
    seed_names: set[str] = set()
    seed_files: set[str] = set()
    for s in target_syms:
        seed_names.add(s.name)
        seed_files.add(s.file_path)

    # Build symbol-name → Symbol lookup
    sym_lookup: dict[str, Symbol] = {}
    for s in symbols:
        if s.kind != "import":
            sym_lookup.setdefault(s.name, s)

    # ── BFS over call graph (callers of target symbols) ──────────
    direct: list[AffectedSymbol] = []
    transitive: list[AffectedSymbol] = []
    visited_callers: set[str] = set()  # caller keys visited
    queue: deque[tuple[str, int, str]] = deque()  # (symbol_name, depth, relationship)

    for name in seed_names:
        for edge in call_graph.callers_of(name):
            caller_key = edge.caller
            if caller_key in visited_callers:
                continue
            visited_callers.add(caller_key)
            # Parse caller_key "file:name"
            parts = caller_key.rsplit(":", 1)
            caller_name = parts[-1] if len(parts) == 2 else caller_key
            queue.append((caller_name, 1, "direct_caller"))

    while queue:
        sym_name, depth, relationship = queue.popleft()
        sym = sym_lookup.get(sym_name)
        if sym is None:
            continue

        affected = AffectedSymbol(
            name=sym.name,
            file_path=sym.file_path,
            kind=sym.kind,
            relationship=relationship,
            depth=depth,
        )
        if depth == 1:
            direct.append(affected)
        else:
            transitive.append(affected)

        # Continue BFS if within depth limit
        if depth < max_depth:
            for edge in call_graph.callers_of(sym.name):
                if edge.caller not in visited_callers:
                    visited_callers.add(edge.caller)
                    parts = edge.caller.rsplit(":", 1)
                    cname = parts[-1] if len(parts) == 2 else edge.caller
                    queue.append((cname, depth + 1, "transitive_caller"))

    # ── Module-level impact via dependency map ────────────────────
    affected_modules: list[AffectedModule] = []
    visited_modules: set[str] = set()

    for fpath in seed_files:
        # Find the module name from file path
        p = Path(fpath)
        module_name = p.stem

        dependents = dep_map.get_dependents(module_name)
        for dep in dependents:
            if dep.source_file not in visited_modules and dep.source_file not in seed_files:
                visited_modules.add(dep.source_file)
                affected_modules.append(AffectedModule(
                    file_path=dep.source_file,
                    relationship="imports_target",
                    depth=1,
                ))

    # Add files containing direct callers
    for s in direct:
        if s.file_path not in visited_modules and s.file_path not in seed_files:
            visited_modules.add(s.file_path)
            affected_modules.append(AffectedModule(
                file_path=s.file_path,
                relationship="contains_caller",
                depth=1,
            ))

    # ── Build dependency chains (top 10) ─────────────────────────
    chains: list[DependencyChain] = []
    for s in direct[:10]:
        chain = [target, s.name]
        chains.append(DependencyChain(path=chain))

    for s in transitive[:5]:
        chain = [target, "...", s.name]
        chains.append(DependencyChain(path=chain))

    return ImpactReport(
        target=target,
        target_kind=target_kind,
        direct_symbols=direct,
        transitive_symbols=transitive,
        affected_modules=affected_modules,
        chains=chains,
    )
