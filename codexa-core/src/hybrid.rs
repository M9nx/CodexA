//! Reciprocal Rank Fusion — merges semantic and keyword ranked lists.
//!
//! Mirrors the Python `reciprocal_rank_fusion` function exactly.

use pyo3::prelude::*;
use std::collections::HashMap;

/// Fuse two ranked lists via Reciprocal Rank Fusion.
///
/// Args:
///     semantic_ranking: [(chunk_index, score), ...] ordered best-first.
///     keyword_ranking:  [(chunk_index, score), ...] ordered best-first.
///     k: RRF smoothing constant (default 60).
///
/// Returns:
///     [(chunk_index, fused_score, semantic_score, keyword_score), ...]
///     sorted by fused_score descending.
#[pyfunction]
#[pyo3(signature = (semantic_ranking, keyword_ranking, k = 60))]
pub fn reciprocal_rank_fusion_rs(
    semantic_ranking: Vec<(usize, f64)>,
    keyword_ranking: Vec<(usize, f64)>,
    k: usize,
) -> Vec<(usize, f64, f64, f64)> {
    let mut scores: HashMap<usize, f64> = HashMap::new();
    let mut sem_scores: HashMap<usize, f64> = HashMap::new();
    let mut kw_scores: HashMap<usize, f64> = HashMap::new();

    for (rank, &(idx, score)) in semantic_ranking.iter().enumerate() {
        *scores.entry(idx).or_default() += 1.0 / (k as f64 + rank as f64 + 1.0);
        sem_scores.insert(idx, score);
    }

    for (rank, &(idx, score)) in keyword_ranking.iter().enumerate() {
        *scores.entry(idx).or_default() += 1.0 / (k as f64 + rank as f64 + 1.0);
        kw_scores.insert(idx, score);
    }

    let mut fused: Vec<(usize, f64, f64, f64)> = scores
        .into_iter()
        .map(|(idx, fused_score)| {
            (
                idx,
                fused_score,
                *sem_scores.get(&idx).unwrap_or(&0.0),
                *kw_scores.get(&idx).unwrap_or(&0.0),
            )
        })
        .collect();

    fused.sort_unstable_by(|a, b| {
        b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal)
    });

    fused
}
