"""Code chunker — splits source files into meaningful chunks for embedding."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class CodeChunk:
    """A chunk of code extracted from a source file."""

    file_path: str
    content: str
    start_line: int
    end_line: int
    chunk_index: int
    language: str


# Map file extensions to language names
EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".sh": "shell",
    ".bash": "shell",
    ".sql": "sql",
    ".r": "r",
    ".lua": "lua",
    ".dart": "dart",
    ".ex": "elixir",
    ".exs": "elixir",
}


def detect_language(file_path: str) -> str:
    """Detect the programming language from a file extension.

    Args:
        file_path: Path to the source file.

    Returns:
        Language name string, or 'unknown' if unrecognized.
    """
    ext = Path(file_path).suffix.lower()
    return EXTENSION_TO_LANGUAGE.get(ext, "unknown")


def chunk_code(
    content: str,
    file_path: str,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> list[CodeChunk]:
    """Split source code into overlapping chunks by line boundaries.

    Chunks are split at line boundaries to preserve code structure.
    Each chunk is at most chunk_size characters, with chunk_overlap
    characters of overlap with the previous chunk.

    Args:
        content: The full source code string.
        file_path: Path to the source file (for metadata).
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Characters of overlap between consecutive chunks.

    Returns:
        List of CodeChunk objects.
    """
    if not content.strip():
        return []

    language = detect_language(file_path)
    lines = content.splitlines(keepends=True)
    chunks: list[CodeChunk] = []

    current_chars = 0
    chunk_start_line = 0
    chunk_lines: list[str] = []
    chunk_index = 0

    for i, line in enumerate(lines):
        chunk_lines.append(line)
        current_chars += len(line)

        if current_chars >= chunk_size:
            chunk_text = "".join(chunk_lines)
            chunks.append(
                CodeChunk(
                    file_path=file_path,
                    content=chunk_text,
                    start_line=chunk_start_line + 1,  # 1-indexed
                    end_line=i + 1,
                    chunk_index=chunk_index,
                    language=language,
                )
            )
            chunk_index += 1

            # Calculate overlap: walk backwards until we have enough overlap chars
            overlap_chars = 0
            overlap_start = len(chunk_lines)
            for j in range(len(chunk_lines) - 1, -1, -1):
                overlap_chars += len(chunk_lines[j])
                if overlap_chars >= chunk_overlap:
                    overlap_start = j
                    break

            chunk_lines = chunk_lines[overlap_start:]
            chunk_start_line = i + 1 - len(chunk_lines) + 1
            # But we need to preserve 0-indexed line tracking
            chunk_start_line = (i + 1) - len(chunk_lines)
            current_chars = sum(len(l) for l in chunk_lines)

    # Emit the last chunk if there's remaining content
    if chunk_lines:
        chunk_text = "".join(chunk_lines)
        if chunk_text.strip():
            chunks.append(
                CodeChunk(
                    file_path=file_path,
                    content=chunk_text,
                    start_line=chunk_start_line + 1,
                    end_line=len(lines),
                    chunk_index=chunk_index,
                    language=language,
                )
            )

    return chunks


def chunk_file(
    file_path: Path,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> list[CodeChunk]:
    """Read a file and split it into code chunks.

    Args:
        file_path: Path to the source file.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Characters of overlap.

    Returns:
        List of CodeChunk objects.
    """
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError):
        return []

    return chunk_code(
        content=content,
        file_path=str(file_path),
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
