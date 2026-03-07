"""Tests for Phase 11 — Multi-Language Parsing Expansion.

Covers: language detection, tree-sitter grammar loading, and symbol
extraction for TypeScript, TSX, C++, C#, Ruby, and PHP.
"""

from __future__ import annotations

import pytest

from semantic_code_intelligence.parsing.parser import (
    EXTENSION_TO_LANGUAGE,
    FUNCTION_NODE_TYPES,
    CLASS_NODE_TYPES,
    IMPORT_NODE_TYPES,
    detect_language,
    get_language,
    parse_file,
)


# =========================================================================
# Language detection tests
# =========================================================================


class TestNewLanguageDetection:
    """Verify file extensions map to the correct language names."""

    def test_typescript(self):
        assert detect_language("app.ts") == "typescript"

    def test_tsx(self):
        assert detect_language("Component.tsx") == "tsx"

    def test_cpp_extensions(self):
        assert detect_language("main.cpp") == "cpp"
        assert detect_language("util.cc") == "cpp"
        assert detect_language("header.hpp") == "cpp"
        assert detect_language("types.h") == "cpp"

    def test_csharp(self):
        assert detect_language("Program.cs") == "csharp"

    def test_ruby(self):
        assert detect_language("app.rb") == "ruby"

    def test_php(self):
        assert detect_language("index.php") == "php"

    def test_case_insensitive(self):
        assert detect_language("APP.TS") == "typescript"
        assert detect_language("MAIN.CPP") == "cpp"
        assert detect_language("PROG.CS") == "csharp"
        assert detect_language("APP.RB") == "ruby"
        assert detect_language("PAGE.PHP") == "php"


# =========================================================================
# Grammar loading tests
# =========================================================================


class TestGrammarLoading:
    """Verify tree-sitter grammars load without errors."""

    @pytest.mark.parametrize("lang", [
        "typescript", "tsx", "cpp", "csharp", "ruby", "php",
    ])
    def test_load_language(self, lang):
        result = get_language(lang)
        assert result is not None, f"Failed to load grammar for {lang}"

    def test_unknown_language_returns_none(self):
        assert get_language("brainfuck") is None


# =========================================================================
# Node type mapping coverage
# =========================================================================


class TestNodeTypeMappings:
    """Ensure all new languages have entries in every mapping dict."""

    @pytest.mark.parametrize("lang", [
        "typescript", "tsx", "cpp", "csharp", "ruby", "php",
    ])
    def test_function_types(self, lang):
        assert lang in FUNCTION_NODE_TYPES
        assert len(FUNCTION_NODE_TYPES[lang]) > 0

    @pytest.mark.parametrize("lang", [
        "typescript", "tsx", "cpp", "csharp", "ruby", "php",
    ])
    def test_class_types(self, lang):
        assert lang in CLASS_NODE_TYPES
        assert len(CLASS_NODE_TYPES[lang]) > 0

    @pytest.mark.parametrize("lang", [
        "typescript", "tsx", "cpp", "csharp", "ruby", "php",
    ])
    def test_import_types(self, lang):
        assert lang in IMPORT_NODE_TYPES
        assert len(IMPORT_NODE_TYPES[lang]) > 0


# =========================================================================
# TypeScript parsing
# =========================================================================

TYPESCRIPT_CODE = """\
import { useState } from 'react';

interface Config {
    host: string;
    port: number;
}

class Server {
    constructor(private config: Config) {}

    start(): void {
        console.log('starting');
    }
}

function createServer(config: Config): Server {
    return new Server(config);
}

const helper = (x: number): number => x * 2;
"""


class TestTypeScriptParsing:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.symbols = parse_file("server.ts", TYPESCRIPT_CODE)
        self.kinds = {s.kind for s in self.symbols}
        self.names = {s.name for s in self.symbols}

    def test_detects_import(self):
        imports = [s for s in self.symbols if s.kind == "import"]
        assert len(imports) >= 1

    def test_detects_interface(self):
        classes = [s for s in self.symbols if s.kind == "class"]
        class_names = {s.name for s in classes}
        assert "Config" in class_names

    def test_detects_class(self):
        classes = [s for s in self.symbols if s.kind == "class"]
        class_names = {s.name for s in classes}
        assert "Server" in class_names

    def test_detects_function(self):
        fns = [s for s in self.symbols if s.kind == "function"]
        fn_names = {s.name for s in fns}
        assert "createServer" in fn_names

    def test_detects_method(self):
        methods = [s for s in self.symbols if s.kind == "method"]
        method_names = {s.name for s in methods}
        assert "start" in method_names


# =========================================================================
# TSX parsing
# =========================================================================

TSX_CODE = """\
import React from 'react';

interface Props {
    title: string;
}

class Header extends React.Component<Props> {
    render() {
        return <h1>{this.props.title}</h1>;
    }
}

function App(): JSX.Element {
    return <Header title="Hello" />;
}
"""


class TestTSXParsing:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.symbols = parse_file("App.tsx", TSX_CODE)

    def test_has_symbols(self):
        assert len(self.symbols) > 0

    def test_detects_class(self):
        classes = [s for s in self.symbols if s.kind == "class"]
        assert any(s.name == "Header" for s in classes)

    def test_detects_function(self):
        fns = [s for s in self.symbols if s.kind == "function"]
        assert any(s.name == "App" for s in fns)


# =========================================================================
# C++ parsing
# =========================================================================

CPP_CODE = """\
#include <iostream>
#include <string>

class Animal {
public:
    Animal(std::string name) : name_(name) {}
    virtual void speak() const = 0;
private:
    std::string name_;
};

struct Point {
    double x, y;
};

void greet(const std::string& name) {
    std::cout << "Hello, " << name << std::endl;
}

int main() {
    greet("world");
    return 0;
}
"""


class TestCppParsing:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.symbols = parse_file("main.cpp", CPP_CODE)

    def test_has_symbols(self):
        assert len(self.symbols) > 0

    def test_detects_include(self):
        imports = [s for s in self.symbols if s.kind == "import"]
        assert len(imports) >= 2

    def test_detects_class(self):
        classes = [s for s in self.symbols if s.kind == "class"]
        class_names = {s.name for s in classes}
        assert "Animal" in class_names

    def test_detects_struct(self):
        classes = [s for s in self.symbols if s.kind == "class"]
        class_names = {s.name for s in classes}
        assert "Point" in class_names

    def test_detects_function(self):
        fns = [s for s in self.symbols if s.kind == "function"]
        fn_names = {s.name for s in fns}
        assert "greet" in fn_names
        assert "main" in fn_names


# =========================================================================
# C# parsing
# =========================================================================

CSHARP_CODE = """\
using System;
using System.Collections.Generic;

namespace MyApp
{
    interface IGreeter
    {
        void Greet(string name);
    }

    class Greeter : IGreeter
    {
        public Greeter() { }

        public void Greet(string name)
        {
            Console.WriteLine($"Hello, {name}!");
        }

        public static int Add(int a, int b)
        {
            return a + b;
        }
    }

    enum Color
    {
        Red,
        Green,
        Blue
    }
}
"""


class TestCSharpParsing:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.symbols = parse_file("Program.cs", CSHARP_CODE)

    def test_has_symbols(self):
        assert len(self.symbols) > 0

    def test_detects_using(self):
        imports = [s for s in self.symbols if s.kind == "import"]
        assert len(imports) >= 2

    def test_detects_interface(self):
        classes = [s for s in self.symbols if s.kind == "class"]
        class_names = {s.name for s in classes}
        assert "IGreeter" in class_names

    def test_detects_class(self):
        classes = [s for s in self.symbols if s.kind == "class"]
        class_names = {s.name for s in classes}
        assert "Greeter" in class_names

    def test_detects_enum(self):
        classes = [s for s in self.symbols if s.kind == "class"]
        class_names = {s.name for s in classes}
        assert "Color" in class_names

    def test_detects_method(self):
        methods = [s for s in self.symbols if s.kind == "method"]
        method_names = {s.name for s in methods}
        assert "Greet" in method_names


# =========================================================================
# Ruby parsing
# =========================================================================

RUBY_CODE = """\
require 'json'
require_relative 'helpers'

module Serializable
  def to_json
    JSON.generate(to_h)
  end
end

class User
  include Serializable

  attr_reader :name, :age

  def initialize(name, age)
    @name = name
    @age = age
  end

  def greet
    puts "Hello, #{@name}"
  end

  def self.create(name, age)
    new(name, age)
  end

  def to_h
    { name: @name, age: @age }
  end
end

def standalone_function(x)
  x * 2
end
"""


class TestRubyParsing:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.symbols = parse_file("app.rb", RUBY_CODE)

    def test_has_symbols(self):
        assert len(self.symbols) > 0

    def test_detects_require(self):
        imports = [s for s in self.symbols if s.kind == "import"]
        assert len(imports) >= 2
        import_text = " ".join(s.body for s in imports)
        assert "json" in import_text
        assert "helpers" in import_text

    def test_does_not_treat_include_as_import(self):
        """include is a method call but not require/require_relative."""
        imports = [s for s in self.symbols if s.kind == "import"]
        for imp in imports:
            assert "include" not in imp.name.split()[0]

    def test_detects_module(self):
        classes = [s for s in self.symbols if s.kind == "class"]
        class_names = {s.name for s in classes}
        assert "Serializable" in class_names

    def test_detects_class(self):
        classes = [s for s in self.symbols if s.kind == "class"]
        class_names = {s.name for s in classes}
        assert "User" in class_names

    def test_detects_method(self):
        methods = [s for s in self.symbols if s.kind == "method"]
        method_names = {s.name for s in methods}
        assert "initialize" in method_names
        assert "greet" in method_names

    def test_detects_standalone_function(self):
        fns = [s for s in self.symbols if s.kind == "function"]
        fn_names = {s.name for s in fns}
        assert "standalone_function" in fn_names


# =========================================================================
# PHP parsing
# =========================================================================

PHP_CODE = """\
<?php

use App\\Models\\User;

interface Cacheable
{
    public function cacheKey(): string;
}

trait Timestampable
{
    public function createdAt(): string
    {
        return $this->created_at;
    }
}

class UserService implements Cacheable
{
    use Timestampable;

    public function __construct(
        private readonly string $name
    ) {}

    public function cacheKey(): string
    {
        return "user_" . $this->name;
    }

    public static function create(string $name): self
    {
        return new self($name);
    }
}

function helper(int $x): int
{
    return $x * 2;
}
"""


class TestPHPParsing:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.symbols = parse_file("index.php", PHP_CODE)

    def test_has_symbols(self):
        assert len(self.symbols) > 0

    def test_detects_use(self):
        imports = [s for s in self.symbols if s.kind == "import"]
        assert len(imports) >= 1

    def test_detects_interface(self):
        classes = [s for s in self.symbols if s.kind == "class"]
        class_names = {s.name for s in classes}
        assert "Cacheable" in class_names

    def test_detects_trait(self):
        classes = [s for s in self.symbols if s.kind == "class"]
        class_names = {s.name for s in classes}
        assert "Timestampable" in class_names

    def test_detects_class(self):
        classes = [s for s in self.symbols if s.kind == "class"]
        class_names = {s.name for s in classes}
        assert "UserService" in class_names

    def test_detects_method(self):
        methods = [s for s in self.symbols if s.kind == "method"]
        method_names = {s.name for s in methods}
        assert "cacheKey" in method_names

    def test_detects_function(self):
        fns = [s for s in self.symbols if s.kind == "function"]
        fn_names = {s.name for s in fns}
        assert "helper" in fn_names


# =========================================================================
# Semantic chunker integration
# =========================================================================


class TestSemanticChunkerIntegration:
    """Verify the semantic chunker works with new languages."""

    @pytest.mark.parametrize("ext,code", [
        ("server.ts", TYPESCRIPT_CODE),
        ("App.tsx", TSX_CODE),
        ("main.cpp", CPP_CODE),
        ("Program.cs", CSHARP_CODE),
        ("app.rb", RUBY_CODE),
        ("index.php", PHP_CODE),
    ])
    def test_semantic_chunking(self, ext, code):
        from semantic_code_intelligence.indexing.semantic_chunker import semantic_chunk_code
        chunks = semantic_chunk_code(code, ext, chunk_size=2048)
        assert len(chunks) > 0
        # At least some chunks should have symbol metadata
        symbol_chunks = [c for c in chunks if c.symbol_name]
        assert len(symbol_chunks) > 0


# =========================================================================
# Edge cases
# =========================================================================


class TestEdgeCases:
    def test_empty_typescript_file(self):
        symbols = parse_file("empty.ts", "")
        assert symbols == []

    def test_empty_cpp_file(self):
        symbols = parse_file("empty.cpp", "")
        assert symbols == []

    def test_empty_ruby_file(self):
        symbols = parse_file("empty.rb", "")
        assert symbols == []

    def test_minimal_typescript(self):
        symbols = parse_file("min.ts", "const x = 1;")
        assert isinstance(symbols, list)

    def test_minimal_cpp(self):
        symbols = parse_file("min.cpp", "int main() { return 0; }")
        fns = [s for s in symbols if s.kind == "function"]
        assert any(s.name == "main" for s in fns)

    def test_minimal_csharp(self):
        symbols = parse_file("min.cs", "using System;")
        imports = [s for s in symbols if s.kind == "import"]
        assert len(imports) >= 1

    def test_minimal_ruby(self):
        symbols = parse_file("min.rb", "def hello; end")
        fns = [s for s in symbols if s.kind == "function"]
        assert any(s.name == "hello" for s in fns)

    def test_minimal_php(self):
        code = "<?php\nfunction test() { return 1; }\n"
        symbols = parse_file("min.php", code)
        fns = [s for s in symbols if s.kind == "function"]
        assert any(s.name == "test" for s in fns)

    def test_symbol_line_numbers(self):
        """Symbol start_line should be >= 1."""
        for code, path in [
            (TYPESCRIPT_CODE, "t.ts"),
            (CPP_CODE, "t.cpp"),
            (CSHARP_CODE, "t.cs"),
            (RUBY_CODE, "t.rb"),
            (PHP_CODE, "t.php"),
        ]:
            symbols = parse_file(path, code)
            for s in symbols:
                assert s.start_line >= 1, f"{path}: {s.name} has start_line {s.start_line}"
                assert s.end_line >= s.start_line
