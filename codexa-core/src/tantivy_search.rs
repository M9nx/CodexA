//! Tantivy full-text search backend — optional feature.
//!
//! Provides a PyO3-exposed `TantivyIndex` class wrapping a Tantivy
//! index for BM25-quality full-text search with sub-100ms query latency.
//! Documents are code chunks (file_path, content, language, line range).

#[cfg(feature = "tantivy-backend")]
use pyo3::prelude::*;

#[cfg(feature = "tantivy-backend")]
use tantivy::{
    collector::TopDocs,
    doc,
    query::QueryParser,
    schema::{Field, Schema, STORED, TEXT},
    Index, IndexReader, IndexWriter, ReloadPolicy,
};

#[cfg(feature = "tantivy-backend")]
use std::path::PathBuf;

/// A Tantivy-backed full-text search index for code chunks.
///
/// Wraps Tantivy's inverted index for BM25-quality full-text search.
/// Created via `TantivyIndex(directory)` — the index is disk-persistent.
#[cfg(feature = "tantivy-backend")]
#[pyclass]
pub struct TantivyIndex {
    index: Index,
    reader: IndexReader,
    f_file_path: Field,
    f_content: Field,
    f_language: Field,
    f_start_line: Field,
    f_end_line: Field,
    f_chunk_index: Field,
    schema: Schema,
    index_dir: PathBuf,
}

#[cfg(feature = "tantivy-backend")]
#[pymethods]
impl TantivyIndex {
    /// Create or open a Tantivy index at the given directory.
    #[new]
    fn new(directory: String) -> PyResult<Self> {
        let dir = PathBuf::from(&directory);
        std::fs::create_dir_all(&dir).map_err(|e| {
            pyo3::exceptions::PyIOError::new_err(format!("Cannot create index dir: {e}"))
        })?;

        let mut schema_builder = Schema::builder();
        let f_file_path = schema_builder.add_text_field("file_path", STORED);
        let f_content = schema_builder.add_text_field("content", TEXT | STORED);
        let f_language = schema_builder.add_text_field("language", STORED);
        let f_start_line = schema_builder.add_text_field("start_line", STORED);
        let f_end_line = schema_builder.add_text_field("end_line", STORED);
        let f_chunk_index = schema_builder.add_text_field("chunk_index", STORED);
        let schema = schema_builder.build();

        let mmap_dir =
            tantivy::directory::MmapDirectory::open(&dir).map_err(|e| {
                pyo3::exceptions::PyIOError::new_err(format!("Tantivy dir error: {e}"))
            })?;

        let index = Index::open_or_create(mmap_dir, schema.clone()).map_err(|e| {
            pyo3::exceptions::PyRuntimeError::new_err(format!("Tantivy index error: {e}"))
        })?;

        let reader = index
            .reader_builder()
            .reload_policy(ReloadPolicy::OnCommitWithDelay)
            .try_into()
            .map_err(|e| {
                pyo3::exceptions::PyRuntimeError::new_err(format!("Reader error: {e}"))
            })?;

        Ok(Self {
            index,
            reader,
            f_file_path,
            f_content,
            f_language,
            f_start_line,
            f_end_line,
            f_chunk_index,
            schema,
            index_dir: dir,
        })
    }

    /// Add a batch of code chunks to the index.
    ///
    /// Each chunk is a tuple: (file_path, content, language, start_line, end_line, chunk_index)
    fn add_chunks(&self, chunks: Vec<(String, String, String, usize, usize, usize)>) -> PyResult<u64> {
        let mut writer: IndexWriter = self.index.writer(50_000_000).map_err(|e| {
            pyo3::exceptions::PyRuntimeError::new_err(format!("Writer error: {e}"))
        })?;

        let mut count = 0u64;
        for (fp, content, lang, sl, el, ci) in chunks {
            writer.add_document(doc!(
                self.f_file_path => fp,
                self.f_content => content,
                self.f_language => lang,
                self.f_start_line => sl.to_string(),
                self.f_end_line => el.to_string(),
                self.f_chunk_index => ci.to_string(),
            )).map_err(|e| {
                pyo3::exceptions::PyRuntimeError::new_err(format!("Add doc error: {e}"))
            })?;
            count += 1;
        }

        writer.commit().map_err(|e| {
            pyo3::exceptions::PyRuntimeError::new_err(format!("Commit error: {e}"))
        })?;

        Ok(count)
    }

    /// Search the index for a query string, returning up to `top_k` results.
    ///
    /// Returns a list of (file_path, content, language, start_line, end_line, chunk_index, score).
    fn search(&self, query: &str, top_k: usize) -> PyResult<Vec<(String, String, String, usize, usize, usize, f32)>> {
        let searcher = self.reader.searcher();
        let query_parser = QueryParser::for_index(&self.index, vec![self.f_content]);
        let parsed = query_parser.parse_query(query).map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!("Query parse error: {e}"))
        })?;

        let top_docs = searcher.search(&parsed, &TopDocs::with_limit(top_k)).map_err(|e| {
            pyo3::exceptions::PyRuntimeError::new_err(format!("Search error: {e}"))
        })?;

        let mut results = Vec::with_capacity(top_docs.len());
        for (score, doc_address) in top_docs {
            let doc = searcher.doc::<tantivy::TantivyDocument>(doc_address).map_err(|e| {
                pyo3::exceptions::PyRuntimeError::new_err(format!("Doc fetch error: {e}"))
            })?;

            let get_text = |field: Field| -> String {
                doc.get_first(field)
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string()
            };

            let file_path = get_text(self.f_file_path);
            let content = get_text(self.f_content);
            let language = get_text(self.f_language);
            let start_line: usize = get_text(self.f_start_line).parse().unwrap_or(0);
            let end_line: usize = get_text(self.f_end_line).parse().unwrap_or(0);
            let chunk_index: usize = get_text(self.f_chunk_index).parse().unwrap_or(0);

            results.push((file_path, content, language, start_line, end_line, chunk_index, score));
        }

        Ok(results)
    }

    /// Remove all documents for a given file path.
    fn remove_file(&self, file_path: &str) -> PyResult<u64> {
        let mut writer: IndexWriter = self.index.writer(50_000_000).map_err(|e| {
            pyo3::exceptions::PyRuntimeError::new_err(format!("Writer error: {e}"))
        })?;

        let term = tantivy::Term::from_field_text(self.f_file_path, file_path);
        writer.delete_term(term);
        writer.commit().map_err(|e| {
            pyo3::exceptions::PyRuntimeError::new_err(format!("Commit error: {e}"))
        })?;

        Ok(0) // Tantivy doesn't easily report deleted count
    }

    /// Clear the entire index.
    fn clear(&self) -> PyResult<()> {
        let mut writer: IndexWriter = self.index.writer(50_000_000).map_err(|e| {
            pyo3::exceptions::PyRuntimeError::new_err(format!("Writer error: {e}"))
        })?;
        writer.delete_all_documents().map_err(|e| {
            pyo3::exceptions::PyRuntimeError::new_err(format!("Clear error: {e}"))
        })?;
        writer.commit().map_err(|e| {
            pyo3::exceptions::PyRuntimeError::new_err(format!("Commit error: {e}"))
        })?;
        Ok(())
    }

    /// Return the number of documents in the index.
    fn num_docs(&self) -> u64 {
        self.reader.searcher().num_docs()
    }
}
