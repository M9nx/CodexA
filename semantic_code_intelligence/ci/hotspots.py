"""Hotspot detection engine — identifies high-risk, high-impact code areas.

Computes a weighted risk score per file and symbol using:
- Cyclomatic complexity
- Duplication density
- Dependency fan-in / fan-out
- Historical change frequency (git log, if available)
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from semantic_code_intelligence.context.engine import CallGraph, DependencyMap
from semantic_code_intelligence.parsing.parser import Symbol
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("ci.hotspots")

# ── Weight defaults ──────────────────────────────────────────────────

_W_COMPLEXITY = 0.30
_W_DUPLICATION = 0.20
_W_FAN_IN = 0.15
_W_FAN_OUT = 0.15
_W_CHURN = 0.20


@dataclass
class HotspotFactor:
    """A single contributing factor to a hotspot score."""

    name: str
    raw_value: float
    normalized: float  # 0-1
    weight: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "raw_value": round(self.raw_value, 2),
            "normalized": round(self.normalized, 3),
            "weight": self.weight,
        }


@dataclass
class Hotspot:
    """A detected hotspot — file or symbol with risk score."""

    name: str
    file_path: str
    kind: str  # "file" or "symbol"
    risk_score: float  # 0-100
    factors: list[HotspotFactor] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "file_path": self.file_path,
            "kind": self.kind,
            "risk_score": round(self.risk_score, 1),
            "factors": [f.to_dict() for f in self.factors],
        }


@dataclass
class HotspotReport:
    """Result of hotspot analysis."""

    files_analyzed: int
    symbols_analyzed: int
    hotspots: list[Hotspot] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "files_analyzed": self.files_analyzed,
            "symbols_analyzed": self.symbols_analyzed,
            "hotspot_count": len(self.hotspots),
            "hotspots": [h.to_dict() for h in self.hotspots],
        }


# ── Git churn ────────────────────────────────────────────────────────


def _git_change_counts(project_root: Path) -> dict[str, int]:
    """Return commit-count-per-file via ``git log --name-only``.

    Returns an empty dict if git is unavailable or the directory is not
    a repository.
    """
    try:
        result = subprocess.run(
            ["git", "log", "--name-only", "--pretty=format:"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            return {}
    except Exception:
        return {}

    counts: dict[str, int] = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if line:
            counts[line] = counts.get(line, 0) + 1
    return counts


# ── Normalisation helpers ────────────────────────────────────────────


def _normalise(value: float, max_val: float) -> float:
    """Normalise *value* to [0, 1] given *max_val*."""
    if max_val <= 0:
        return 0.0
    return min(value / max_val, 1.0)


# ── Core analyser ────────────────────────────────────────────────────


def analyze_hotspots(
    symbols: list[Symbol],
    call_graph: CallGraph,
    dep_map: DependencyMap,
    project_root: Path,
    *,
    top_n: int = 20,
    include_git: bool = True,
    weights: dict[str, float] | None = None,
) -> HotspotReport:
    """Detect hotspots across files in the project.

    Args:
        symbols: All parsed symbols.
        call_graph: Pre-built call graph.
        dep_map: Pre-built dependency map.
        project_root: Project root for git and path resolution.
        top_n: Maximum hotspots to return.
        include_git: Whether to factor git churn.
        weights: Override default factor weights.

    Returns:
        HotspotReport with ranked hotspots.
    """
    from semantic_code_intelligence.ci.quality import compute_complexity

    w = weights or {}
    w_complexity = w.get("complexity", _W_COMPLEXITY)
    w_duplication = w.get("duplication", _W_DUPLICATION)
    w_fan_in = w.get("fan_in", _W_FAN_IN)
    w_fan_out = w.get("fan_out", _W_FAN_OUT)
    w_churn = w.get("churn", _W_CHURN)

    # If no git, redistribute churn weight
    churn_map: dict[str, int] = {}
    if include_git:
        churn_map = _git_change_counts(project_root)
    if not churn_map:
        extra = w_churn / 4
        w_complexity += extra
        w_duplication += extra
        w_fan_in += extra
        w_fan_out += extra
        w_churn = 0.0

    callable_symbols = [s for s in symbols if s.kind in ("function", "method")]

    # ── Per-symbol raw metrics ───────────────────────────────────
    # Complexity
    sym_complexity: dict[str, int] = {}
    for s in callable_symbols:
        cr = compute_complexity(s)
        sym_complexity[f"{s.file_path}:{s.name}"] = cr.complexity

    max_complexity = max(sym_complexity.values(), default=1)

    # Fan-in / fan-out
    sym_fan_in: dict[str, int] = {}
    sym_fan_out: dict[str, int] = {}
    for s in callable_symbols:
        key = f"{s.file_path}:{s.name}"
        sym_fan_in[key] = len(call_graph.callers_of(s.name))
        sym_fan_out[key] = len(call_graph.callees_of(key))

    max_fan_in = max(sym_fan_in.values(), default=1)
    max_fan_out = max(sym_fan_out.values(), default=1)

    # Per-file aggregate: duplication density
    # Count how many duplicate pairs touch each file
    file_dup_count: dict[str, int] = {}
    try:
        from semantic_code_intelligence.ci.quality import detect_duplicates

        dups = detect_duplicates(callable_symbols, threshold=0.70, min_lines=3)
        for d in dups:
            file_dup_count[d.file_a] = file_dup_count.get(d.file_a, 0) + 1
            file_dup_count[d.file_b] = file_dup_count.get(d.file_b, 0) + 1
    except Exception:
        pass

    max_dup = max(file_dup_count.values(), default=1)

    # Git churn — resolve relative paths
    root = project_root.resolve()
    max_churn = max(churn_map.values(), default=1)

    # ── Score each callable symbol ───────────────────────────────
    hotspots: list[Hotspot] = []
    unique_files: set[str] = set()

    for s in callable_symbols:
        unique_files.add(s.file_path)
        key = f"{s.file_path}:{s.name}"

        cc = sym_complexity.get(key, 1)
        fi = sym_fan_in.get(key, 0)
        fo = sym_fan_out.get(key, 0)
        dp = file_dup_count.get(s.file_path, 0)

        # Resolve relative path for git churn lookup
        try:
            rel = str(Path(s.file_path).resolve().relative_to(root)).replace("\\", "/")
        except ValueError:
            rel = ""
        ch = churn_map.get(rel, 0)

        n_cc = _normalise(float(cc), float(max_complexity))
        n_fi = _normalise(float(fi), float(max_fan_in))
        n_fo = _normalise(float(fo), float(max_fan_out))
        n_dp = _normalise(float(dp), float(max_dup))
        n_ch = _normalise(float(ch), float(max_churn))

        score = (
            w_complexity * n_cc
            + w_fan_in * n_fi
            + w_fan_out * n_fo
            + w_duplication * n_dp
            + w_churn * n_ch
        ) * 100

        factors = [
            HotspotFactor("complexity", float(cc), n_cc, w_complexity),
            HotspotFactor("fan_in", float(fi), n_fi, w_fan_in),
            HotspotFactor("fan_out", float(fo), n_fo, w_fan_out),
            HotspotFactor("duplication", float(dp), n_dp, w_duplication),
        ]
        if w_churn > 0:
            factors.append(HotspotFactor("churn", float(ch), n_ch, w_churn))

        hotspots.append(Hotspot(
            name=s.name,
            file_path=s.file_path,
            kind="symbol",
            risk_score=score,
            factors=factors,
        ))

    hotspots.sort(key=lambda h: h.risk_score, reverse=True)
    return HotspotReport(
        files_analyzed=len(unique_files),
        symbols_analyzed=len(callable_symbols),
        hotspots=hotspots[:top_n],
    )
