"""Tests for the tree-sitter based code parser."""

import pytest

from semantic_code_intelligence.parsing.parser import (
    Symbol,
    detect_language,
    extract_classes,
    extract_functions,
    extract_imports,
    get_language,
    parse_file,
    _get_node_text,
)


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

class TestDetectLanguage:
    def test_python(self):
        assert detect_language("main.py") == "python"

    def test_javascript(self):
        assert detect_language("app.js") == "javascript"

    def test_jsx(self):
        assert detect_language("component.jsx") == "javascript"

    def test_java(self):
        assert detect_language("Main.java") == "java"

    def test_go(self):
        assert detect_language("main.go") == "go"

    def test_rust(self):
        assert detect_language("lib.rs") == "rust"

    def test_unsupported(self):
        assert detect_language("style.css") is None

    def test_no_extension(self):
        assert detect_language("Makefile") is None

    def test_case_insensitive(self):
        assert detect_language("FILE.PY") == "python"
        assert detect_language("APP.JS") == "javascript"


# ---------------------------------------------------------------------------
# Language loading
# ---------------------------------------------------------------------------

class TestGetLanguage:
    def test_load_python(self):
        lang = get_language("python")
        assert lang is not None

    def test_load_javascript(self):
        lang = get_language("javascript")
        assert lang is not None

    def test_load_java(self):
        lang = get_language("java")
        assert lang is not None

    def test_load_go(self):
        lang = get_language("go")
        assert lang is not None

    def test_load_rust(self):
        lang = get_language("rust")
        assert lang is not None

    def test_unsupported_language(self):
        assert get_language("cobol") is None

    def test_caching(self):
        """Loading same language twice returns cached instance."""
        lang1 = get_language("python")
        lang2 = get_language("python")
        assert lang1 is lang2


# ---------------------------------------------------------------------------
# Python parsing
# ---------------------------------------------------------------------------

PYTHON_CODE = '''\
import os
from pathlib import Path

def hello(name: str) -> str:
    """Greet someone."""
    return f"Hello, {name}!"

class Calculator:
    """A simple calculator."""

    def __init__(self, value: int = 0):
        self.value = value

    def add(self, x: int) -> int:
        self.value += x
        return self.value

    def subtract(self, x: int) -> int:
        self.value -= x
        return self.value

def _private_helper():
    pass
'''


class TestPythonParsing:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.symbols = parse_file("example.py", PYTHON_CODE)

    def test_total_symbols_found(self):
        # 2 imports + 1 function + 1 class + 3 methods + 1 private helper
        assert len(self.symbols) >= 7

    def test_function_extraction(self):
        funcs = [s for s in self.symbols if s.kind == "function"]
        names = {f.name for f in funcs}
        assert "hello" in names
        assert "_private_helper" in names

    def test_class_extraction(self):
        classes = [s for s in self.symbols if s.kind == "class"]
        assert len(classes) == 1
        assert classes[0].name == "Calculator"

    def test_method_extraction(self):
        methods = [s for s in self.symbols if s.kind == "method"]
        names = {m.name for m in methods}
        assert "__init__" in names
        assert "add" in names
        assert "subtract" in names

    def test_methods_have_parent(self):
        methods = [s for s in self.symbols if s.kind == "method"]
        for m in methods:
            assert m.parent == "Calculator"

    def test_import_extraction(self):
        imports = [s for s in self.symbols if s.kind == "import"]
        assert len(imports) >= 2

    def test_line_numbers(self):
        hello = next(s for s in self.symbols if s.name == "hello")
        assert hello.start_line == 4
        assert hello.end_line == 6

    def test_body_contains_code(self):
        hello = next(s for s in self.symbols if s.name == "hello")
        assert "def hello" in hello.body
        assert "return" in hello.body

    def test_parameters(self):
        hello = next(s for s in self.symbols if s.name == "hello")
        assert "name" in hello.parameters

    def test_symbol_to_dict(self):
        hello = next(s for s in self.symbols if s.name == "hello")
        d = hello.to_dict()
        assert d["name"] == "hello"
        assert d["kind"] == "function"
        assert d["file_path"] == "example.py"
        assert "start_line" in d
        assert "body" in d


# ---------------------------------------------------------------------------
# JavaScript parsing
# ---------------------------------------------------------------------------

JS_CODE = '''\
import { useState } from 'react';

function greet(name) {
    return `Hello, ${name}!`;
}

const add = (a, b) => a + b;

class Counter {
    constructor(initial) {
        this.count = initial;
    }

    increment() {
        this.count++;
    }
}
'''


class TestJavaScriptParsing:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.symbols = parse_file("app.js", JS_CODE)

    def test_function_found(self):
        funcs = extract_functions("app.js", JS_CODE)
        names = {f.name for f in funcs}
        assert "greet" in names

    def test_class_found(self):
        classes = extract_classes("app.js", JS_CODE)
        assert any(c.name == "Counter" for c in classes)

    def test_methods_found(self):
        methods = [s for s in self.symbols if s.kind == "method"]
        names = {m.name for m in methods}
        # constructor and increment
        assert "constructor" in names or "increment" in names

    def test_import_found(self):
        imports = extract_imports("app.js", JS_CODE)
        assert len(imports) >= 1


# ---------------------------------------------------------------------------
# Java parsing
# ---------------------------------------------------------------------------

JAVA_CODE = '''\
import java.util.List;

public class Calculator {
    private int value;

    public Calculator(int initial) {
        this.value = initial;
    }

    public int add(int x) {
        this.value += x;
        return this.value;
    }

    public int getValue() {
        return this.value;
    }
}
'''


class TestJavaParsing:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.symbols = parse_file("Calculator.java", JAVA_CODE)

    def test_class_found(self):
        classes = extract_classes("Calculator.java", JAVA_CODE)
        assert any(c.name == "Calculator" for c in classes)

    def test_methods_found(self):
        methods = [s for s in self.symbols if s.kind == "method"]
        names = {m.name for m in methods}
        assert "add" in names
        assert "getValue" in names

    def test_constructor_found(self):
        methods = [s for s in self.symbols if s.kind == "method"]
        names = {m.name for m in methods}
        assert "Calculator" in names

    def test_import_found(self):
        imports = extract_imports("Calculator.java", JAVA_CODE)
        assert len(imports) >= 1


# ---------------------------------------------------------------------------
# Go parsing
# ---------------------------------------------------------------------------

GO_CODE = '''\
package main

import "fmt"

func main() {
    fmt.Println("Hello")
}

func add(a int, b int) int {
    return a + b
}

type Calculator struct {
    value int
}

func (c *Calculator) Add(x int) int {
    c.value += x
    return c.value
}
'''


class TestGoParsing:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.symbols = parse_file("main.go", GO_CODE)

    def test_functions_found(self):
        funcs = [s for s in self.symbols if s.kind == "function"]
        names = {f.name for f in funcs}
        assert "main" in names
        assert "add" in names

    def test_type_found(self):
        classes = extract_classes("main.go", GO_CODE)
        assert len(classes) >= 1

    def test_method_found(self):
        methods = [s for s in self.symbols if s.kind == "method"]
        names = {m.name for m in methods}
        assert "Add" in names

    def test_import_found(self):
        imports = extract_imports("main.go", GO_CODE)
        assert len(imports) >= 1


# ---------------------------------------------------------------------------
# Rust parsing
# ---------------------------------------------------------------------------

RUST_CODE = '''\
use std::fmt;

fn main() {
    println!("Hello");
}

fn add(a: i32, b: i32) -> i32 {
    a + b
}

struct Calculator {
    value: i32,
}

impl Calculator {
    fn new(value: i32) -> Self {
        Calculator { value }
    }

    fn add(&self, x: i32) -> i32 {
        self.value + x
    }
}

enum Color {
    Red,
    Green,
    Blue,
}
'''


class TestRustParsing:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.symbols = parse_file("lib.rs", RUST_CODE)

    def test_functions_found(self):
        funcs = [s for s in self.symbols if s.kind == "function"]
        names = {f.name for f in funcs}
        assert "main" in names
        assert "add" in names

    def test_struct_found(self):
        classes = extract_classes("lib.rs", RUST_CODE)
        names = {c.name for c in classes}
        assert "Calculator" in names

    def test_impl_methods(self):
        # Methods inside impl blocks
        methods = [s for s in self.symbols if s.kind == "method"]
        names = {m.name for m in methods}
        assert "new" in names or "add" in names

    def test_enum_found(self):
        classes = extract_classes("lib.rs", RUST_CODE)
        names = {c.name for c in classes}
        assert "Color" in names

    def test_use_found(self):
        imports = extract_imports("lib.rs", RUST_CODE)
        assert len(imports) >= 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_file(self):
        symbols = parse_file("empty.py", "")
        assert symbols == []

    def test_syntax_error_still_parses(self):
        """tree-sitter is error-tolerant and should still parse partial code."""
        code = "def broken_func(:\n    pass"
        symbols = parse_file("broken.py", code)
        # Should not crash — may or may not find symbols
        assert isinstance(symbols, list)

    def test_unsupported_extension(self):
        symbols = parse_file("style.css", "body { color: red; }")
        assert symbols == []

    def test_unicode_content(self):
        code = 'def greet():\n    print("Héllo, 世界!")\n'
        symbols = parse_file("unicode.py", code)
        funcs = [s for s in symbols if s.kind == "function"]
        assert len(funcs) == 1
        assert funcs[0].name == "greet"

    def test_nonexistent_file_returns_empty(self, tmp_path):
        symbols = parse_file(str(tmp_path / "does_not_exist.py"))
        assert symbols == []

    def test_read_from_disk(self, tmp_path):
        f = tmp_path / "hello.py"
        f.write_text("def disk_func():\n    pass\n", encoding="utf-8")
        symbols = parse_file(str(f))
        funcs = [s for s in symbols if s.kind == "function"]
        assert any(fun.name == "disk_func" for fun in funcs)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

class TestExtractHelpers:
    def test_extract_functions_filters(self):
        funcs = extract_functions("example.py", PYTHON_CODE)
        for f in funcs:
            assert f.kind in ("function", "method")

    def test_extract_classes_filters(self):
        classes = extract_classes("example.py", PYTHON_CODE)
        for c in classes:
            assert c.kind == "class"

    def test_extract_imports_filters(self):
        imports = extract_imports("example.py", PYTHON_CODE)
        for i in imports:
            assert i.kind == "import"


# ---------------------------------------------------------------------------
# Python decorators
# ---------------------------------------------------------------------------

DECORATED_CODE = '''\
import functools

def my_decorator(func):
    pass

@my_decorator
def decorated_function():
    pass

class MyClass:
    @staticmethod
    def static_method():
        pass
'''


class TestDecorators:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.symbols = parse_file("decorated.py", DECORATED_CODE)

    def test_decorated_function_found(self):
        funcs = [s for s in self.symbols if s.kind == "function"]
        names = {f.name for f in funcs}
        assert "decorated_function" in names
        assert "my_decorator" in names

    def test_static_method_found(self):
        methods = [s for s in self.symbols if s.kind == "method"]
        names = {m.name for m in methods}
        assert "static_method" in names
