//! CodexA Rust core — native search and indexing engine.
//!
//! Provides drop-in replacements for Python FAISS vector store, BM25 index,
//! code chunker, file scanner, hybrid RRF fusion, HNSW ANN index,
//! AST-aware chunker, and optional ONNX embedding inference.

use pyo3::prelude::*;

mod ann;
mod ast_chunk;
mod bm25;
pub(crate) mod chunk;
mod embed;
mod hnsw;
mod hybrid;
mod scan;

/// The top-level Python module exposed via PyO3.
#[pymodule]
fn codexa_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Vector store — flat brute-force (replaces FAISS)
    m.add_class::<ann::RustVectorStore>()?;
    m.add_class::<ann::ChunkMeta>()?;

    // Vector store — HNSW approximate nearest neighbour
    m.add_class::<hnsw::HnswVectorStore>()?;

    // BM25 text search (replaces Python BM25Index)
    m.add_class::<bm25::RustBM25Index>()?;

    // Code chunker — line-boundary (replaces Python chunk_code)
    m.add_class::<chunk::RustChunker>()?;

    // Code chunker — AST-aware (tree-sitter, 10 languages)
    m.add_class::<ast_chunk::AstChunker>()?;

    // File scanner (blake3 hashing, parallel walk)
    m.add_class::<scan::RustScanner>()?;
    m.add_class::<scan::ScannedFileResult>()?;

    // Hybrid search (RRF fusion)
    m.add_function(wrap_pyfunction!(hybrid::reciprocal_rank_fusion_rs, m)?)?;

    // ONNX embedder (only when compiled with --features onnx)
    #[cfg(feature = "onnx")]
    m.add_class::<embed::OnnxEmbedder>()?;

    Ok(())
}
