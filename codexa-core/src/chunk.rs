//! Code chunker — splits source files into line-boundary chunks.
//!
//! Mirrors the Python `chunk_code` function exactly: accumulate lines up to
//! `chunk_size` characters, then walk backwards for `chunk_overlap` overlap.

use pyo3::prelude::*;
use std::collections::HashMap;
use std::path::Path;

// Map file extensions to language names (matches Python EXTENSION_TO_LANGUAGE)
fn extension_to_language() -> HashMap<&'static str, &'static str> {
    let mut m = HashMap::new();
    m.insert(".py", "python");
    m.insert(".js", "javascript");
    m.insert(".ts", "typescript");
    m.insert(".jsx", "javascript");
    m.insert(".tsx", "typescript");
    m.insert(".java", "java");
    m.insert(".go", "go");
    m.insert(".rs", "rust");
    m.insert(".c", "c");
    m.insert(".cpp", "cpp");
    m.insert(".h", "c");
    m.insert(".hpp", "cpp");
    m.insert(".rb", "ruby");
    m.insert(".php", "php");
    m.insert(".cs", "csharp");
    m.insert(".swift", "swift");
    m.insert(".kt", "kotlin");
    m.insert(".scala", "scala");
    m.insert(".sh", "shell");
    m.insert(".bash", "shell");
    m.insert(".sql", "sql");
    m.insert(".r", "r");
    m.insert(".lua", "lua");
    m.insert(".dart", "dart");
    m.insert(".ex", "elixir");
    m.insert(".exs", "elixir");
    m
}

/// Detect language from file extension.
fn detect_language(file_path: &str) -> String {
    let ext = Path::new(file_path)
        .extension()
        .and_then(|e| e.to_str())
        .map(|e| format!(".{}", e.to_ascii_lowercase()))
        .unwrap_or_default();

    let map = extension_to_language();
    map.get(ext.as_str())
        .unwrap_or(&"unknown")
        .to_string()
}

/// A single code chunk (returned to Python as a dict for compatibility).
#[derive(Clone)]
struct CodeChunkData {
    file_path: String,
    content: String,
    start_line: usize, // 1-indexed
    end_line: usize,
    chunk_index: usize,
    language: String,
}

impl IntoPy<PyObject> for CodeChunkData {
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
pub struct RustChunker;

#[pymethods]
impl RustChunker {
    #[new]
    fn new() -> Self {
        Self
    }

    /// Detect language from a file path.
    #[staticmethod]
    fn detect_language(file_path: &str) -> String {
        detect_language(file_path)
    }

    /// Split source code into overlapping chunks by line boundaries.
    ///
    /// Returns a list of dicts with keys:
    /// file_path, content, start_line, end_line, chunk_index, language
    #[staticmethod]
    #[pyo3(signature = (content, file_path, chunk_size = 512, chunk_overlap = 64))]
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

        let language = detect_language(file_path);

        // Split into lines keeping line endings
        let mut lines: Vec<String> = Vec::new();
        let mut start = 0;
        for (i, ch) in content.char_indices() {
            if ch == '\n' {
                lines.push(content[start..=i].to_string());
                start = i + 1;
            }
        }
        if start < content.len() {
            lines.push(content[start..].to_string());
        }

        let mut chunks: Vec<CodeChunkData> = Vec::new();
        let mut current_chars: usize = 0;
        let mut chunk_start_line: usize = 0;
        let mut chunk_lines: Vec<String> = Vec::new();
        let mut chunk_index: usize = 0;

        for (i, line) in lines.iter().enumerate() {
            chunk_lines.push(line.clone());
            current_chars += line.len();

            if current_chars >= chunk_size {
                let chunk_text: String = chunk_lines.concat();
                chunks.push(CodeChunkData {
                    file_path: file_path.to_string(),
                    content: chunk_text,
                    start_line: chunk_start_line + 1,
                    end_line: i + 1,
                    chunk_index,
                    language: language.clone(),
                });
                chunk_index += 1;

                // Calculate overlap: walk backwards
                let mut overlap_chars: usize = 0;
                let mut overlap_start = chunk_lines.len();
                for j in (0..chunk_lines.len()).rev() {
                    overlap_chars += chunk_lines[j].len();
                    if overlap_chars >= chunk_overlap {
                        overlap_start = j;
                        break;
                    }
                }

                chunk_lines = chunk_lines[overlap_start..].to_vec();
                chunk_start_line = (i + 1) - chunk_lines.len();
                current_chars = chunk_lines.iter().map(|l| l.len()).sum();
            }
        }

        // Emit last chunk if content remains
        if !chunk_lines.is_empty() {
            let chunk_text: String = chunk_lines.concat();
            if !chunk_text.trim().is_empty() {
                chunks.push(CodeChunkData {
                    file_path: file_path.to_string(),
                    content: chunk_text,
                    start_line: chunk_start_line + 1,
                    end_line: lines.len(),
                    chunk_index,
                    language: language.clone(),
                });
            }
        }

        Python::with_gil(|py| chunks.into_iter().map(|c| c.into_py(py)).collect())
    }

    /// Chunk a file from disk.
    #[staticmethod]
    #[pyo3(signature = (file_path, chunk_size = 512, chunk_overlap = 64))]
    fn chunk_file(
        file_path: &str,
        chunk_size: usize,
        chunk_overlap: usize,
    ) -> PyResult<Vec<PyObject>> {
        let content = std::fs::read_to_string(file_path)
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;
        Ok(Self::chunk_code(&content, file_path, chunk_size, chunk_overlap))
    }
}
