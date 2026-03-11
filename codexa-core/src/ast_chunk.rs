//! AST-aware code chunker using tree-sitter.
//!
//! Parses source files with tree-sitter grammars (9 languages) and chunks at
//! function / class / method boundaries.  Falls back to the existing
//! line-boundary chunker for unsupported languages.

use pyo3::prelude::*;
use std::path::Path;
use tree_sitter::Parser;

// ── Language helpers ────────────────────────────────────────────────────────

/// Returns a tree-sitter `Language` for the given language id, or `None` if
/// we don't have a grammar for it.
fn get_language(lang: &str) -> Option<tree_sitter::Language> {
    let lang_fn = match lang {
        "python" => tree_sitter_python::LANGUAGE,
        "javascript" => tree_sitter_javascript::LANGUAGE,
        "typescript" => tree_sitter_typescript::LANGUAGE_TYPESCRIPT,
        "tsx" => tree_sitter_typescript::LANGUAGE_TSX,
        "rust" => tree_sitter_rust::LANGUAGE,
        "go" => tree_sitter_go::LANGUAGE,
        "java" => tree_sitter_java::LANGUAGE,
        "c" => tree_sitter_c::LANGUAGE,
        "cpp" => tree_sitter_cpp::LANGUAGE,
        "ruby" => tree_sitter_ruby::LANGUAGE,
        _ => return None,
    };
    Some(lang_fn.into())
}

/// Node kinds that represent "definition" boundaries per language.
fn is_definition_node(lang: &str, kind: &str) -> bool {
    match lang {
        "python" => matches!(
            kind,
            "function_definition" | "class_definition" | "decorated_definition"
        ),
        "javascript" | "tsx" => matches!(
            kind,
            "function_declaration"
                | "class_declaration"
                | "export_statement"
                | "lexical_declaration"
                | "variable_declaration"
        ),
        "typescript" => matches!(
            kind,
            "function_declaration"
                | "class_declaration"
                | "export_statement"
                | "lexical_declaration"
                | "variable_declaration"
                | "interface_declaration"
                | "type_alias_declaration"
        ),
        "rust" => matches!(
            kind,
            "function_item"
                | "impl_item"
                | "struct_item"
                | "enum_item"
                | "mod_item"
                | "trait_item"
                | "type_item"
                | "const_item"
                | "static_item"
                | "macro_definition"
        ),
        "go" => matches!(
            kind,
            "function_declaration" | "method_declaration" | "type_declaration"
        ),
        "java" => matches!(
            kind,
            "class_declaration"
                | "method_declaration"
                | "interface_declaration"
                | "enum_declaration"
                | "constructor_declaration"
        ),
        "c" => matches!(
            kind,
            "function_definition" | "struct_specifier" | "enum_specifier" | "declaration"
        ),
        "cpp" => matches!(
            kind,
            "function_definition"
                | "class_specifier"
                | "struct_specifier"
                | "enum_specifier"
                | "namespace_definition"
                | "template_declaration"
        ),
        "ruby" => matches!(kind, "method" | "class" | "module" | "singleton_method"),
        _ => false,
    }
}

// ── Detected span ──────────────────────────────────────────────────────────

/// A contiguous range of lines that belong to one or more top-level definitions.
struct Span {
    _start_byte: usize,
    _end_byte: usize,
    _start_row: usize, // 0-indexed
    end_row: usize,    // 0-indexed, inclusive
}

/// Walk the tree's immediate children to find definition boundaries.
fn collect_definition_spans(
    tree: &tree_sitter::Tree,
    lang: &str,
) -> Vec<Span> {
    let root = tree.root_node();
    let mut spans = Vec::new();

    let mut cursor = root.walk();
    for child in root.children(&mut cursor) {
        if is_definition_node(lang, child.kind()) {
            spans.push(Span {
                _start_byte: child.start_byte(),
                _end_byte: child.end_byte(),
                _start_row: child.start_position().row,
                end_row: child.end_position().row,
            });
        } else {
            // For languages with nested definitions at top level (e.g. Java
            // where everything is inside `program > class_declaration`),
            // also check grandchildren.
            let mut inner_cursor = child.walk();
            for grandchild in child.children(&mut inner_cursor) {
                if is_definition_node(lang, grandchild.kind()) {
                    spans.push(Span {
                        _start_byte: grandchild.start_byte(),
                        _end_byte: grandchild.end_byte(),
                        _start_row: grandchild.start_position().row,
                        end_row: grandchild.end_position().row,
                    });
                }
            }
        }
    }

    spans
}

// ── Public chunker ─────────────────────────────────────────────────────────

/// Result chunk dictionary (returned to Python).
#[derive(Clone)]
struct AstChunkData {
    file_path: String,
    content: String,
    start_line: usize,
    end_line: usize,
    chunk_index: usize,
    language: String,
}

impl IntoPy<PyObject> for AstChunkData {
    fn into_py(self, py: Python<'_>) -> PyObject {
        let dict = pyo3::types::PyDict::new_bound(py);
        dict.set_item("file_path", &self.file_path).unwrap();
        dict.set_item("content", &self.content).unwrap();
        dict.set_item("start_line", self.start_line).unwrap();
        dict.set_item("end_line", self.end_line).unwrap();
        dict.set_item("chunk_index", self.chunk_index).unwrap();
        dict.set_item("language", &self.language).unwrap();
        dict.into_py(py)
    }
}

#[pyclass]
pub struct AstChunker;

#[pymethods]
impl AstChunker {
    #[new]
    fn new() -> Self {
        Self
    }

    /// AST-aware chunk.
    ///
    /// Parses the source with tree-sitter, groups top-level definitions into
    /// chunks that fit within `chunk_size` characters, and returns a list of
    /// dicts identical in shape to `RustChunker.chunk_code`.
    ///
    /// Falls back to line-boundary chunking for unsupported languages.
    #[staticmethod]
    #[pyo3(signature = (content, file_path, chunk_size = 1500, chunk_overlap = 200))]
    fn chunk_code(
        content: &str,
        file_path: &str,
        chunk_size: usize,
        chunk_overlap: usize,
    ) -> Vec<PyObject> {
        let trimmed = content.trim();
        if trimmed.is_empty() {
            return Vec::new();
        }

        let lang = detect_lang(file_path);
        let ts_lang = get_language(&lang);

        // If we don't have a grammar → fall back to line-boundary
        let ts_lang = match ts_lang {
            Some(l) => l,
            None => {
                return crate::chunk::RustChunker::chunk_code_fallback(
                    content,
                    file_path,
                    chunk_size,
                    chunk_overlap,
                );
            }
        };

        let mut parser = Parser::new();
        if parser.set_language(&ts_lang).is_err() {
            return crate::chunk::RustChunker::chunk_code_fallback(
                content,
                file_path,
                chunk_size,
                chunk_overlap,
            );
        }

        let tree = match parser.parse(content, None) {
            Some(t) => t,
            None => {
                return crate::chunk::RustChunker::chunk_code_fallback(
                    content,
                    file_path,
                    chunk_size,
                    chunk_overlap,
                );
            }
        };

        let spans = collect_definition_spans(&tree, &lang);

        // No definitions found → treat as a single or line-boundary chunk
        if spans.is_empty() {
            return crate::chunk::RustChunker::chunk_code_fallback(
                content,
                file_path,
                chunk_size,
                chunk_overlap,
            );
        }

        let lines: Vec<&str> = content.lines().collect();
        let total_lines = lines.len();

        // Build region list: (start_line 0-idx, end_line 0-idx inclusive)
        // Include gaps between definitions as part of the following definition
        // (e.g. imports, comments preceding a function).
        let mut regions: Vec<(usize, usize)> = Vec::new();
        let mut prev_end: usize = 0;

        for span in &spans {
            let region_start = prev_end;
            let region_end = span.end_row;
            regions.push((region_start, region_end));
            prev_end = span.end_row + 1;
        }

        // Trailing code after last definition
        if prev_end < total_lines {
            // Append to the last region
            if let Some(last) = regions.last_mut() {
                last.1 = total_lines - 1;
            }
        }

        // Now merge regions into chunks ≤ chunk_size characters
        let mut chunks: Vec<AstChunkData> = Vec::new();
        let mut chunk_index = 0usize;
        let mut cur_start: Option<usize> = None;
        let mut cur_end: usize = 0;
        let mut cur_chars: usize = 0;

        for (rs, re) in &regions {
            let region_text_len: usize = (*rs..=*re)
                .filter_map(|l| lines.get(l))
                .map(|l| l.len() + 1) // +1 for newline
                .sum();

            match cur_start {
                None => {
                    cur_start = Some(*rs);
                    cur_end = *re;
                    cur_chars = region_text_len;
                }
                Some(cs) => {
                    if cur_chars + region_text_len > chunk_size {
                        // Flush current chunk
                        let text = line_range_text(&lines, cs, cur_end);
                        chunks.push(AstChunkData {
                            file_path: file_path.to_string(),
                            content: text,
                            start_line: cs + 1,
                            end_line: cur_end + 1,
                            chunk_index,
                            language: lang.clone(),
                        });
                        chunk_index += 1;

                        // Compute overlap: take last `chunk_overlap` chars
                        // from the previous chunk boundary
                        let overlap_start =
                            find_overlap_start(&lines, cs, cur_end, chunk_overlap);

                        cur_start = Some(overlap_start.min(*rs));
                        cur_end = *re;
                        cur_chars = line_range_len(&lines, cur_start.unwrap(), cur_end);
                    } else {
                        cur_end = *re;
                        cur_chars += region_text_len;
                    }
                }
            }
        }

        // Flush remaining
        if let Some(cs) = cur_start {
            let text = line_range_text(&lines, cs, cur_end);
            if !text.trim().is_empty() {
                chunks.push(AstChunkData {
                    file_path: file_path.to_string(),
                    content: text,
                    start_line: cs + 1,
                    end_line: cur_end + 1,
                    chunk_index,
                    language: lang.clone(),
                });
            }
        }

        Python::with_gil(|py| chunks.into_iter().map(|c| c.into_py(py)).collect())
    }

    /// Chunk a file from disk using AST-aware splitting.
    #[staticmethod]
    #[pyo3(signature = (file_path, chunk_size = 1500, chunk_overlap = 200))]
    fn chunk_file(
        file_path: &str,
        chunk_size: usize,
        chunk_overlap: usize,
    ) -> PyResult<Vec<PyObject>> {
        let content = std::fs::read_to_string(file_path)
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;
        Ok(Self::chunk_code(&content, file_path, chunk_size, chunk_overlap))
    }

    /// List supported languages for AST chunking.
    #[staticmethod]
    fn supported_languages() -> Vec<&'static str> {
        vec![
            "python",
            "javascript",
            "typescript",
            "tsx",
            "rust",
            "go",
            "java",
            "c",
            "cpp",
            "ruby",
        ]
    }
}

// ── Helpers ────────────────────────────────────────────────────────────────

fn detect_lang(file_path: &str) -> String {
    let ext = Path::new(file_path)
        .extension()
        .and_then(|e| e.to_str())
        .map(|e| e.to_ascii_lowercase())
        .unwrap_or_default();

    match ext.as_str() {
        "py" => "python",
        "js" | "jsx" | "mjs" => "javascript",
        "ts" => "typescript",
        "tsx" => "tsx",
        "rs" => "rust",
        "go" => "go",
        "java" => "java",
        "c" | "h" => "c",
        "cpp" | "cc" | "cxx" | "hpp" | "hxx" => "cpp",
        "rb" => "ruby",
        _ => "unknown",
    }
    .to_string()
}

/// Concatenate lines from start..=end (0-indexed) into a string with newlines.
fn line_range_text(lines: &[&str], start: usize, end: usize) -> String {
    let end = end.min(lines.len().saturating_sub(1));
    let mut result = String::new();
    for i in start..=end {
        result.push_str(lines[i]);
        if i < end {
            result.push('\n');
        }
    }
    result
}

fn line_range_len(lines: &[&str], start: usize, end: usize) -> usize {
    let end = end.min(lines.len().saturating_sub(1));
    (start..=end)
        .map(|i| lines[i].len() + 1)
        .sum::<usize>()
}

/// Walk backwards from `end` towards `start` to find the first line where
/// the accumulated character count exceeds `overlap`.
fn find_overlap_start(
    lines: &[&str],
    start: usize,
    end: usize,
    overlap: usize,
) -> usize {
    let mut chars = 0usize;
    for i in (start..=end).rev() {
        chars += lines[i].len() + 1;
        if chars >= overlap {
            return i;
        }
    }
    start
}
