//! HNSW vector index — approximate nearest-neighbour search.
//!
//! Replaces the flat brute-force `RustVectorStore` for large-scale repos.
//! Uses `instant-distance` for O(log n) queries and supports memory-mapped
//! persistence via `memmap2`.

use instant_distance::{Builder, HnswMap, Search};
use memmap2::Mmap;
use numpy::{PyArray1, PyReadonlyArray1, PyReadonlyArray2};
use pyo3::prelude::*;
use pyo3::types::PyType;
use std::collections::HashMap;
use std::fs;
use std::path::Path;

use crate::ann::ChunkMeta;

// ---------------------------------------------------------------------------
// Point wrapper for instant-distance
// ---------------------------------------------------------------------------

/// A point in embedding space — wraps a `Vec<f32>` and implements the
/// `instant_distance::Point` trait using inner-product distance.
#[derive(Clone, Debug)]
struct EmbeddingPoint {
    vec: Vec<f32>,
}

impl instant_distance::Point for EmbeddingPoint {
    fn distance(&self, other: &Self) -> f32 {
        // instant-distance expects *distance* (lower = closer).
        // We use inner-product similarity → distance = 1 − dot.
        let dot: f32 = self
            .vec
            .iter()
            .zip(other.vec.iter())
            .map(|(a, b)| a * b)
            .sum();
        1.0 - dot
    }
}

// ---------------------------------------------------------------------------
// Persistence format (header + raw vectors + metadata JSON)
// ---------------------------------------------------------------------------

/// Compact header for the mmap file.
/// Layout: [magic:4][version:u32][dim:u32][count:u32][meta_offset:u64]
///         [f32 × dim × count][metadata_json_bytes]
const MAGIC: &[u8; 4] = b"CXHW";
const VERSION: u32 = 1;
const HEADER_SIZE: usize = 4 + 4 + 4 + 4 + 8; // 24 bytes

// ---------------------------------------------------------------------------
// HnswVectorStore
// ---------------------------------------------------------------------------

#[pyclass]
pub struct HnswVectorStore {
    dimension: usize,
    /// Raw vector data (owned or mmap-backed)
    vectors: VectorStorage,
    metadata: Vec<ChunkMeta>,
    file_index: HashMap<String, Vec<usize>>,
    /// The HNSW index (rebuilt after mutations)
    index: Option<HnswMap<EmbeddingPoint, usize>>,
    /// Whether the index needs rebuilding before next search
    dirty: bool,
}

/// Vectors can be heap-owned or memory-mapped.
enum VectorStorage {
    Owned(Vec<f32>),
    Mmap {
        _mmap: Mmap,
        ptr: *const f32,
        len: usize,
    },
}

// SAFETY: the mmap pointer is valid for the lifetime of the Mmap handle
// which we keep alive inside VectorStorage.
unsafe impl Send for VectorStorage {}
unsafe impl Sync for VectorStorage {}

impl VectorStorage {
    fn as_slice(&self) -> &[f32] {
        match self {
            VectorStorage::Owned(v) => v.as_slice(),
            VectorStorage::Mmap { ptr, len, .. } => unsafe {
                std::slice::from_raw_parts(*ptr, *len)
            },
        }
    }

    /// Convert to owned storage (required before mutation).
    fn to_owned_mut(&mut self) -> &mut Vec<f32> {
        if let VectorStorage::Mmap { ptr, len, .. } = self {
            let slice = unsafe { std::slice::from_raw_parts(*ptr, *len) };
            *self = VectorStorage::Owned(slice.to_vec());
        }
        match self {
            VectorStorage::Owned(v) => v,
            _ => unreachable!(),
        }
    }
}

impl HnswVectorStore {
    /// Build HNSW index from current vectors.
    fn build_index(&mut self) {
        let n = self.metadata.len();
        if n == 0 {
            self.index = None;
            self.dirty = false;
            return;
        }

        let dim = self.dimension;
        let data = self.vectors.as_slice();

        let points: Vec<EmbeddingPoint> = (0..n)
            .map(|i| {
                let offset = i * dim;
                EmbeddingPoint {
                    vec: data[offset..offset + dim].to_vec(),
                }
            })
            .collect();

        let values: Vec<usize> = (0..n).collect();

        let hnsw = Builder::default().build(points, values);
        self.index = Some(hnsw);
        self.dirty = false;
    }
}

#[pymethods]
impl HnswVectorStore {
    #[new]
    fn new(dimension: usize) -> Self {
        Self {
            dimension,
            vectors: VectorStorage::Owned(Vec::new()),
            metadata: Vec::new(),
            file_index: HashMap::new(),
            index: None,
            dirty: false,
        }
    }

    #[getter]
    fn size(&self) -> usize {
        self.metadata.len()
    }

    #[getter]
    fn dimension_size(&self) -> usize {
        self.dimension
    }

    /// Add embeddings and metadata. Marks the HNSW index as dirty.
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
            for j in 0..dim {
                vec_store.push(arr[[i, j]]);
            }
        }
        self.metadata.extend(metadata_list);
        self.dirty = true;

        Ok(())
    }

    /// Search for top-k nearest neighbours via HNSW.
    ///
    /// Automatically rebuilds the index if dirty.
    /// Returns list of (ChunkMeta, score) tuples sorted by score descending.
    fn search(
        &mut self,
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

        if self.metadata.is_empty() {
            return Ok(Vec::new());
        }

        // Rebuild HNSW if needed
        if self.dirty || self.index.is_none() {
            self.build_index();
        }

        let hnsw = self.index.as_ref().unwrap();
        let query_point = EmbeddingPoint { vec: q.to_vec() };

        let mut search = Search::default();
        let results = hnsw.search(&query_point, &mut search);

        let mut out: Vec<(ChunkMeta, f32)> = results
            .take(top_k)
            .map(|item| {
                let idx = *item.value;
                let score = 1.0 - item.distance; // convert distance back to similarity
                (self.metadata[idx].clone(), score)
            })
            .collect();

        // Ensure sorted by score descending (HNSW returns sorted by distance ascending)
        out.sort_unstable_by(|a, b| {
            b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal)
        });

        Ok(out)
    }

    /// Save to directory with mmap-friendly binary format.
    ///
    /// Writes `hnsw_vectors.bin` (mmap-ready) and reuses `metadata.json`.
    fn save(&self, directory: &str) -> PyResult<()> {
        let dir = Path::new(directory);
        fs::create_dir_all(dir)
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;

        let count = self.metadata.len();
        let dim = self.dimension;
        let data = self.vectors.as_slice();

        // Serialize metadata to JSON
        let meta_json = serde_json::to_vec(&self.metadata)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        let meta_offset = (HEADER_SIZE + count * dim * 4) as u64;

        // Build the binary file
        let vec_path = dir.join("hnsw_vectors.bin");
        let total_size = HEADER_SIZE + count * dim * 4 + meta_json.len();
        let mut buf = Vec::with_capacity(total_size);

        // Header
        buf.extend_from_slice(MAGIC);
        buf.extend_from_slice(&VERSION.to_le_bytes());
        buf.extend_from_slice(&(dim as u32).to_le_bytes());
        buf.extend_from_slice(&(count as u32).to_le_bytes());
        buf.extend_from_slice(&meta_offset.to_le_bytes());

        // Vector data
        for &v in &data[..count * dim] {
            buf.extend_from_slice(&v.to_le_bytes());
        }

        // Metadata JSON
        buf.extend_from_slice(&meta_json);

        fs::write(&vec_path, &buf)
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;

        // Also write metadata.json for compatibility with RustVectorStore
        let meta_path = dir.join("metadata.json");
        let json_str = serde_json::to_string(&self.metadata)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        fs::write(&meta_path, json_str)
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;

        Ok(())
    }

    /// Load from directory using memory-mapped I/O for near-instant startup.
    #[classmethod]
    fn load(_cls: &Bound<'_, PyType>, directory: &str) -> PyResult<Self> {
        let dir = Path::new(directory);
        let vec_path = dir.join("hnsw_vectors.bin");

        let file = fs::File::open(&vec_path)
            .map_err(|e| pyo3::exceptions::PyFileNotFoundError::new_err(e.to_string()))?;

        // Memory-map the file
        let mmap = unsafe { Mmap::map(&file) }
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;

        if mmap.len() < HEADER_SIZE {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "Invalid hnsw_vectors.bin: file too small",
            ));
        }

        // Parse header
        let magic = &mmap[0..4];
        if magic != MAGIC {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "Invalid hnsw_vectors.bin: bad magic",
            ));
        }
        let version = u32::from_le_bytes(mmap[4..8].try_into().unwrap());
        if version != VERSION {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "Unsupported hnsw_vectors.bin version: {}",
                version
            )));
        }
        let dim = u32::from_le_bytes(mmap[8..12].try_into().unwrap()) as usize;
        let count = u32::from_le_bytes(mmap[12..16].try_into().unwrap()) as usize;
        let meta_offset = u64::from_le_bytes(mmap[16..24].try_into().unwrap()) as usize;

        // Validate sizes
        let vec_bytes = count * dim * 4;
        if mmap.len() < HEADER_SIZE + vec_bytes {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "Truncated hnsw_vectors.bin",
            ));
        }

        // Parse metadata
        let meta_json = &mmap[meta_offset..];
        let metadata: Vec<ChunkMeta> = serde_json::from_slice(meta_json)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        if metadata.len() != count {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "Metadata count ({}) != vector count ({})",
                metadata.len(),
                count
            )));
        }

        // Build file index
        let mut file_index: HashMap<String, Vec<usize>> = HashMap::new();
        for (i, m) in metadata.iter().enumerate() {
            file_index.entry(m.file_path.clone()).or_default().push(i);
        }

        // Set up mmap-backed vector storage
        let float_count = count * dim;
        let vec_start = HEADER_SIZE;
        // Verify alignment — f32 requires 4-byte alignment
        let ptr = mmap[vec_start..].as_ptr() as *const f32;

        let storage = VectorStorage::Mmap {
            _mmap: mmap,
            ptr,
            len: float_count,
        };

        let mut store = Self {
            dimension: dim,
            vectors: storage,
            metadata,
            file_index,
            index: None,
            dirty: true, // will build HNSW on first search
        };

        // Pre-build the HNSW index
        store.build_index();

        Ok(store)
    }

    /// Remove all vectors for a given file path. Marks index as dirty.
    fn remove_by_file(&mut self, file_path: &str) -> usize {
        let indices = match self.file_index.remove(file_path) {
            Some(v) => v,
            None => return 0,
        };
        let count = indices.len();
        let remove_set: std::collections::HashSet<usize> = indices.into_iter().collect();

        let dim = self.dimension;
        let data = self.vectors.as_slice();
        let mut new_vectors: Vec<f32> = Vec::with_capacity(data.len() - count * dim);
        let mut new_metadata = Vec::with_capacity(self.metadata.len() - count);

        for (i, meta) in self.metadata.iter().enumerate() {
            if !remove_set.contains(&i) {
                new_metadata.push(meta.clone());
                let start = i * dim;
                new_vectors.extend_from_slice(&data[start..start + dim]);
            }
        }

        self.vectors = VectorStorage::Owned(new_vectors);
        self.metadata = new_metadata;

        self.file_index.clear();
        for (i, m) in self.metadata.iter().enumerate() {
            self.file_index.entry(m.file_path.clone()).or_default().push(i);
        }

        self.dirty = true;
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

    fn clear(&mut self) {
        self.vectors = VectorStorage::Owned(Vec::new());
        self.metadata.clear();
        self.file_index.clear();
        self.index = None;
        self.dirty = false;
    }

    fn __len__(&self) -> usize {
        self.metadata.len()
    }

    fn __repr__(&self) -> String {
        format!(
            "HnswVectorStore(dimension={}, vectors={}, indexed={})",
            self.dimension,
            self.metadata.len(),
            self.index.is_some() && !self.dirty,
        )
    }
}
