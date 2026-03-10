//! File scanner — parallel directory walk with blake3 hashing.
//!
//! Replaces the Python `scan_repository` and `compute_file_hash` functions.
//! Uses `rayon` for parallel file hashing and `blake3` (3× faster than SHA-256).

use blake3;
use pyo3::prelude::*;
use rayon::prelude::*;
use std::collections::HashSet;
use std::fs;
use std::path::{Path, PathBuf};

/// Represents a scanned file (returned to Python).
#[pyclass]
#[derive(Clone)]
pub struct ScannedFileResult {
    #[pyo3(get)]
    pub path: String,
    #[pyo3(get)]
    pub relative_path: String,
    #[pyo3(get)]
    pub extension: String,
    #[pyo3(get)]
    pub size_bytes: u64,
    #[pyo3(get)]
    pub content_hash: String,
}

#[pymethods]
impl ScannedFileResult {
    fn __repr__(&self) -> String {
        format!("ScannedFileResult('{}')", self.relative_path)
    }
}

/// Compute a blake3 hash of a file (replaces SHA-256).
fn hash_file(path: &Path) -> Option<String> {
    let data = fs::read(path).ok()?;
    Some(blake3::hash(&data).to_hex().to_string())
}

/// Check if a relative path matches any ignore pattern.
fn matches_pattern(rel: &str, patterns: &[String]) -> bool {
    for pattern in patterns {
        // Simple glob matching (fnmatch-compatible)
        if glob_match(pattern, rel) {
            return true;
        }
    }
    false
}

/// Minimal glob matching: supports `*`, `**`, and `?`.
fn glob_match(pattern: &str, text: &str) -> bool {
    let pat = pattern.replace("\\", "/");
    let txt = text.replace("\\", "/");

    // Use globset for proper matching
    match globset::Glob::new(&pat) {
        Ok(glob) => {
            let matcher = glob.compile_matcher();
            matcher.is_match(&txt)
        }
        Err(_) => txt.contains(&pat.replace("*", "")),
    }
}

/// Load patterns from `.codexaignore` file.
fn load_ignore_patterns(root: &Path) -> Vec<String> {
    let ignore_file = root.join(".codexaignore");
    if !ignore_file.exists() {
        return Vec::new();
    }
    match fs::read_to_string(&ignore_file) {
        Ok(content) => content
            .lines()
            .map(|l| l.trim().to_string())
            .filter(|l| !l.is_empty() && !l.starts_with('#'))
            .collect(),
        Err(_) => Vec::new(),
    }
}

/// Known extensions for source code files.
fn default_extensions() -> HashSet<String> {
    [
        ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".c", ".cpp",
        ".h", ".hpp", ".rb", ".php", ".cs", ".swift", ".kt", ".scala", ".sh",
        ".bash", ".sql", ".r", ".lua", ".dart", ".ex", ".exs", ".html", ".css",
        ".json", ".yaml", ".yml", ".toml", ".xml", ".md", ".txt",
    ]
    .iter()
    .map(|s| s.to_string())
    .collect()
}

/// Default directories to ignore.
fn default_ignore_dirs() -> HashSet<String> {
    [
        ".git",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".eggs",
        "target",
        ".codexa",
    ]
    .iter()
    .map(|s| s.to_string())
    .collect()
}

#[pyclass]
pub struct RustScanner;

#[pymethods]
impl RustScanner {
    #[new]
    fn new() -> Self {
        Self
    }

    /// Compute blake3 hash of a single file.
    #[staticmethod]
    fn compute_file_hash(file_path: &str) -> PyResult<String> {
        let path = Path::new(file_path);
        hash_file(path).ok_or_else(|| {
            pyo3::exceptions::PyIOError::new_err(format!("Cannot read file: {}", file_path))
        })
    }

    /// Scan a repository for indexable files. Returns list of ScannedFileResult.
    ///
    /// Uses `rayon` for parallel hash computation and `blake3` hashing.
    #[staticmethod]
    #[pyo3(signature = (root, extensions = None, ignore_dirs = None, exclude_patterns = None))]
    fn scan_repository(
        root: &str,
        extensions: Option<Vec<String>>,
        ignore_dirs: Option<Vec<String>>,
        exclude_patterns: Option<Vec<String>>,
    ) -> PyResult<Vec<ScannedFileResult>> {
        let root_path = Path::new(root).canonicalize().map_err(|e| {
            pyo3::exceptions::PyIOError::new_err(format!("Cannot resolve root: {}", e))
        })?;

        let ext_set: HashSet<String> = extensions
            .map(|v| v.into_iter().collect())
            .unwrap_or_else(default_extensions);

        let dir_set: HashSet<String> = ignore_dirs
            .map(|v| v.into_iter().collect())
            .unwrap_or_else(default_ignore_dirs);

        let ignore_patterns = load_ignore_patterns(&root_path);
        let exclude = exclude_patterns.unwrap_or_default();

        // Collect all candidate file paths (sequential walk — IO bound)
        let mut candidates: Vec<PathBuf> = Vec::new();
        collect_files(&root_path, &root_path, &ext_set, &dir_set, &ignore_patterns, &exclude, &mut candidates);
        candidates.sort();

        // Parallel hash computation (CPU bound)
        let results: Vec<ScannedFileResult> = candidates
            .par_iter()
            .filter_map(|file_path| {
                let rel = file_path
                    .strip_prefix(&root_path)
                    .ok()?
                    .to_str()?
                    .to_string();
                let ext = file_path
                    .extension()
                    .and_then(|e| e.to_str())
                    .map(|e| format!(".{}", e))
                    .unwrap_or_default();
                let size = fs::metadata(file_path).ok()?.len();
                let hash = hash_file(file_path)?;

                Some(ScannedFileResult {
                    path: file_path.to_str()?.to_string(),
                    relative_path: rel,
                    extension: ext,
                    size_bytes: size,
                    content_hash: hash,
                })
            })
            .collect();

        Ok(results)
    }
}

/// Recursively collect file paths (filtering by ext and ignore rules).
fn collect_files(
    current: &Path,
    root: &Path,
    ext_set: &HashSet<String>,
    dir_set: &HashSet<String>,
    ignore_patterns: &[String],
    exclude_patterns: &[String],
    out: &mut Vec<PathBuf>,
) {
    let entries = match fs::read_dir(current) {
        Ok(e) => e,
        Err(_) => return,
    };

    for entry in entries {
        let entry = match entry {
            Ok(e) => e,
            Err(_) => continue,
        };
        let path = entry.path();

        if path.is_dir() {
            let name = path
                .file_name()
                .and_then(|n| n.to_str())
                .unwrap_or("");
            if dir_set.contains(name) {
                continue;
            }
            collect_files(&path, root, ext_set, dir_set, ignore_patterns, exclude_patterns, out);
        } else if path.is_file() {
            let ext = path
                .extension()
                .and_then(|e| e.to_str())
                .map(|e| format!(".{}", e.to_ascii_lowercase()))
                .unwrap_or_default();
            if !ext_set.contains(&ext) {
                continue;
            }
            if let Ok(rel) = path.strip_prefix(root) {
                let rel_str = rel.to_str().unwrap_or("").replace("\\", "/");
                if !ignore_patterns.is_empty() && matches_pattern(&rel_str, ignore_patterns) {
                    continue;
                }
                if !exclude_patterns.is_empty() && matches_pattern(&rel_str, exclude_patterns) {
                    continue;
                }
                out.push(path);
            }
        }
    }
}
