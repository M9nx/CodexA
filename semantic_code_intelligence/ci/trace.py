"""Symbol trace tool — traces execution relationships between symbols.

Builds upstream callers and downstream callees for a given symbol,
with transitive traversal and cross-file relationship tracking.
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any

from semantic_code_intelligence.context.engine import CallGraph
from semantic_code_intelligence.parsing.parser import Symbol
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("ci.trace")


@dataclass
class TraceNode:
    """A node in a symbol trace — a caller or callee."""

    name: str
    file_path: str
    kind: str  # "function", "method", "class"
    depth: int  # hops from source; negative=upstream, positive=downstream

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TraceEdge:
    """A directed edge in the trace graph."""

    caller: str
    callee: str
    file_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TraceResult:
    """Result of tracing a symbol's execution relationships."""

    target: str
    target_file: str
    upstream: list[TraceNode] = field(default_factory=list)
    downstream: list[TraceNode] = field(default_factory=list)
    edges: list[TraceEdge] = field(default_factory=list)
    max_upstream_depth: int = 0
    max_downstream_depth: int = 0

    @property
    def total_nodes(self) -> int:
        return len(self.upstream) + len(self.downstream)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "target_file": self.target_file,
            "upstream": [n.to_dict() for n in self.upstream],
            "downstream": [n.to_dict() for n in self.downstream],
            "edges": [e.to_dict() for e in self.edges],
            "max_upstream_depth": self.max_upstream_depth,
            "max_downstream_depth": self.max_downstream_depth,
            "total_nodes": self.total_nodes,
        }


def trace_symbol(
    target: str,
    symbols: list[Symbol],
    call_graph: CallGraph,
    *,
    max_depth: int = 5,
) -> TraceResult:
    """Trace execution relationships for a symbol.

    Walks both upstream (callers) and downstream (callees) in the call graph.

    Args:
        target: Symbol name to trace.
        symbols: All parsed symbols.
        call_graph: Pre-built call graph.
        max_depth: Maximum BFS traversal depth in each direction.

    Returns:
        TraceResult with upstream/downstream nodes and edges.
    """
    # Resolve target to a known symbol
    target_syms = [s for s in symbols if s.name == target and s.kind != "import"]
    if not target_syms:
        return TraceResult(target=target, target_file="")

    target_sym = target_syms[0]
    target_key = f"{target_sym.file_path}:{target_sym.name}"

    # Build name → Symbol index
    sym_by_name: dict[str, Symbol] = {}
    for s in symbols:
        if s.kind != "import":
            sym_by_name.setdefault(s.name, s)

    # Reverse caller_key → Symbol
    sym_by_key: dict[str, Symbol] = {}
    for s in symbols:
        if s.kind in ("function", "method", "class"):
            sym_by_key[f"{s.file_path}:{s.name}"] = s

    upstream: list[TraceNode] = []
    downstream: list[TraceNode] = []
    edges: list[TraceEdge] = []
    max_up = 0
    max_down = 0

    # ── Upstream: who calls target? ──────────────────────────────
    visited_up: set[str] = {target}
    queue_up: deque[tuple[str, int]] = deque()  # (symbol_name, depth)

    for edge in call_graph.callers_of(target):
        parts = edge.caller.rsplit(":", 1)
        caller_name = parts[-1] if len(parts) == 2 else edge.caller
        if caller_name not in visited_up:
            visited_up.add(caller_name)
            queue_up.append((caller_name, 1))
            edges.append(TraceEdge(
                caller=caller_name,
                callee=target,
                file_path=edge.file_path,
            ))

    while queue_up:
        sym_name, depth = queue_up.popleft()
        sym = sym_by_name.get(sym_name)
        if sym is None:
            continue

        upstream.append(TraceNode(
            name=sym.name,
            file_path=sym.file_path,
            kind=sym.kind,
            depth=-depth,  # negative = upstream
        ))
        max_up = max(max_up, depth)

        if depth < max_depth:
            for edge in call_graph.callers_of(sym.name):
                parts = edge.caller.rsplit(":", 1)
                cname = parts[-1] if len(parts) == 2 else edge.caller
                if cname not in visited_up:
                    visited_up.add(cname)
                    queue_up.append((cname, depth + 1))
                    edges.append(TraceEdge(
                        caller=cname,
                        callee=sym.name,
                        file_path=edge.file_path,
                    ))

    # ── Downstream: what does target call? ────────────────────────
    visited_down: set[str] = {target_key}
    queue_down: deque[tuple[str, str, int]] = deque()  # (caller_key, symbol_name, depth)

    for edge in call_graph.callees_of(target_key):
        callee_sym = sym_by_name.get(edge.callee)
        callee_key = f"{callee_sym.file_path}:{callee_sym.name}" if callee_sym else edge.callee
        if callee_key not in visited_down:
            visited_down.add(callee_key)
            queue_down.append((callee_key, edge.callee, 1))
            edges.append(TraceEdge(
                caller=target,
                callee=edge.callee,
                file_path=edge.file_path,
            ))

    while queue_down:
        caller_key, sym_name, depth = queue_down.popleft()
        sym = sym_by_name.get(sym_name)
        if sym is None:
            continue

        downstream.append(TraceNode(
            name=sym.name,
            file_path=sym.file_path,
            kind=sym.kind,
            depth=depth,
        ))
        max_down = max(max_down, depth)

        if depth < max_depth:
            key = f"{sym.file_path}:{sym.name}"
            for edge in call_graph.callees_of(key):
                callee_sym = sym_by_name.get(edge.callee)
                callee_key = f"{callee_sym.file_path}:{callee_sym.name}" if callee_sym else edge.callee
                if callee_key not in visited_down:
                    visited_down.add(callee_key)
                    queue_down.append((callee_key, edge.callee, depth + 1))
                    edges.append(TraceEdge(
                        caller=sym.name,
                        callee=edge.callee,
                        file_path=edge.file_path,
                    ))

    return TraceResult(
        target=target,
        target_file=target_sym.file_path,
        upstream=upstream,
        downstream=downstream,
        edges=edges,
        max_upstream_depth=max_up,
        max_downstream_depth=max_down,
    )
