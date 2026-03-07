"""AST-aware semantic chunker — splits code along structural boundaries.

Uses tree-sitter parsed symbols to produce chunks aligned to function,
class, and method boundaries rather than arbitrary line counts.  Falls
back to the line-based chunker for unsupported languages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from semantic_code_intelligence.indexing.chunker import (
    CodeChunk,
    chunk_code,
    detect_language,
)
from semantic_code_intelligence.parsing.parser import (
    Symbol,
    parse_file,
    detect_language as detect_ts_language,
)
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("indexing.semantic_chunker")


@dataclass
class SemanticChunk(CodeChunk):
    """A chunk with additional semantic metadata."""

    symbol_name: str = ""
    symbol_kind: str = ""      # "function", "class", "method", "module_header", "block"
    parent_symbol: str = ""
    parameters: list[str] = field(default_factory=list)
    semantic_label: str = ""   # human-readable label for the chunk

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "content": self.content,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "chunk_index": self.chunk_index,
            "language": self.language,
            "symbol_name": self.symbol_name,
            "symbol_kind": self.symbol_kind,
            "parent_symbol": self.parent_symbol,
            "parameters": self.parameters,
            "semantic_label": self.semantic_label,
        }


def _build_semantic_label(chunk: "SemanticChunk") -> str:
    """Build a human-readable label for embedding prepend."""
    parts: list[str] = []
    if chunk.language and chunk.language != "unknown":
        parts.append(f"[{chunk.language}]")
    if chunk.symbol_kind:
        parts.append(chunk.symbol_kind)
    if chunk.parent_symbol:
        parts.append(f"{chunk.parent_symbol}.{chunk.symbol_name}")
    elif chunk.symbol_name:
        parts.append(chunk.symbol_name)
    if chunk.parameters:
        parts.append(f"({', '.join(chunk.parameters)})")
    return " ".join(parts)


def _symbols_to_chunks(
    symbols: list[Symbol],
    content: str,
    file_path: str,
    language: str,
    max_chunk_size: int = 512,
) -> list[SemanticChunk]:
    """Convert parsed symbols into semantic chunks.

    Large symbols that exceed max_chunk_size are sub-split at line
    boundaries while preserving the semantic metadata.
    """
    chunks: list[SemanticChunk] = []
    lines = content.splitlines(keepends=True)
    covered_lines: set[int] = set()  # 1-indexed lines covered by symbols
    chunk_index = 0

    # Sort symbols by start_line for deterministic output
    sorted_symbols = sorted(symbols, key=lambda s: (s.start_line, -s.end_line))

    for sym in sorted_symbols:
        if sym.kind == "import":
            continue  # imports are collected separately

        body = sym.body
        if not body.strip():
            continue

        # Mark lines as covered
        for ln in range(sym.start_line, sym.end_line + 1):
            covered_lines.add(ln)

        # If body fits in one chunk, emit directly
        if len(body) <= max_chunk_size:
            sc = SemanticChunk(
                file_path=file_path,
                content=body,
                start_line=sym.start_line,
                end_line=sym.end_line,
                chunk_index=chunk_index,
                language=language,
                symbol_name=sym.name,
                symbol_kind=sym.kind,
                parent_symbol=sym.parent or "",
                parameters=list(sym.parameters),
            )
            sc.semantic_label = _build_semantic_label(sc)
            chunks.append(sc)
            chunk_index += 1
        else:
            # Sub-split large symbols at line boundaries
            body_lines = body.splitlines(keepends=True)
            sub_lines: list[str] = []
            sub_start = sym.start_line
            sub_chars = 0

            for offset, line in enumerate(body_lines):
                sub_lines.append(line)
                sub_chars += len(line)

                if sub_chars >= max_chunk_size:
                    sc = SemanticChunk(
                        file_path=file_path,
                        content="".join(sub_lines),
                        start_line=sub_start,
                        end_line=sym.start_line + offset,
                        chunk_index=chunk_index,
                        language=language,
                        symbol_name=sym.name,
                        symbol_kind=sym.kind,
                        parent_symbol=sym.parent or "",
                        parameters=list(sym.parameters),
                    )
                    sc.semantic_label = _build_semantic_label(sc)
                    chunks.append(sc)
                    chunk_index += 1
                    sub_lines = []
                    sub_start = sym.start_line + offset + 1
                    sub_chars = 0

            if sub_lines and "".join(sub_lines).strip():
                sc = SemanticChunk(
                    file_path=file_path,
                    content="".join(sub_lines),
                    start_line=sub_start,
                    end_line=sym.end_line,
                    chunk_index=chunk_index,
                    language=language,
                    symbol_name=sym.name,
                    symbol_kind=sym.kind,
                    parent_symbol=sym.parent or "",
                    parameters=list(sym.parameters),
                )
                sc.semantic_label = _build_semantic_label(sc)
                chunks.append(sc)
                chunk_index += 1

    # Collect uncovered regions (module-level code, imports header, etc.)
    uncovered_blocks = _extract_uncovered_blocks(lines, covered_lines)
    for start_line, end_line, block_content in uncovered_blocks:
        if not block_content.strip():
            continue
        if len(block_content) <= max_chunk_size:
            sc = SemanticChunk(
                file_path=file_path,
                content=block_content,
                start_line=start_line,
                end_line=end_line,
                chunk_index=chunk_index,
                language=language,
                symbol_name="",
                symbol_kind="module_header" if start_line <= 5 else "block",
            )
            sc.semantic_label = _build_semantic_label(sc)
            chunks.append(sc)
            chunk_index += 1
        else:
            # Sub-split large uncovered blocks
            block_lines = block_content.splitlines(keepends=True)
            buf: list[str] = []
            buf_start = start_line
            buf_chars = 0
            for offset, line in enumerate(block_lines):
                buf.append(line)
                buf_chars += len(line)
                if buf_chars >= max_chunk_size:
                    sc = SemanticChunk(
                        file_path=file_path,
                        content="".join(buf),
                        start_line=buf_start,
                        end_line=start_line + offset,
                        chunk_index=chunk_index,
                        language=language,
                        symbol_name="",
                        symbol_kind="block",
                    )
                    sc.semantic_label = _build_semantic_label(sc)
                    chunks.append(sc)
                    chunk_index += 1
                    buf = []
                    buf_start = start_line + offset + 1
                    buf_chars = 0
            if buf and "".join(buf).strip():
                sc = SemanticChunk(
                    file_path=file_path,
                    content="".join(buf),
                    start_line=buf_start,
                    end_line=end_line,
                    chunk_index=chunk_index,
                    language=language,
                    symbol_name="",
                    symbol_kind="block",
                )
                sc.semantic_label = _build_semantic_label(sc)
                chunks.append(sc)
                chunk_index += 1

    # Sort by start_line for stable ordering
    chunks.sort(key=lambda c: c.start_line)
    for i, c in enumerate(chunks):
        c.chunk_index = i

    return chunks


def _extract_uncovered_blocks(
    lines: list[str],
    covered_lines: set[int],
) -> list[tuple[int, int, str]]:
    """Find contiguous blocks of lines not covered by any symbol.

    Returns list of (start_line, end_line, content) tuples (1-indexed).
    """
    blocks: list[tuple[int, int, str]] = []
    block_start: int | None = None
    block_lines: list[str] = []

    for i, line in enumerate(lines):
        line_num = i + 1  # 1-indexed
        if line_num not in covered_lines:
            if block_start is None:
                block_start = line_num
            block_lines.append(line)
        else:
            if block_start is not None:
                blocks.append((block_start, line_num - 1, "".join(block_lines)))
                block_start = None
                block_lines = []

    if block_start is not None:
        blocks.append((block_start, len(lines), "".join(block_lines)))

    return blocks


def semantic_chunk_code(
    content: str,
    file_path: str,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> list[SemanticChunk]:
    """Split code into semantically meaningful chunks using AST analysis.

    For supported languages (Python, JS, TypeScript, Java, Go, Rust, C++,
    C#, Ruby, PHP), uses tree-sitter to identify symbol boundaries and
    produces chunks aligned to function, class, and method definitions.

    For unsupported languages, falls back to line-boundary chunking and
    wraps the result as SemanticChunk objects.

    Args:
        content: Full source code string.
        file_path: Path for language detection and metadata.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Overlap chars (used only in fallback mode).

    Returns:
        List of SemanticChunk objects.
    """
    if not content.strip():
        return []

    language = detect_language(file_path)
    ts_language = detect_ts_language(file_path)

    # If tree-sitter supports this language, use AST-aware chunking
    if ts_language is not None:
        symbols = parse_file(file_path, content)
        if symbols:
            return _symbols_to_chunks(symbols, content, file_path, language, chunk_size)

    # Fallback: wrap line-based chunks as SemanticChunks
    line_chunks = chunk_code(content, file_path, chunk_size, chunk_overlap)
    return [
        SemanticChunk(
            file_path=c.file_path,
            content=c.content,
            start_line=c.start_line,
            end_line=c.end_line,
            chunk_index=c.chunk_index,
            language=c.language,
            symbol_kind="block",
        )
        for c in line_chunks
    ]


def semantic_chunk_file(
    file_path: Path,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> list[SemanticChunk]:
    """Read a file and split into semantic chunks.

    Args:
        file_path: Path to the source file.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Overlap for fallback mode.

    Returns:
        List of SemanticChunk objects.
    """
    try:
        content = Path(file_path).read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError):
        return []
    return semantic_chunk_code(content, str(file_path), chunk_size, chunk_overlap)
