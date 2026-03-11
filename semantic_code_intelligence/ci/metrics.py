"""Code quality metrics, trend tracking, and policy enforcement.

Provides:
- **Maintainability index** — weighted composite of complexity, comment ratio,
  LOC, and dead-code density for individual files and whole projects.
- **QualitySnapshot** — timestamped metric capture persisted via WorkspaceMemory.
- **Trend analysis** — linear-regression slope over historical snapshots for
  detecting improvement or degradation.
- **QualityPolicy / QualityGate** — configurable thresholds and CI-friendly
  gate enforcement.
"""

from __future__ import annotations

import json
import math
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from semantic_code_intelligence.ci.quality import (
    QualityReport,
    analyze_complexity,
    analyze_project,
    compute_complexity,
)
from semantic_code_intelligence.context.memory import WorkspaceMemory
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("ci.metrics")

# ── Maintainability index ────────────────────────────────────────────

# The index is inspired by the Software Engineering Institute formula:
#   MI = 171 - 5.2·ln(avgV) - 0.23·avgCC - 16.2·ln(avgLOC) + 50·sin(sqrt(2.4·%comments))
# We simplify and clamp to [0, 100] for usability.


@dataclass
class FileMetrics:
    """Per-file quality metrics."""

    file_path: str
    lines_of_code: int = 0
    comment_lines: int = 0
    blank_lines: int = 0
    avg_complexity: float = 0.0
    max_complexity: int = 0
    symbol_count: int = 0
    maintainability_index: float = 100.0

    @property
    def comment_ratio(self) -> float:
        """Fraction of lines that are comments (0.0–1.0)."""
        total = self.lines_of_code + self.comment_lines + self.blank_lines
        if total == 0:
            return 0.0
        return self.comment_lines / total

    def to_dict(self) -> dict[str, Any]:
        """Serialise file-level metrics to a plain dictionary."""
        return {
            "file_path": self.file_path,
            "lines_of_code": self.lines_of_code,
            "comment_lines": self.comment_lines,
            "blank_lines": self.blank_lines,
            "avg_complexity": round(self.avg_complexity, 2),
            "max_complexity": self.max_complexity,
            "symbol_count": self.symbol_count,
            "maintainability_index": round(self.maintainability_index, 1),
            "comment_ratio": round(self.comment_ratio, 3),
        }


@dataclass
class ProjectMetrics:
    """Project-wide quality metrics aggregation."""

    files_analyzed: int = 0
    total_loc: int = 0
    total_comment_lines: int = 0
    total_blank_lines: int = 0
    avg_complexity: float = 0.0
    max_complexity: int = 0
    total_symbols: int = 0
    maintainability_index: float = 100.0
    file_metrics: list[FileMetrics] = field(default_factory=list)

    @property
    def comment_ratio(self) -> float:
        """Fraction of lines that are comments (0.0–1.0)."""
        total = self.total_loc + self.total_comment_lines + self.total_blank_lines
        if total == 0:
            return 0.0
        return self.total_comment_lines / total

    def to_dict(self) -> dict[str, Any]:
        """Serialise project-wide metrics to a plain dictionary."""
        return {
            "files_analyzed": self.files_analyzed,
            "total_loc": self.total_loc,
            "total_comment_lines": self.total_comment_lines,
            "total_blank_lines": self.total_blank_lines,
            "avg_complexity": round(self.avg_complexity, 2),
            "max_complexity": self.max_complexity,
            "total_symbols": self.total_symbols,
            "maintainability_index": round(self.maintainability_index, 1),
            "comment_ratio": round(self.comment_ratio, 3),
            "file_metrics": [f.to_dict() for f in self.file_metrics],
        }


# Comment line patterns for common languages
_COMMENT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^\s*#"),       # Python, Ruby, Bash
    re.compile(r"^\s*//"),      # JS, TS, Java, Go, Rust, C++, C#
    re.compile(r"^\s*/\*"),     # Block comments start
    re.compile(r"^\s*\*"),      # Inside block comment
    re.compile(r"^\s*\*/"),     # Block comment end
]


def _count_lines(content: str) -> tuple[int, int, int]:
    """Return (code_lines, comment_lines, blank_lines) for source content."""
    code = 0
    comments = 0
    blanks = 0
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            blanks += 1
        elif any(p.match(line) for p in _COMMENT_PATTERNS):
            comments += 1
        else:
            code += 1
    return code, comments, blanks


def _compute_mi(avg_loc: float, avg_cc: float, comment_ratio: float) -> float:
    """Compute maintainability index (0-100 scale).

    Simplified SEI formula, clamped to [0, 100].
    """
    ln_loc = math.log(max(avg_loc, 1))
    ln_vol = math.log(max(avg_loc * max(avg_cc, 1), 1))
    sin_cm = math.sin(math.sqrt(2.4 * comment_ratio))
    raw = 171.0 - 5.2 * ln_vol - 0.23 * avg_cc - 16.2 * ln_loc + 50.0 * sin_cm
    # Normalise to 0-100
    return max(0.0, min(100.0, raw * 100.0 / 171.0))


def compute_file_metrics(file_path: str | Path) -> FileMetrics:
    """Compute quality metrics for a single file."""
    from semantic_code_intelligence.parsing.parser import parse_file

    fpath = Path(file_path)
    try:
        content = fpath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return FileMetrics(file_path=str(fpath))

    loc, comments, blanks = _count_lines(content)
    symbols = parse_file(str(fpath))

    complexities = [compute_complexity(s) for s in symbols if s.kind in ("function", "method")]
    avg_cc = sum(c.complexity for c in complexities) / max(len(complexities), 1)
    max_cc = max((c.complexity for c in complexities), default=0)

    total = loc + comments + blanks
    cr = comments / total if total > 0 else 0.0
    mi = _compute_mi(float(loc), avg_cc, cr)

    return FileMetrics(
        file_path=str(fpath),
        lines_of_code=loc,
        comment_lines=comments,
        blank_lines=blanks,
        avg_complexity=avg_cc,
        max_complexity=max_cc,
        symbol_count=len(symbols),
        maintainability_index=mi,
    )


def compute_project_metrics(
    project_root: Path,
    *,
    file_paths: list[str] | None = None,
) -> ProjectMetrics:
    """Compute aggregated quality metrics across a project."""
    from semantic_code_intelligence.parsing.parser import EXTENSION_TO_LANGUAGE

    root = project_root.resolve()

    if file_paths:
        files = [str(Path(f).resolve()) for f in file_paths]
    else:
        files = []
        for f in root.rglob("*"):
            if f.is_file() and f.suffix in EXTENSION_TO_LANGUAGE:
                parts = f.relative_to(root).parts
                if any(
                    p.startswith(".") or p in ("__pycache__", "node_modules", ".codexa")
                    for p in parts
                ):
                    continue
                files.append(str(f))

    file_metrics: list[FileMetrics] = []
    for fpath in files:
        try:
            fm = compute_file_metrics(fpath)
            file_metrics.append(fm)
        except Exception as exc:
            logger.debug("Skipping %s: %s", fpath, exc)

    total_loc = sum(f.lines_of_code for f in file_metrics)
    total_cm = sum(f.comment_lines for f in file_metrics)
    total_bl = sum(f.blank_lines for f in file_metrics)
    total_symbols = sum(f.symbol_count for f in file_metrics)

    if file_metrics:
        avg_cc = sum(f.avg_complexity for f in file_metrics) / len(file_metrics)
    else:
        avg_cc = 0.0
    max_cc = max((f.max_complexity for f in file_metrics), default=0)

    total = total_loc + total_cm + total_bl
    cr = total_cm / total if total > 0 else 0.0
    mi = _compute_mi(float(total_loc) / max(len(file_metrics), 1), avg_cc, cr)

    return ProjectMetrics(
        files_analyzed=len(file_metrics),
        total_loc=total_loc,
        total_comment_lines=total_cm,
        total_blank_lines=total_bl,
        avg_complexity=avg_cc,
        max_complexity=max_cc,
        total_symbols=total_symbols,
        maintainability_index=mi,
        file_metrics=file_metrics,
    )


# ── Metric snapshots & trend tracking ────────────────────────────────

_SNAPSHOT_PREFIX = "quality:snapshot:"


@dataclass
class QualitySnapshot:
    """Timestamped capture of quality metrics."""

    timestamp: float
    maintainability_index: float
    total_loc: int
    total_symbols: int
    issue_count: int
    files_analyzed: int
    avg_complexity: float
    comment_ratio: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialise the snapshot to a plain dictionary."""
        return {
            "timestamp": self.timestamp,
            "maintainability_index": round(self.maintainability_index, 1),
            "total_loc": self.total_loc,
            "total_symbols": self.total_symbols,
            "issue_count": self.issue_count,
            "files_analyzed": self.files_analyzed,
            "avg_complexity": round(self.avg_complexity, 2),
            "comment_ratio": round(self.comment_ratio, 3),
            "metadata": self.metadata,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> QualitySnapshot:
        """Construct a :class:`QualitySnapshot` from a dictionary."""
        return QualitySnapshot(
            timestamp=data["timestamp"],
            maintainability_index=data["maintainability_index"],
            total_loc=data["total_loc"],
            total_symbols=data["total_symbols"],
            issue_count=data["issue_count"],
            files_analyzed=data["files_analyzed"],
            avg_complexity=data.get("avg_complexity", 0.0),
            comment_ratio=data.get("comment_ratio", 0.0),
            metadata=data.get("metadata", {}),
        )


def save_snapshot(
    project_root: Path,
    project_metrics: ProjectMetrics,
    quality_report: QualityReport,
    *,
    metadata: dict[str, Any] | None = None,
) -> QualitySnapshot:
    """Persist a quality snapshot via WorkspaceMemory."""
    ts = time.time()
    snapshot = QualitySnapshot(
        timestamp=ts,
        maintainability_index=project_metrics.maintainability_index,
        total_loc=project_metrics.total_loc,
        total_symbols=project_metrics.total_symbols,
        issue_count=quality_report.issue_count,
        files_analyzed=project_metrics.files_analyzed,
        avg_complexity=project_metrics.avg_complexity,
        comment_ratio=project_metrics.comment_ratio,
        metadata=metadata or {},
    )

    mem = WorkspaceMemory(project_root)
    key = f"{_SNAPSHOT_PREFIX}{ts:.6f}"
    mem.add(key, json.dumps(snapshot.to_dict()), kind="metrics")
    return snapshot


def load_snapshots(
    project_root: Path,
    *,
    limit: int = 50,
) -> list[QualitySnapshot]:
    """Retrieve recent quality snapshots from WorkspaceMemory, newest first."""
    mem = WorkspaceMemory(project_root)
    entries = mem.search(_SNAPSHOT_PREFIX, limit=limit * 3)

    snapshots: list[QualitySnapshot] = []
    for entry in entries:
        if not entry.key.startswith(_SNAPSHOT_PREFIX):
            continue
        try:
            data = json.loads(entry.content)
            snapshots.append(QualitySnapshot.from_dict(data))
        except Exception:
            logger.debug("Skipping corrupt snapshot: %s", entry.key)
            continue

    snapshots.sort(key=lambda s: s.timestamp, reverse=True)
    return snapshots[:limit]


# ── Trend analysis ───────────────────────────────────────────────────

@dataclass
class TrendResult:
    """Result of trend analysis over metric snapshots."""

    metric_name: str
    snapshot_count: int
    oldest_value: float
    newest_value: float
    delta: float
    slope: float  # per-second rate
    direction: str  # "improving", "stable", "degrading"

    def to_dict(self) -> dict[str, Any]:
        """Serialise trend analysis to a plain dictionary."""
        return {
            "metric_name": self.metric_name,
            "snapshot_count": self.snapshot_count,
            "oldest_value": round(self.oldest_value, 2),
            "newest_value": round(self.newest_value, 2),
            "delta": round(self.delta, 2),
            "slope": self.slope,
            "direction": self.direction,
        }


def _linear_slope(xs: list[float], ys: list[float]) -> float:
    """Simple linear regression slope (least squares)."""
    n = len(xs)
    if n < 2:
        return 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(xs, ys))
    den = sum((xi - mean_x) ** 2 for xi in xs)
    if den == 0:
        return 0.0
    return num / den


def compute_trend(
    snapshots: list[QualitySnapshot],
    metric: str = "maintainability_index",
    *,
    higher_is_better: bool = True,
    threshold: float = 0.01,
) -> TrendResult:
    """Compute trend for a given metric over sorted (newest-first) snapshots.

    Args:
        snapshots: Newest-first list of snapshots.
        metric: Attribute name on QualitySnapshot to track.
        higher_is_better: If True, positive slope means improving.
        threshold: Fractional change below which trend is "stable".
    """
    if not snapshots:
        return TrendResult(
            metric_name=metric,
            snapshot_count=0,
            oldest_value=0.0,
            newest_value=0.0,
            delta=0.0,
            slope=0.0,
            direction="stable",
        )

    # Snapshots are newest-first; reverse for chronological order
    ordered = list(reversed(snapshots))
    ts_list = [s.timestamp for s in ordered]
    vals = [float(getattr(s, metric, 0)) for s in ordered]

    slope = _linear_slope(ts_list, vals)

    oldest = vals[0]
    newest = vals[-1]
    delta = newest - oldest

    # Determine direction
    if len(snapshots) < 2:
        direction = "stable"
    else:
        frac = abs(delta) / max(abs(oldest), 1e-9)
        if frac < threshold:
            direction = "stable"
        elif (delta > 0) == higher_is_better:
            direction = "improving"
        else:
            direction = "degrading"

    return TrendResult(
        metric_name=metric,
        snapshot_count=len(snapshots),
        oldest_value=oldest,
        newest_value=newest,
        delta=delta,
        slope=slope,
        direction=direction,
    )


# ── Quality policies & gates ─────────────────────────────────────────

@dataclass
class QualityPolicy:
    """Configurable quality thresholds for gate enforcement."""

    min_maintainability: float = 40.0
    max_complexity: int = 25
    max_issues: int = 20
    max_dead_code: int = 15
    max_duplicates: int = 10
    require_safety_pass: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Serialise the quality policy to a plain dictionary."""
        return asdict(self)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> QualityPolicy:
        """Construct a :class:`QualityPolicy` from a dictionary."""
        return QualityPolicy(
            min_maintainability=data.get("min_maintainability", 40.0),
            max_complexity=data.get("max_complexity", 25),
            max_issues=data.get("max_issues", 20),
            max_dead_code=data.get("max_dead_code", 15),
            max_duplicates=data.get("max_duplicates", 10),
            require_safety_pass=data.get("require_safety_pass", True),
        )


@dataclass
class GateViolation:
    """A single quality gate violation."""

    rule: str
    message: str
    actual: float | int
    threshold: float | int

    def to_dict(self) -> dict[str, Any]:
        """Serialise the gate violation to a plain dictionary."""
        return asdict(self)


@dataclass
class GateResult:
    """Result of quality gate enforcement."""

    passed: bool
    violations: list[GateViolation] = field(default_factory=list)
    policy: QualityPolicy = field(default_factory=QualityPolicy)

    def to_dict(self) -> dict[str, Any]:
        """Serialise the gate result to a plain dictionary."""
        return {
            "passed": self.passed,
            "violations": [v.to_dict() for v in self.violations],
            "policy": self.policy.to_dict(),
        }


def enforce_quality_gate(
    project_metrics: ProjectMetrics,
    quality_report: QualityReport,
    policy: QualityPolicy | None = None,
) -> GateResult:
    """Evaluate quality metrics against policy thresholds.

    Returns a GateResult indicating pass/fail with violation details.
    """
    pol = policy or QualityPolicy()
    violations: list[GateViolation] = []

    # Maintainability
    if project_metrics.maintainability_index < pol.min_maintainability:
        violations.append(GateViolation(
            rule="min_maintainability",
            message=f"Maintainability index {project_metrics.maintainability_index:.1f} < {pol.min_maintainability}",
            actual=project_metrics.maintainability_index,
            threshold=pol.min_maintainability,
        ))

    # Max complexity
    if project_metrics.max_complexity > pol.max_complexity:
        violations.append(GateViolation(
            rule="max_complexity",
            message=f"Max complexity {project_metrics.max_complexity} > {pol.max_complexity}",
            actual=project_metrics.max_complexity,
            threshold=pol.max_complexity,
        ))

    # Total issues
    if quality_report.issue_count > pol.max_issues:
        violations.append(GateViolation(
            rule="max_issues",
            message=f"Issue count {quality_report.issue_count} > {pol.max_issues}",
            actual=quality_report.issue_count,
            threshold=pol.max_issues,
        ))

    # Dead code
    if len(quality_report.dead_code) > pol.max_dead_code:
        violations.append(GateViolation(
            rule="max_dead_code",
            message=f"Dead code count {len(quality_report.dead_code)} > {pol.max_dead_code}",
            actual=len(quality_report.dead_code),
            threshold=pol.max_dead_code,
        ))

    # Duplicates
    if len(quality_report.duplicates) > pol.max_duplicates:
        violations.append(GateViolation(
            rule="max_duplicates",
            message=f"Duplicate count {len(quality_report.duplicates)} > {pol.max_duplicates}",
            actual=len(quality_report.duplicates),
            threshold=pol.max_duplicates,
        ))

    # Safety
    if pol.require_safety_pass and quality_report.safety and not quality_report.safety.safe:
        violations.append(GateViolation(
            rule="require_safety_pass",
            message=f"Safety check failed with {len(quality_report.safety.issues)} issue(s)",
            actual=len(quality_report.safety.issues),
            threshold=0,
        ))

    return GateResult(
        passed=len(violations) == 0,
        violations=violations,
        policy=pol,
    )
