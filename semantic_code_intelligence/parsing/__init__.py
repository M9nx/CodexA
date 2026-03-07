"""Parsing package — tree-sitter based code analysis."""

from semantic_code_intelligence.parsing.parser import (
    Symbol,
    detect_language,
    extract_classes,
    extract_functions,
    extract_imports,
    parse_file,
)

__all__ = [
    "Symbol",
    "detect_language",
    "extract_classes",
    "extract_functions",
    "extract_imports",
    "parse_file",
]
