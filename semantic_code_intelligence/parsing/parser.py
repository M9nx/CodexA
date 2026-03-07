"""Code parser — uses tree-sitter to extract functions, classes, and symbols."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tree_sitter

from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("parsing")

# Grammar modules for supported languages
_LANGUAGE_MODULES: dict[str, str] = {
    "python": "tree_sitter_python",
    "javascript": "tree_sitter_javascript",
    "typescript": "tree_sitter_typescript",
    "tsx": "tree_sitter_typescript",
    "java": "tree_sitter_java",
    "go": "tree_sitter_go",
    "rust": "tree_sitter_rust",
    "cpp": "tree_sitter_cpp",
    "csharp": "tree_sitter_c_sharp",
    "ruby": "tree_sitter_ruby",
    "php": "tree_sitter_php",
}

# Languages that require a special factory function name (not just `language()`)
_LANGUAGE_FACTORY: dict[str, str] = {
    "typescript": "language_typescript",
    "tsx": "language_tsx",
    "php": "language_php",
}

# Extension to language mapping
EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".h": "cpp",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
}

# Node types that represent function definitions per language
FUNCTION_NODE_TYPES: dict[str, set[str]] = {
    "python": {"function_definition"},
    "javascript": {"function_declaration", "arrow_function", "method_definition"},
    "typescript": {"function_declaration", "arrow_function", "method_definition"},
    "tsx": {"function_declaration", "arrow_function", "method_definition"},
    "java": {"method_declaration", "constructor_declaration"},
    "go": {"function_declaration", "method_declaration"},
    "rust": {"function_item"},
    "cpp": {"function_definition"},
    "csharp": {"method_declaration", "constructor_declaration"},
    "ruby": {"method", "singleton_method"},
    "php": {"function_definition", "method_declaration"},
}

# Node types that represent class/struct definitions per language
CLASS_NODE_TYPES: dict[str, set[str]] = {
    "python": {"class_definition"},
    "javascript": {"class_declaration"},
    "typescript": {"class_declaration", "interface_declaration", "enum_declaration"},
    "tsx": {"class_declaration", "interface_declaration", "enum_declaration"},
    "java": {"class_declaration", "interface_declaration", "enum_declaration"},
    "go": {"type_declaration"},
    "rust": {"struct_item", "enum_item", "impl_item", "trait_item"},
    "cpp": {"class_specifier", "struct_specifier", "enum_specifier"},
    "csharp": {"class_declaration", "interface_declaration", "struct_declaration", "enum_declaration"},
    "ruby": {"class", "module"},
    "php": {"class_declaration", "interface_declaration", "trait_declaration", "enum_declaration"},
}

# Node types for import statements
IMPORT_NODE_TYPES: dict[str, set[str]] = {
    "python": {"import_statement", "import_from_statement"},
    "javascript": {"import_statement"},
    "typescript": {"import_statement"},
    "tsx": {"import_statement"},
    "java": {"import_declaration"},
    "go": {"import_declaration"},
    "rust": {"use_declaration"},
    "cpp": {"preproc_include"},
    "csharp": {"using_directive"},
    "ruby": {"call"},  # require/require_relative detected via name filter
    "php": {"namespace_use_declaration"},
}

# Cache for loaded languages
_language_cache: dict[str, tree_sitter.Language] = {}


@dataclass
class Symbol:
    """A parsed symbol (function, class, method, etc.)."""

    name: str
    kind: str  # "function", "class", "method", "import"
    file_path: str
    start_line: int
    end_line: int
    start_col: int
    end_col: int
    body: str
    parent: str | None = None  # Parent class name for methods
    parameters: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        return {
            "name": self.name,
            "kind": self.kind,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "body": self.body,
            "parent": self.parent,
            "parameters": self.parameters,
            "decorators": self.decorators,
        }


def get_language(lang_name: str) -> tree_sitter.Language | None:
    """Load and cache a tree-sitter Language for the given language name.

    Args:
        lang_name: Language name (e.g. 'python', 'javascript').

    Returns:
        A tree_sitter.Language instance, or None if unsupported.
    """
    if lang_name in _language_cache:
        return _language_cache[lang_name]

    module_name = _LANGUAGE_MODULES.get(lang_name)
    if module_name is None:
        return None

    try:
        import importlib
        mod = importlib.import_module(module_name)
        factory_name = _LANGUAGE_FACTORY.get(lang_name, "language")
        factory = getattr(mod, factory_name)
        lang = tree_sitter.Language(factory())
        _language_cache[lang_name] = lang
        return lang
    except (ImportError, AttributeError, Exception) as e:
        logger.warning("Failed to load tree-sitter grammar for %s: %s", lang_name, e)
        return None


def detect_language(file_path: str) -> str | None:
    """Detect language from file extension.

    Returns None if the language is not supported by tree-sitter.
    """
    ext = Path(file_path).suffix.lower()
    return EXTENSION_TO_LANGUAGE.get(ext)


def _get_node_text(node: tree_sitter.Node, source: bytes) -> str:
    """Extract the text of a tree-sitter node."""
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _find_name(node: tree_sitter.Node, source: bytes) -> str:
    """Find the name identifier within a definition node."""
    _NAME_TYPES = {
        "identifier", "property_identifier", "type_identifier",
        "field_identifier", "constant", "name",  # constant=Ruby, name=PHP
    }
    for child in node.children:
        if child.type in _NAME_TYPES:
            return _get_node_text(child, source)
    # C++: name may be inside a declarator child (e.g. function_declarator)
    for child in node.children:
        if child.type.endswith("_declarator"):
            for sub in child.children:
                if sub.type in _NAME_TYPES:
                    return _get_node_text(sub, source)
    return "<anonymous>"


def _find_parameters(node: tree_sitter.Node, source: bytes) -> list[str]:
    """Extract parameter names from a function definition node."""
    params: list[str] = []
    for child in node.children:
        if child.type in ("parameters", "formal_parameters", "parameter_list"):
            for param in child.children:
                if param.type in ("identifier", "typed_parameter", "typed_default_parameter"):
                    # For typed params, get just the name
                    name_node = param.child_by_field_name("name") or param
                    for sub in [name_node] if name_node.type == "identifier" else name_node.children:
                        if sub.type == "identifier":
                            params.append(_get_node_text(sub, source))
                            break
                elif param.type == "parameter":
                    for sub in param.children:
                        if sub.type == "identifier":
                            params.append(_get_node_text(sub, source))
                            break
    return params


def _find_decorators(node: tree_sitter.Node, source: bytes) -> list[str]:
    """Extract decorator names from a definition node (Python)."""
    decorators: list[str] = []
    if node.prev_named_sibling and node.prev_named_sibling.type == "decorator":
        decorators.append(_get_node_text(node.prev_named_sibling, source).strip())
    # Also check for decorated_definition parent
    if node.parent and node.parent.type == "decorated_definition":
        for child in node.parent.children:
            if child.type == "decorator":
                decorators.append(_get_node_text(child, source).strip())
    return decorators


def _extract_symbols_recursive(
    node: tree_sitter.Node,
    source: bytes,
    file_path: str,
    language: str,
    parent_class: str | None = None,
) -> list[Symbol]:
    """Recursively walk the AST and extract symbols."""
    symbols: list[Symbol] = []
    func_types = FUNCTION_NODE_TYPES.get(language, set())
    class_types = CLASS_NODE_TYPES.get(language, set())
    import_types = IMPORT_NODE_TYPES.get(language, set())

    for child in node.children:
        # Handle decorated definitions (Python wraps func/class in decorated_definition)
        actual = child
        if child.type == "decorated_definition":
            for sub in child.children:
                if sub.type in func_types or sub.type in class_types:
                    actual = sub
                    break

        if actual.type in func_types:
            name = _find_name(actual, source)
            # Some languages have dedicated method node types (e.g. Go method_declaration,
            # JS method_definition) that indicate a method even without a parent class.
            _method_node_types = {
                "method_declaration", "method_definition", "constructor_declaration",
            }
            if parent_class or actual.type in _method_node_types:
                kind = "method"
            else:
                kind = "function"
            symbols.append(
                Symbol(
                    name=name,
                    kind=kind,
                    file_path=file_path,
                    start_line=actual.start_point[0] + 1,
                    end_line=actual.end_point[0] + 1,
                    start_col=actual.start_point[1],
                    end_col=actual.end_point[1],
                    body=_get_node_text(actual, source),
                    parent=parent_class,
                    parameters=_find_parameters(actual, source),
                    decorators=_find_decorators(actual, source),
                )
            )

        elif actual.type in class_types:
            name = _find_name(actual, source)
            symbols.append(
                Symbol(
                    name=name,
                    kind="class",
                    file_path=file_path,
                    start_line=actual.start_point[0] + 1,
                    end_line=actual.end_point[0] + 1,
                    start_col=actual.start_point[1],
                    end_col=actual.end_point[1],
                    body=_get_node_text(actual, source),
                )
            )
            # Recurse into class body for methods
            symbols.extend(
                _extract_symbols_recursive(actual, source, file_path, language, parent_class=name)
            )
            continue  # already recursed into children

        elif actual.type in import_types:
            text = _get_node_text(actual, source).strip()
            # Ruby: only treat require/require_relative calls as imports
            if language == "ruby" and actual.type == "call":
                method_name = _find_name(actual, source)
                if method_name not in ("require", "require_relative"):
                    symbols.extend(
                        _extract_symbols_recursive(child, source, file_path, language, parent_class)
                    )
                    continue
            symbols.append(
                Symbol(
                    name=text,
                    kind="import",
                    file_path=file_path,
                    start_line=actual.start_point[0] + 1,
                    end_line=actual.end_point[0] + 1,
                    start_col=actual.start_point[1],
                    end_col=actual.end_point[1],
                    body=_get_node_text(actual, source),
                )
            )

        # Recurse into children
        symbols.extend(
            _extract_symbols_recursive(child, source, file_path, language, parent_class)
        )

    return symbols


def parse_file(file_path: str | Path, content: str | None = None) -> list[Symbol]:
    """Parse a source file and extract all symbols.

    Args:
        file_path: Path to the source file.
        content: Optional file content. If None, reads from disk.

    Returns:
        List of extracted Symbol objects.
    """
    file_path = str(file_path)
    lang_name = detect_language(file_path)
    if lang_name is None:
        return []

    language = get_language(lang_name)
    if language is None:
        return []

    if content is None:
        try:
            content = Path(file_path).read_text(encoding="utf-8", errors="replace")
        except (OSError, PermissionError):
            return []

    source = content.encode("utf-8")
    parser = tree_sitter.Parser(language)
    tree = parser.parse(source)

    return _extract_symbols_recursive(tree.root_node, source, file_path, lang_name)


def extract_functions(file_path: str | Path, content: str | None = None) -> list[Symbol]:
    """Extract only function and method symbols from a file."""
    return [s for s in parse_file(file_path, content) if s.kind in ("function", "method")]


def extract_classes(file_path: str | Path, content: str | None = None) -> list[Symbol]:
    """Extract only class symbols from a file."""
    return [s for s in parse_file(file_path, content) if s.kind == "class"]


def extract_imports(file_path: str | Path, content: str | None = None) -> list[Symbol]:
    """Extract only import symbols from a file."""
    return [s for s in parse_file(file_path, content) if s.kind == "import"]
