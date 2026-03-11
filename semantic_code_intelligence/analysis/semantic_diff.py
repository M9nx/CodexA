"""Semantic diff — AST-level diff that understands code structure.

Detects renamed symbols, moved functions, signature changes, and body
edits, separating structural changes from cosmetic ones (whitespace,
comment-only edits).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from semantic_code_intelligence.parsing.parser import Symbol, parse_file
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("semantic_diff")


class ChangeKind(str, Enum):
    """Kind of semantic change detected."""
    ADDED = "added"
    REMOVED = "removed"
    RENAMED = "renamed"
    MOVED = "moved"
    SIGNATURE_CHANGED = "signature_changed"
    BODY_CHANGED = "body_changed"
    COSMETIC = "cosmetic"  # whitespace/comment only


@dataclass
class SemanticChange:
    """A single semantic change between two versions of code."""

    kind: ChangeKind
    symbol_name: str
    symbol_kind: str = ""
    file_path: str = ""
    old_name: str | None = None
    old_file: str | None = None
    old_signature: str | None = None
    new_signature: str | None = None
    details: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "kind": self.kind.value,
            "symbol_name": self.symbol_name,
            "symbol_kind": self.symbol_kind,
            "file_path": self.file_path,
        }
        if self.old_name:
            d["old_name"] = self.old_name
        if self.old_file:
            d["old_file"] = self.old_file
        if self.old_signature:
            d["old_signature"] = self.old_signature
        if self.new_signature:
            d["new_signature"] = self.new_signature
        if self.details:
            d["details"] = self.details
        return d


@dataclass
class SemanticDiffResult:
    """Result of comparing two versions of a file or directory."""

    changes: list[SemanticChange] = field(default_factory=list)
    structural_changes: int = 0
    cosmetic_changes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "changes": [c.to_dict() for c in self.changes],
            "structural_changes": self.structural_changes,
            "cosmetic_changes": self.cosmetic_changes,
            "total_changes": len(self.changes),
        }


def _normalize_body(body: str) -> str:
    """Normalize code body by stripping whitespace and comments for comparison."""
    lines = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("//"):
            lines.append(stripped)
    return "\n".join(lines)


def _extract_signature(sym: Symbol) -> str:
    """Extract the signature (first line) of a symbol."""
    first_line = sym.body.split("\n")[0].strip() if sym.body else ""
    return first_line


def diff_symbols(
    old_symbols: list[Symbol],
    new_symbols: list[Symbol],
    file_path: str = "",
) -> SemanticDiffResult:
    """Compare two lists of symbols and produce a semantic diff.

    Detects: additions, removals, renames, signature changes, body changes,
    and cosmetic-only changes.
    """
    result = SemanticDiffResult()

    old_by_name: dict[str, Symbol] = {s.name: s for s in old_symbols if s.kind != "import"}
    new_by_name: dict[str, Symbol] = {s.name: s for s in new_symbols if s.kind != "import"}

    old_names = set(old_by_name.keys())
    new_names = set(new_by_name.keys())

    # Check for renames: removed + added with same normalized body
    removed = old_names - new_names
    added = new_names - old_names
    rename_pairs: set[tuple[str, str]] = set()

    for old_name in list(removed):
        old_body = _normalize_body(old_by_name[old_name].body)
        for new_name in list(added):
            new_body = _normalize_body(new_by_name[new_name].body)
            if old_body == new_body and old_body:
                rename_pairs.add((old_name, new_name))
                removed.discard(old_name)
                added.discard(new_name)
                break

    # Emit renames
    for old_name, new_name in rename_pairs:
        result.changes.append(SemanticChange(
            kind=ChangeKind.RENAMED,
            symbol_name=new_name,
            symbol_kind=new_by_name[new_name].kind,
            file_path=file_path,
            old_name=old_name,
        ))
        result.structural_changes += 1

    # Emit removals
    for name in sorted(removed):
        result.changes.append(SemanticChange(
            kind=ChangeKind.REMOVED,
            symbol_name=name,
            symbol_kind=old_by_name[name].kind,
            file_path=file_path,
        ))
        result.structural_changes += 1

    # Emit additions
    for name in sorted(added):
        result.changes.append(SemanticChange(
            kind=ChangeKind.ADDED,
            symbol_name=name,
            symbol_kind=new_by_name[name].kind,
            file_path=file_path,
        ))
        result.structural_changes += 1

    # Compare symbols present in both versions
    common = old_names & new_names
    for name in sorted(common):
        old_sym = old_by_name[name]
        new_sym = new_by_name[name]

        old_sig = _extract_signature(old_sym)
        new_sig = _extract_signature(new_sym)
        old_body = _normalize_body(old_sym.body)
        new_body = _normalize_body(new_sym.body)

        if old_sig != new_sig:
            result.changes.append(SemanticChange(
                kind=ChangeKind.SIGNATURE_CHANGED,
                symbol_name=name,
                symbol_kind=new_sym.kind,
                file_path=file_path,
                old_signature=old_sig,
                new_signature=new_sig,
            ))
            result.structural_changes += 1
        elif old_body != new_body:
            result.changes.append(SemanticChange(
                kind=ChangeKind.BODY_CHANGED,
                symbol_name=name,
                symbol_kind=new_sym.kind,
                file_path=file_path,
            ))
            result.structural_changes += 1
        elif old_sym.body != new_sym.body:
            # Body differs only in whitespace/comments
            result.changes.append(SemanticChange(
                kind=ChangeKind.COSMETIC,
                symbol_name=name,
                symbol_kind=new_sym.kind,
                file_path=file_path,
                details="whitespace or comment changes only",
            ))
            result.cosmetic_changes += 1

    return result


def diff_files(old_path: str, old_content: str, new_path: str, new_content: str) -> SemanticDiffResult:
    """Compute a semantic diff between two file versions.

    If the file was moved (different paths, same content), detects that.
    Otherwise, parses both versions and compares symbols.
    """
    old_symbols = parse_file(old_path, old_content)
    new_symbols = parse_file(new_path, new_content)

    result = diff_symbols(old_symbols, new_symbols, file_path=new_path)

    # Detect file-level move
    if old_path != new_path:
        for change in result.changes:
            if change.kind == ChangeKind.COSMETIC or change.kind == ChangeKind.BODY_CHANGED:
                change.old_file = old_path

    return result
