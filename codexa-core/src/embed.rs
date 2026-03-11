//! ONNX embedding inference — feature-gated behind `onnx`.
//!
//! Loads a sentence-transformer model exported to ONNX and runs inference
//! entirely in Rust via `ort` (ONNX Runtime).  This removes the Python
//! sentence-transformers / torch dependency at embedding time.
//!
//! Compile with:  `maturin develop --release --features onnx`

#[cfg(feature = "onnx")]
mod inner {
    use ndarray::{Array2, CowArray, Ix2};
    use ort::{Session, Value};
    use pyo3::prelude::*;
    use std::path::Path;

    /// Minimal tokenizer-free embedder.
    ///
    /// Expects pre-tokenized `input_ids` and `attention_mask` arrays (i64).
    /// Typical workflow:
    ///   1. Python side tokenizes text → numpy arrays
    ///   2. `OnnxEmbedder.embed(input_ids, attention_mask)` → numpy f32 embeddings
    ///
    /// This avoids re-implementing a tokenizer in Rust while offloading the
    /// heavy matrix maths to ONNX Runtime.
    #[pyclass]
    pub struct OnnxEmbedder {
        session: Session,
    }

    #[pymethods]
    impl OnnxEmbedder {
        /// Load an ONNX model from `model_path`.
        #[new]
        fn new(model_path: &str) -> PyResult<Self> {
            let path = Path::new(model_path);
            if !path.exists() {
                return Err(pyo3::exceptions::PyFileNotFoundError::new_err(format!(
                    "ONNX model not found: {}",
                    model_path
                )));
            }

            let session = Session::builder()
                .and_then(|b| b.with_model_from_file(path))
                .map_err(|e| {
                    pyo3::exceptions::PyRuntimeError::new_err(format!(
                        "Failed to load ONNX model: {}",
                        e
                    ))
                })?;

            Ok(Self { session })
        }

        /// Run embedding inference.
        ///
        /// `input_ids`:      i64 array  [batch, seq_len]
        /// `attention_mask`:  i64 array  [batch, seq_len]
        ///
        /// Returns: f32 array [batch, embed_dim]  (mean-pooled last hidden state).
        fn embed(
            &self,
            py: Python<'_>,
            input_ids: numpy::PyReadonlyArray2<'_, i64>,
            attention_mask: numpy::PyReadonlyArray2<'_, i64>,
        ) -> PyResult<Py<numpy::PyArray2<f32>>> {
            let ids = input_ids.as_array();
            let mask = attention_mask.as_array();

            let (batch, seq_len) = ids.dim();
            if mask.dim() != (batch, seq_len) {
                return Err(pyo3::exceptions::PyValueError::new_err(
                    "input_ids and attention_mask shape mismatch",
                ));
            }

            // Build ONNX runtime input tensors
            let ids_cow = CowArray::from(ids.into_owned()).into_dimensionality::<Ix2>().unwrap();
            let mask_cow = CowArray::from(mask.into_owned()).into_dimensionality::<Ix2>().unwrap();

            let ids_value = Value::from_array(&ids_cow)
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            let mask_value = Value::from_array(&mask_cow)
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

            let outputs = self
                .session
                .run(ort::inputs![ids_value, mask_value].map_err(|e| {
                    pyo3::exceptions::PyRuntimeError::new_err(e.to_string())
                })?)
                .map_err(|e| {
                    pyo3::exceptions::PyRuntimeError::new_err(format!(
                        "ONNX inference failed: {}",
                        e
                    ))
                })?;

            // Extract last_hidden_state  [batch, seq_len, hidden]
            let hidden = outputs[0]
                .try_extract_tensor::<f32>()
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

            let hidden_view = hidden.view();
            let hidden_dim = hidden_view.shape();
            let embed_dim = hidden_dim[2];

            // Mean pooling with attention mask
            let mut result = Array2::<f32>::zeros((batch, embed_dim));
            for b in 0..batch {
                let mut sum = vec![0.0f32; embed_dim];
                let mut count = 0.0f32;
                for s in 0..seq_len {
                    let m = mask_cow[[b, s]] as f32;
                    if m > 0.0 {
                        for d in 0..embed_dim {
                            sum[d] += hidden_view[[b, s, d]] * m;
                        }
                        count += m;
                    }
                }
                if count > 0.0 {
                    for d in 0..embed_dim {
                        result[[b, d]] = sum[d] / count;
                    }
                }
            }

            // L2 normalize each embedding
            for b in 0..batch {
                let mut norm: f32 = 0.0;
                for d in 0..embed_dim {
                    norm += result[[b, d]] * result[[b, d]];
                }
                let norm = norm.sqrt().max(1e-12);
                for d in 0..embed_dim {
                    result[[b, d]] /= norm;
                }
            }

            let py_arr = numpy::PyArray2::from_owned_array_bound(py, result).unbind();
            Ok(py_arr)
        }

        fn __repr__(&self) -> String {
            "OnnxEmbedder(loaded)".to_string()
        }
    }
}

#[cfg(feature = "onnx")]
pub use inner::OnnxEmbedder;
