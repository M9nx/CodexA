//! Vector store — brute-force inner-product search with rayon parallelism.
//!
//! Drop-in replacement for the Python FAISS-backed VectorStore.
//! Uses flat inner-product search (matching IndexFlatIP behaviour).
//! Vectors are stored as a contiguous `Vec<f32>` for cache-friendly access.
//! Supports memory-mapped loading via `load_mmap` for near-instant startup.

use memmap2::Mmap;
use numpy::{PyArray1, PyReadonlyArray1, PyReadonlyArray2};
use pyo3::prelude::*;
use pyo3::types::PyType;
use rayon::prelude::*;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::Path;

// ---------------------------------------------------------------------------
// ChunkMeta — mirrors Python ChunkMetadata dataclass
// ---------------------------------------------------------------------------

#[pyclass]
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ChunkMeta {
    #[pyo3(get, set)]
    pub file_path: String,
    #[pyo3(get, set)]
    pub start_line: usize,
    #[pyo3(get, set)]
    pub end_line: usize,
    #[pyo3(get, set)]
    pub chunk_index: usize,
    #[pyo3(get, set)]
    pub language: String,
    #[pyo3(get, set)]
    pub content: String,
    #[pyo3(get, set)]
    pub content_hash: String,
}

#[pymethods]
impl ChunkMeta {
    #[new]
    #[pyo3(signature = (file_path, start_line, end_line, chunk_index, language, content, content_hash = String::new()))]
    fn new(
        file_path: String,
        start_line: usize,
        end_line: usize,
        chunk_index: usize,
        language: String,
        content: String,
        content_hash: String,
    ) -> Self {
        Self {
            file_path,
            start_line,
            end_line,
            chunk_index,
            language,
            content,
            content_hash,
        }
    }

    fn to_dict(&self) -> HashMap<String, PyObject> {
        Python::with_gil(|py| {
            let mut d = HashMap::new();
            d.insert("file_path".into(), self.file_path.clone().into_py(py));
            d.insert("start_line".into(), self.start_line.into_py(py));
            d.insert("end_line".into(), self.end_line.into_py(py));
            d.insert("chunk_index".into(), self.chunk_index.into_py(py));
            d.insert("language".into(), self.language.clone().into_py(py));
            d.insert("content".into(), self.content.clone().into_py(py));
            d.insert("content_hash".into(), self.content_hash.clone().into_py(py));
            d
        })
    }

    fn __repr__(&self) -> String {
        format!(
            "ChunkMeta(file_path='{}', lines={}-{}, chunk={})",
            self.file_path, self.start_line, self.end_line, self.chunk_index
        )
    }
}

// ---------------------------------------------------------------------------
// VectorStorage — owned or memory-mapped
// ---------------------------------------------------------------------------

enum FlatVectorStorage {
    Owned(Vec<f32>),
    Mmap {
        _mmap: Mmap,
        ptr: *const f32,
        len: usize,
    },
}

unsafe impl Send for FlatVectorStorage {}
unsafe impl Sync for FlatVectorStorage {}

impl FlatVectorStorage {
    fn as_slice(&self) -> &[f32] {
        match self {
            FlatVectorStorage::Owned(v) => v.as_slice(),
            FlatVectorStorage::Mmap { ptr, len, .. } => unsafe {
                std::slice::from_raw_parts(*ptr, *len)
            },
        }
    }

    fn to_owned_mut(&mut self) -> &mut Vec<f32> {
        if let FlatVectorStorage::Mmap { ptr, len, .. } = self {
            let slice = unsafe { std::slice::from_raw_parts(*ptr, *len) };
            *self = FlatVectorStorage::Owned(slice.to_vec());
        }
        match self {
            FlatVectorStorage::Owned(v) => v,
            _ => unreachable!(),
        }
    }
}

// ---------------------------------------------------------------------------
// VectorStore — flat inner-product search
// ---------------------------------------------------------------------------

#[pyclass]
pub struct RustVectorStore {
    dimension: usize,
    /// Flat contiguous storage: vectors[i*dim .. (i+1)*dim]
    vectors: FlatVectorStorage,
    metadata: Vec<ChunkMeta>,
    /// file_path → set of vector indices
    file_index: HashMap<String, Vec<usize>>,
}

#[pymethods]
impl RustVectorStore {
    #[new]
    fn new(dimension: usize) -> Self {
        Self {
            dimension,
            vectors: FlatVectorStorage::Owned(Vec::new()),
            metadata: Vec::new(),
            file_index: HashMap::new(),
        }
    }

    /// Number of stored vectors.
    #[getter]
    fn size(&self) -> usize {
        self.metadata.len()
    }

    /// Embedding dimensionality.
    #[getter]
    fn dimension_size(&self) -> usize {
        self.dimension
    }

    /// Add embeddings (n × dim numpy array) and their metadata.
    fn add(
        &mut self,
        embeddings: PyReadonlyArray2<'_, f32>,
        metadata_list: Vec<ChunkMeta>,
    ) -> PyResult<()> {
        let arr = embeddings.as_array();
        let (n, dim) = arr.dim();
        if dim != self.dimension {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "Expected dimension {}, got {}",
                self.dimension, dim
            )));
        }
        if n != metadata_list.len() {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "Embedding count ({}) != metadata count ({})",
                n,
                metadata_list.len()
            )));
        }
        if n == 0 {
            return Ok(());
        }

        let base_idx = self.metadata.len();
        let vec_store = self.vectors.to_owned_mut();
        vec_store.reserve(n * dim);

        for i in 0..n {
            let idx = base_idx + i;
            self.file_index
                .entry(metadata_list[i].file_path.clone())
                .or_default()
                .push(idx);

            // Append vector data (row-major from numpy)
            for j in 0..dim {
                vec_store.push(arr[[i, j]]);
            }
        }
        self.metadata.extend(metadata_list);

        Ok(())
    }

    /// Search for the top-k most similar vectors via inner product.
    ///
    /// Returns list of (ChunkMeta, score) tuples sorted by score descending.
    fn search(
        &self,
        _py: Python<'_>,
        query_embedding: PyReadonlyArray1<'_, f32>,
        top_k: usize,
    ) -> PyResult<Vec<(ChunkMeta, f32)>> {
        let q = query_embedding
            .as_slice()
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        if q.len() != self.dimension {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "Query dimension {} != store dimension {}",
                q.len(),
                self.dimension
            )));
        }

        let n = self.metadata.len();
        if n == 0 {
            return Ok(Vec::new());
        }

        let dim = self.dimension;
        let data = self.vectors.as_slice();

        // Parallel inner-product computation
        let mut scores: Vec<(usize, f32)> = (0..n)
            .into_par_iter()
            .map(|i| {
                let offset = i * dim;
                let mut dot: f32 = 0.0;
                // Manual loop for autovectorisation
                for j in 0..dim {
                    dot += unsafe { *data.get_unchecked(offset + j) } * unsafe { *q.get_unchecked(j) };
                }
                (i, dot)
            })
            .collect();

        // Partial sort: we only need top-k
        let k = top_k.min(n);
        scores.select_nth_unstable_by(k.saturating_sub(1), |a, b| {
            b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal)
        });
        scores.truncate(k);
        scores.sort_unstable_by(|a, b| {
            b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal)
        });

        Ok(scores
            .into_iter()
            .map(|(idx, score)| (self.metadata[idx].clone(), score))
            .collect())
    }

    /// Persist vectors and metadata to directory.
    ///
    /// Writes `vectors.bin` (binary f32) and `metadata.json` (compatible
    /// with the Python VectorStore format).
    fn save(&self, directory: &str) -> PyResult<()> {
        let dir = Path::new(directory);
        fs::create_dir_all(dir)
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;

        // --- vectors.bin: [dim:u64][count:u64][f32 × dim × count] ---
        let vec_path = dir.join("vectors.bin");
        let data = self.vectors.as_slice();
        let total_floats = data.len();
        let mut buf = Vec::with_capacity(16 + total_floats * 4);
        buf.extend_from_slice(&(self.dimension as u64).to_le_bytes());
        buf.extend_from_slice(&(self.metadata.len() as u64).to_le_bytes());
        for &v in data {
            buf.extend_from_slice(&v.to_le_bytes());
        }
        fs::write(&vec_path, &buf)
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;

        // --- metadata.json: same schema as Python VectorStore ---
        let meta_path = dir.join("metadata.json");
        let json = serde_json::to_string(&self.metadata)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        fs::write(&meta_path, json)
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;

        Ok(())
    }

    /// Load a vector store from directory (reads file into memory).
    #[classmethod]
    fn load(_cls: &Bound<'_, PyType>, directory: &str) -> PyResult<Self> {
        let dir = Path::new(directory);

        // --- Load vectors.bin ---
        let vec_path = dir.join("vectors.bin");
        let data = fs::read(&vec_path)
            .map_err(|e| pyo3::exceptions::PyFileNotFoundError::new_err(e.to_string()))?;
        if data.len() < 16 {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "Invalid vectors.bin: file too small",
            ));
        }
        let dimension = u64::from_le_bytes(data[0..8].try_into().unwrap()) as usize;
        let count = u64::from_le_bytes(data[8..16].try_into().unwrap()) as usize;
        let float_data = &data[16..];
        let expected = count * dimension * 4;
        if float_data.len() < expected {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "Truncated vectors.bin: expected {} bytes, got {}",
                expected,
                float_data.len()
            )));
        }
        let vectors: Vec<f32> = float_data[..expected]
            .chunks_exact(4)
            .map(|b| f32::from_le_bytes(b.try_into().unwrap()))
            .collect();

        // --- Load metadata.json ---
        let meta_path = dir.join("metadata.json");
        let meta_json = fs::read_to_string(&meta_path)
            .map_err(|e| pyo3::exceptions::PyFileNotFoundError::new_err(e.to_string()))?;
        let metadata: Vec<ChunkMeta> = serde_json::from_str(&meta_json)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        if metadata.len() != count {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "Metadata count ({}) != vector count ({})",
                metadata.len(),
                count
            )));
        }

        // Rebuild file index
        let mut file_index: HashMap<String, Vec<usize>> = HashMap::new();
        for (i, m) in metadata.iter().enumerate() {
            file_index.entry(m.file_path.clone()).or_default().push(i);
        }

        Ok(Self {
            dimension,
            vectors: FlatVectorStorage::Owned(vectors),
            metadata,
            file_index,
        })
    }

    /// Load a vector store with memory-mapped I/O for near-instant startup.
    ///
    /// The vector data stays on disk and is paged in by the OS on demand.
    /// Mutations (add / remove) will copy the data to heap first.
    #[classmethod]
    fn load_mmap(_cls: &Bound<'_, PyType>, directory: &str) -> PyResult<Self> {
        let dir = Path::new(directory);

        let vec_path = dir.join("vectors.bin");
        let file = fs::File::open(&vec_path)
            .map_err(|e| pyo3::exceptions::PyFileNotFoundError::new_err(e.to_string()))?;
        let mmap = unsafe { Mmap::map(&file) }
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;

        if mmap.len() < 16 {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "Invalid vectors.bin: file too small",
            ));
        }

        let dimension = u64::from_le_bytes(mmap[0..8].try_into().unwrap()) as usize;
        let count = u64::from_le_bytes(mmap[8..16].try_into().unwrap()) as usize;
        let expected = count * dimension * 4;
        if mmap.len() < 16 + expected {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "Truncated vectors.bin",
            ));
        }

        let float_count = count * dimension;
        let ptr = mmap[16..].as_ptr() as *const f32;

        // Load metadata.json
        let meta_path = dir.join("metadata.json");
        let meta_json = fs::read_to_string(&meta_path)
            .map_err(|e| pyo3::exceptions::PyFileNotFoundError::new_err(e.to_string()))?;
        let metadata: Vec<ChunkMeta> = serde_json::from_str(&meta_json)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        if metadata.len() != count {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "Metadata count ({}) != vector count ({})",
                metadata.len(),
                count
            )));
        }

        let mut file_index: HashMap<String, Vec<usize>> = HashMap::new();
        for (i, m) in metadata.iter().enumerate() {
            file_index.entry(m.file_path.clone()).or_default().push(i);
        }

        Ok(Self {
            dimension,
            vectors: FlatVectorStorage::Mmap {
                _mmap: mmap,
                ptr,
                len: float_count,
            },
            metadata,
            file_index,
        })
    }

    /// Remove all vectors for a given file path. Returns count removed.
    fn remove_by_file(&mut self, file_path: &str) -> usize {
        let indices = match self.file_index.remove(file_path) {
            Some(v) => v,
            None => return 0,
        };
        let count = indices.len();
        let remove_set: std::collections::HashSet<usize> = indices.into_iter().collect();

        // Single-pass rebuild (no shifting)
        let dim = self.dimension;
        let data = self.vectors.as_slice();
        let mut new_vectors = Vec::with_capacity(data.len() - count * dim);
        let mut new_metadata = Vec::with_capacity(self.metadata.len() - count);

        for (i, meta) in self.metadata.iter().enumerate() {
            if !remove_set.contains(&i) {
                new_metadata.push(meta.clone());
                let start = i * dim;
                new_vectors.extend_from_slice(&data[start..start + dim]);
            }
        }

        self.vectors = FlatVectorStorage::Owned(new_vectors);
        self.metadata = new_metadata;

        // Rebuild file index
        self.file_index.clear();
        for (i, m) in self.metadata.iter().enumerate() {
            self.file_index.entry(m.file_path.clone()).or_default().push(i);
        }

        count
    }

    /// Get vectors and metadata for all chunks belonging to a file.
    fn get_vectors_for_file<'py>(
        &self,
        py: Python<'py>,
        file_path: &str,
    ) -> Vec<(ChunkMeta, Py<PyArray1<f32>>)> {
        let indices = match self.file_index.get(file_path) {
            Some(v) => v,
            None => return Vec::new(),
        };
        let dim = self.dimension;
        let data = self.vectors.as_slice();
        indices
            .iter()
            .map(|&idx| {
                let meta = self.metadata[idx].clone();
                let start = idx * dim;
                let slice = &data[start..start + dim];
                let arr = PyArray1::from_slice_bound(py, slice).unbind();
                (meta, arr)
            })
            .collect()
    }

    /// Clear all stored data.
    fn clear(&mut self) {
        self.vectors = FlatVectorStorage::Owned(Vec::new());
        self.metadata.clear();
        self.file_index.clear();
    }

    fn __len__(&self) -> usize {
        self.metadata.len()
    }

    fn __repr__(&self) -> String {
        format!(
            "RustVectorStore(dimension={}, vectors={})",
            self.dimension,
            self.metadata.len()
        )
    }
}
