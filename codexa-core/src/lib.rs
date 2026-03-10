//! CodexA Rust core — native search and indexing engine.
//!
//! Provides drop-in replacements for Python FAISS vector store, BM25 index,
//! code chunker, file scanner, and hybrid RRF fusion.

use pyo3::prelude::*;

mod ann;
mod bm25;
mod chunk;
mod hybrid;
mod scan;

/// The top-level Python module exposed via PyO3.
#[pymodule]
fn codexa_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Vector store (replaces FAISS)
    m.add_class::<ann::RustVectorStore>()?;
    m.add_class::<ann::ChunkMeta>()?;

    // BM25 text search (replaces Python BM25Index)
    m.add_class::<bm25::RustBM25Index>()?;

    // Code chunker (replaces Python chunk_code)
    m.add_class::<chunk::RustChunker>()?;

    // File scanner (blake3 hashing, parallel walk)
    m.add_class::<scan::RustScanner>()?;
    m.add_class::<scan::ScannedFileResult>()?;

    // Hybrid search (RRF fusion)
    m.add_function(wrap_pyfunction!(hybrid::reciprocal_rank_fusion_rs, m)?)?;

    Ok(())
}
