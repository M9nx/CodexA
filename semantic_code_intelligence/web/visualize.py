"""Visualization generators — Mermaid-compatible text graphs.

All functions return plain strings (Mermaid diagram markup) so they can
be rendered by any compatible viewer, embedded in Markdown, or displayed
in the terminal as-is.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def render_call_graph(
    edges: list[dict[str, Any]],
    *,
    title: str = "Call Graph",
    direction: str = "LR",
) -> str:
    """Render a call graph as a Mermaid flowchart.

    Args:
        edges: List of dicts with ``caller``, ``callee``, ``file_path``.
        title: Optional graph title.
        direction: Mermaid direction (``LR``, ``TD``, ``TB``, ``RL``).

    Returns:
        Mermaid flowchart source text.
    """
    lines: list[str] = [f"---", f"title: {title}", f"---", f"flowchart {direction}"]

    nodes: set[str] = set()
    for edge in edges:
        raw_caller = edge.get("caller", "")
        raw_callee = edge.get("callee", "")
        if not raw_caller or not raw_callee:
            continue
        caller = _sanitize_id(raw_caller)
        callee = _sanitize_id(raw_callee)
        nodes.add(caller)
        nodes.add(callee)

        caller_label = _short_label(edge.get("caller", ""))
        callee_label = _short_label(edge.get("callee", ""))
        lines.append(f"    {caller}[\"{caller_label}\"] --> {callee}[\"{callee_label}\"]")

    if not nodes:
        lines.append("    empty[\"No call edges found\"]")

    return "\n".join(lines)


def render_dependency_graph(
    deps: dict[str, Any],
    *,
    title: str = "Dependency Graph",
    direction: str = "TD",
) -> str:
    """Render file-level dependencies as a Mermaid flowchart.

    Args:
        deps: Dict from ContextProvider.get_dependencies() or similar,
              expected to have a ``dependencies`` key with a list of
              ``{source_file, import_text}`` dicts.
        title: Optional graph title.
        direction: Mermaid direction.

    Returns:
        Mermaid flowchart source text.
    """
    lines: list[str] = [f"---", f"title: {title}", f"---", f"flowchart {direction}"]

    dep_list = deps.get("dependencies", [])
    if isinstance(dep_list, dict):
        # Some formats nest per-file
        flat: list[dict[str, str]] = []
        for _file, entries in dep_list.items():
            if isinstance(entries, list):
                flat.extend(entries)
        dep_list = flat

    seen: set[str] = set()
    for entry in dep_list:
        src = entry.get("source_file", "")
        imp = entry.get("import_text", "")
        if not src or not imp:
            continue

        src_id = _sanitize_id(src)
        imp_id = _sanitize_id(imp)
        edge_key = f"{src_id}-->{imp_id}"
        if edge_key in seen:
            continue
        seen.add(edge_key)

        src_label = Path(src).name
        imp_label = imp.split()[-1] if " " in imp else imp
        # Truncate long import labels
        if len(imp_label) > 40:
            imp_label = imp_label[:37] + "..."
        lines.append(f"    {src_id}[\"{src_label}\"] --> {imp_id}[\"{imp_label}\"]")

    if not seen:
        lines.append("    empty[\"No dependencies found\"]")

    return "\n".join(lines)


def render_workspace_graph(
    repos: list[dict[str, Any]],
    *,
    title: str = "Workspace Repositories",
) -> str:
    """Render workspace repositories as a Mermaid diagram.

    Args:
        repos: List of repo entry dicts with ``name``, ``path``,
               ``file_count``, ``vector_count``.
        title: Optional graph title.

    Returns:
        Mermaid graph source text.
    """
    lines: list[str] = [f"---", f"title: {title}", f"---", "flowchart TD"]

    ws_id = "workspace"
    lines.append(f"    {ws_id}((\"Workspace\"))")

    if not repos:
        lines.append(f"    {ws_id} --> none[\"No repositories\"]")
        return "\n".join(lines)

    for repo in repos:
        name = repo.get("name", "unknown")
        rid = _sanitize_id(f"repo_{name}")
        file_count = repo.get("file_count", "?")
        vec_count = repo.get("vector_count", "?")
        label = f"{name}\\n{file_count} files, {vec_count} vectors"
        lines.append(f"    {ws_id} --> {rid}[\"{label}\"]")

    return "\n".join(lines)


def render_symbol_map(
    symbols: list[dict[str, Any]],
    *,
    title: str = "Symbol Map",
    file_path: str = "",
) -> str:
    """Render a file's symbols as a Mermaid class diagram.

    Args:
        symbols: List of symbol dicts with ``name``, ``kind``, ``parent``.
        title: Optional graph title.
        file_path: Source file being mapped.

    Returns:
        Mermaid class diagram source text.
    """
    lines: list[str] = [f"---", f"title: {title}", f"---", "classDiagram"]

    classes: dict[str, list[str]] = {}  # class_name -> member list
    standalone_functions: list[str] = []

    for sym in symbols:
        kind = sym.get("kind", "")
        name = sym.get("name", "")
        parent = sym.get("parent", "")

        if kind == "class":
            classes.setdefault(name, [])
        elif kind == "method" and parent:
            classes.setdefault(parent, [])
            classes[parent].append(f"+{name}()")
        elif kind == "function":
            standalone_functions.append(name)
        elif kind == "import":
            continue  # skip imports in class diagram

    for cls_name, members in classes.items():
        lines.append(f"    class {_sanitize_class_id(cls_name)} {{")
        for member in members:
            lines.append(f"        {member}")
        lines.append("    }")

    if standalone_functions:
        lines.append(f"    class Functions {{")
        for fn in standalone_functions:
            lines.append(f"        +{fn}()")
        lines.append("    }")

    if not classes and not standalone_functions:
        lines.append("    class Empty {")
        lines.append("        No symbols found")
        lines.append("    }")

    return "\n".join(lines)


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _sanitize_id(text: str) -> str:
    """Convert arbitrary text into a Mermaid-safe node ID."""
    # Take just the filename/symbol portion
    if ":" in text:
        text = text.rsplit(":", 1)[-1]
    text = Path(text).stem if "/" in text or "\\" in text else text
    # Replace non-alphanumeric chars with underscores
    return re.sub(r"[^a-zA-Z0-9_]", "_", text).strip("_")[:60] or "node"


def _sanitize_class_id(text: str) -> str:
    """Convert a class name to a Mermaid-safe class diagram ID."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", text).strip("_")[:60] or "Unknown"


def _short_label(text: str) -> str:
    """Extract a short display label from a caller/callee key."""
    if ":" in text:
        parts = text.rsplit(":", 1)
        fname = Path(parts[0]).name
        return f"{fname}:{parts[1]}"
    return text
