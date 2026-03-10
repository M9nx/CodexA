//! BM25 keyword search — pure Rust implementation.
//!
//! Mirrors the Python `BM25Index` class with identical tokenisation
//! (camelCase splitting) and scoring (BM25 with k1=1.5, b=0.75).

use pyo3::prelude::*;
use pyo3::types::PyType;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::Path;
use std::sync::LazyLock;

use crate::ann::ChunkMeta;

// Pre-compiled regex for tokenisation — matches Python's behaviour exactly.
static TOKEN_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"[a-z]+|[A-Z][a-z]*|[0-9]+").unwrap());

/// Tokenise text by camelCase boundaries, lowercased.
fn tokenize(text: &str) -> Vec<String> {
    TOKEN_RE
        .find_iter(text)
        .map(|m| m.as_str().to_ascii_lowercase())
        .collect()
}

// ---------------------------------------------------------------------------
// Serialisation helpers — compatible with Python BM25 JSON format
// ---------------------------------------------------------------------------

#[derive(Serialize, Deserialize)]
struct BM25Persist {
    n: usize,
    avgdl: f64,
    doc_lengths: Vec<usize>,
    /// term → { "doc_idx_str": freq }
    inverted: HashMap<String, HashMap<String, usize>>,
}

// ---------------------------------------------------------------------------
// RustBM25Index
// ---------------------------------------------------------------------------

#[pyclass]
pub struct RustBM25Index {
    n: usize,
    avgdl: f64,
    doc_lengths: Vec<usize>,
    /// term → { doc_idx → freq }
    inverted: HashMap<String, HashMap<usize, usize>>,
}

#[pymethods]
impl RustBM25Index {
    /// Build a BM25 index from chunk metadata contents.
    #[new]
    fn new(metadata: Vec<ChunkMeta>) -> Self {
        let n = metadata.len();
        let mut doc_lengths = Vec::with_capacity(n);
        let mut inverted: HashMap<String, HashMap<usize, usize>> = HashMap::new();
        let mut total_len: usize = 0;

        for (idx, meta) in metadata.iter().enumerate() {
            let tokens = tokenize(&meta.content);
            let len = tokens.len();
            doc_lengths.push(len);
            total_len += len;

            // Count term frequencies for this document
            let mut seen: HashMap<String, usize> = HashMap::new();
            for tok in &tokens {
                *seen.entry(tok.clone()).or_default() += 1;
            }
            for (tok, freq) in seen {
                inverted.entry(tok).or_default().insert(idx, freq);
            }
        }

        let avgdl = if n > 0 {
            total_len as f64 / n as f64
        } else {
            1.0
        };

        Self {
            n,
            avgdl,
            doc_lengths,
            inverted,
        }
    }

    /// Search the index. Returns list of (doc_index, bm25_score) descending.
    fn search(&self, query: &str, top_k: usize) -> Vec<(usize, f64)> {
        let k1: f64 = 1.5;
        let b: f64 = 0.75;

        let query_tokens = tokenize(query);
        if query_tokens.is_empty() {
            return Vec::new();
        }

        // Deduplicate query tokens
        let unique: std::collections::HashSet<&str> =
            query_tokens.iter().map(|s| s.as_str()).collect();

        let mut scores: HashMap<usize, f64> = HashMap::new();

        for token in unique {
            let postings = match self.inverted.get(token) {
                Some(p) => p,
                None => continue,
            };
            let df = postings.len() as f64;
            let idf = ((self.n as f64 - df + 0.5) / (df + 0.5) + 1.0).ln();

            for (&doc_idx, &tf) in postings {
                let dl = self.doc_lengths[doc_idx] as f64;
                let tf_f = tf as f64;
                let numerator = tf_f * (k1 + 1.0);
                let denominator = tf_f + k1 * (1.0 - b + b * dl / self.avgdl);
                *scores.entry(doc_idx).or_default() += idf * numerator / denominator;
            }
        }

        let mut ranked: Vec<(usize, f64)> = scores.into_iter().collect();
        ranked.sort_unstable_by(|a, b| {
            b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal)
        });
        ranked.truncate(top_k);
        ranked
    }

    /// Persist the BM25 index to `bm25_index.json` (Python-compatible format).
    fn save(&self, directory: &str) -> PyResult<()> {
        let dir = Path::new(directory);
        fs::create_dir_all(dir)
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;

        let path = dir.join("bm25_index.json");

        // Convert int keys to string keys for JSON compatibility
        let inverted_str: HashMap<String, HashMap<String, usize>> = self
            .inverted
            .iter()
            .map(|(term, postings)| {
                let str_postings: HashMap<String, usize> =
                    postings.iter().map(|(k, v)| (k.to_string(), *v)).collect();
                (term.clone(), str_postings)
            })
            .collect();

        let data = BM25Persist {
            n: self.n,
            avgdl: self.avgdl,
            doc_lengths: self.doc_lengths.clone(),
            inverted: inverted_str,
        };

        let json = serde_json::to_string(&data)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        fs::write(&path, json)
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;

        Ok(())
    }

    /// Load a persisted BM25 index. Returns None if missing or stale.
    #[classmethod]
    fn load(
        _cls: &Bound<'_, PyType>,
        directory: &str,
        expected_count: usize,
    ) -> PyResult<Option<Self>> {
        let path = Path::new(directory).join("bm25_index.json");
        if !path.exists() {
            return Ok(None);
        }

        let json = match fs::read_to_string(&path) {
            Ok(s) => s,
            Err(_) => return Ok(None),
        };

        let data: BM25Persist = match serde_json::from_str(&json) {
            Ok(d) => d,
            Err(_) => return Ok(None),
        };

        // Stale check: doc count must match
        if data.n != expected_count {
            return Ok(None);
        }

        // Convert string keys back to int
        let inverted: HashMap<String, HashMap<usize, usize>> = data
            .inverted
            .into_iter()
            .map(|(term, postings)| {
                let int_postings: HashMap<usize, usize> = postings
                    .into_iter()
                    .filter_map(|(k, v)| k.parse::<usize>().ok().map(|idx| (idx, v)))
                    .collect();
                (term, int_postings)
            })
            .collect();

        Ok(Some(Self {
            n: data.n,
            avgdl: data.avgdl,
            doc_lengths: data.doc_lengths,
            inverted,
        }))
    }

    #[getter]
    fn doc_count(&self) -> usize {
        self.n
    }

    #[getter]
    fn term_count(&self) -> usize {
        self.inverted.len()
    }

    fn __repr__(&self) -> String {
        format!(
            "RustBM25Index(docs={}, terms={})",
            self.n,
            self.inverted.len()
        )
    }
}
