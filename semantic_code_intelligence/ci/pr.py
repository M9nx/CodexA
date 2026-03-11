"""Pull Request intelligence — change summary, impact analysis, risk scoring.

All functions take plain data (file lists, symbol dicts) and produce
structured dict results suitable for JSON serialization or Rich rendering.
No git binary is invoked; the caller supplies file lists.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from semantic_code_intelligence.parsing.parser import Symbol, parse_file, detect_language
from semantic_code_intelligence.context.engine import CallGraph, ContextBuilder, DependencyMap
from semantic_code_intelligence.llm.safety import SafetyReport, SafetyValidator
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("ci.pr")


# ── Change summary ───────────────────────────────────────────────────

@dataclass
class FileChange:
    """Metadata for a single changed file."""

    path: str
    language: str | None = None
    symbols_added: list[str] = field(default_factory=list)
    symbols_removed: list[str] = field(default_factory=list)
    symbols_modified: list[str] = field(default_factory=list)
    import_changes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ChangeSummary:
    """Structured summary of a set of file changes."""

    files_changed: int = 0
    languages: list[str] = field(default_factory=list)
    total_symbols_added: int = 0
    total_symbols_removed: int = 0
    total_symbols_modified: int = 0
    file_details: list[FileChange] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "files_changed": self.files_changed,
            "languages": self.languages,
            "total_symbols_added": self.total_symbols_added,
            "total_symbols_removed": self.total_symbols_removed,
            "total_symbols_modified": self.total_symbols_modified,
            "file_details": [f.to_dict() for f in self.file_details],
        }


def _sym_set(symbols: list[Symbol], kind: str | None = None) -> dict[str, Symbol]:
    """Map name → Symbol, optionally filtering by kind."""
    out: dict[str, Symbol] = {}
    for s in symbols:
        if kind and s.kind != kind:
            continue
        key = f"{s.name}:{s.start_line}" if s.kind != "import" else s.name
        out[key] = s
    return out


def build_change_summary(
    changed_files: list[str],
    *,
    base_root: Path | None = None,
) -> ChangeSummary:
    """Build a structured change summary for a list of modified files.

    For each file, parses current symbols.  If *base_root* is supplied it
    attempts to diff against the base version, but works fine without it
    (reports all current symbols as "added").
    """
    summary = ChangeSummary(files_changed=len(changed_files))
    langs: set[str] = set()

    for fpath in changed_files:
        lang = detect_language(fpath)
        if lang:
            langs.add(lang)

        fc = FileChange(path=fpath, language=lang)

        if not lang:
            summary.file_details.append(fc)
            continue

        try:
            current_syms = parse_file(fpath)
        except Exception:
            summary.file_details.append(fc)
            continue

        # Attempt base comparison
        base_syms: list[Symbol] = []
        if base_root:
            base_file = base_root / fpath
            if base_file.exists():
                try:
                    base_syms = parse_file(str(base_file))
                except Exception as exc:
                    logger.debug("Could not parse base file %s: %s", base_file, exc)

        cur_names = {s.name for s in current_syms if s.kind != "import"}
        base_names = {s.name for s in base_syms if s.kind != "import"}

        fc.symbols_added = sorted(cur_names - base_names)
        fc.symbols_removed = sorted(base_names - cur_names)

        # Detect "modified" — same name but different body
        cur_by_name = {s.name: s for s in current_syms if s.kind != "import"}
        base_by_name = {s.name: s for s in base_syms if s.kind != "import"}
        for name in cur_names & base_names:
            if cur_by_name[name].body != base_by_name.get(name, cur_by_name[name]).body:
                fc.symbols_modified.append(name)
        fc.symbols_modified.sort()

        # Import diff
        cur_imports = {s.name for s in current_syms if s.kind == "import"}
        base_imports = {s.name for s in base_syms if s.kind == "import"}
        added_imports = cur_imports - base_imports
        removed_imports = base_imports - cur_imports
        fc.import_changes = sorted(f"+{i}" for i in added_imports) + sorted(f"-{i}" for i in removed_imports)

        summary.total_symbols_added += len(fc.symbols_added)
        summary.total_symbols_removed += len(fc.symbols_removed)
        summary.total_symbols_modified += len(fc.symbols_modified)
        summary.file_details.append(fc)

    summary.languages = sorted(langs)
    return summary


# ── Semantic impact analysis ─────────────────────────────────────────

@dataclass
class ImpactResult:
    """Impact analysis for a set of changed symbols."""

    changed_symbols: list[str] = field(default_factory=list)
    affected_files: list[str] = field(default_factory=list)
    affected_symbols: list[str] = field(default_factory=list)
    dependency_changes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def analyze_impact(
    changed_files: list[str],
    project_root: Path,
) -> ImpactResult:
    """Determine which symbols and files are affected by changes.

    Indexes the project, builds a call graph, then traces callers of
    any modified symbol to find the blast radius.
    """
    builder = ContextBuilder()
    dep_map = DependencyMap()

    # Index changed files
    changed_syms: set[str] = set()
    for fpath in changed_files:
        try:
            syms = builder.index_file(fpath)
            dep_map.add_file(fpath)
            for s in syms:
                if s.kind != "import":
                    changed_syms.add(s.name)
        except Exception as exc:
            logger.debug("Could not index %s for impact: %s", fpath, exc)

    # Build call graph from all indexed symbols
    all_syms = builder.get_all_symbols()
    cg = CallGraph()
    cg.build(all_syms)

    affected_syms: set[str] = set()
    affected_files: set[str] = set()

    for name in changed_syms:
        for edge in cg.callers_of(name):
            caller = edge.caller
            if ":" in caller:
                caller = caller.rsplit(":", 1)[-1]
            affected_syms.add(caller)
            affected_files.add(edge.file_path)

    # Dependency-level impact: who imports these files?
    dep_changes: list[str] = []
    changed_set = {str(Path(f).resolve()) for f in changed_files}
    for f in dep_map.get_all_files():
        for dep in dep_map.get_dependencies(f):
            if any(dep.import_text in str(cf) for cf in changed_set):
                dep_changes.append(f"{f} imports {dep.import_text}")

    return ImpactResult(
        changed_symbols=sorted(changed_syms),
        affected_files=sorted(affected_files),
        affected_symbols=sorted(affected_syms),
        dependency_changes=dep_changes,
    )


# ── Suggested reviewers ──────────────────────────────────────────────

def suggest_reviewers(
    changed_files: list[str],
    *,
    all_files: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Suggest reviewers based on file domain expertise.

    Returns a list of domain areas with associated file patterns so a team
    can assign reviewers by area.  This is a heuristic, not git-blame based.
    """
    domains: dict[str, list[str]] = {}

    for fpath in changed_files:
        parts = Path(fpath).parts
        # Use first two meaningful directories as domain
        meaningful = [p for p in parts if not p.startswith(".") and p not in ("src", "lib")]
        domain = "/".join(meaningful[:2]) if len(meaningful) >= 2 else (meaningful[0] if meaningful else "root")
        domains.setdefault(domain, []).append(fpath)

    return [
        {"domain": domain, "files": files, "file_count": len(files)}
        for domain, files in sorted(domains.items(), key=lambda x: -len(x[1]))
    ]


# ── Risk severity scoring ────────────────────────────────────────────

@dataclass
class RiskScore:
    """Aggregate risk assessment for a changeset."""

    score: int  # 0-100
    level: str  # "low", "medium", "high", "critical"
    factors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _risk_level(score: int) -> str:
    if score < 25:
        return "low"
    if score < 50:
        return "medium"
    if score < 75:
        return "high"
    return "critical"


def compute_risk(
    change_summary: ChangeSummary,
    *,
    safety_report: SafetyReport | None = None,
    impact: ImpactResult | None = None,
) -> RiskScore:
    """Compute a risk severity score (0-100) for a changeset.

    Factors considered:
    - Number of files changed
    - Symbol additions/removals
    - Safety issues
    - Blast radius (affected symbols)
    """
    score = 0
    factors: list[str] = []

    # File count factor
    n_files = change_summary.files_changed
    if n_files > 20:
        score += 20
        factors.append(f"Large changeset: {n_files} files")
    elif n_files > 10:
        score += 10
        factors.append(f"Medium changeset: {n_files} files")
    elif n_files > 0:
        score += 5

    # Symbol removals are riskier than additions
    n_removed = change_summary.total_symbols_removed
    if n_removed > 10:
        score += 20
        factors.append(f"{n_removed} symbols removed")
    elif n_removed > 0:
        score += 10
        factors.append(f"{n_removed} symbols removed")

    n_modified = change_summary.total_symbols_modified
    if n_modified > 10:
        score += 15
        factors.append(f"{n_modified} symbols modified")
    elif n_modified > 0:
        score += 5

    # Safety issues
    if safety_report and not safety_report.safe:
        n_issues = len(safety_report.issues)
        score += min(30, n_issues * 10)
        factors.append(f"{n_issues} safety issue(s)")

    # Blast radius
    if impact:
        n_affected = len(impact.affected_symbols)
        if n_affected > 20:
            score += 15
            factors.append(f"Wide blast radius: {n_affected} affected symbols")
        elif n_affected > 5:
            score += 10
            factors.append(f"{n_affected} affected symbols")

    score = min(100, score)
    return RiskScore(score=score, level=_risk_level(score), factors=factors)


# ── Full PR report ───────────────────────────────────────────────────

@dataclass
class PRReport:
    """Complete PR intelligence report."""

    change_summary: ChangeSummary
    impact: ImpactResult | None = None
    reviewers: list[dict[str, Any]] = field(default_factory=list)
    risk: RiskScore | None = None
    safety: SafetyReport | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "change_summary": self.change_summary.to_dict(),
            "impact": self.impact.to_dict() if self.impact else None,
            "reviewers": self.reviewers,
            "risk": self.risk.to_dict() if self.risk else None,
            "safety": self.safety.to_dict() if self.safety else None,
        }


def generate_pr_report(
    changed_files: list[str],
    project_root: Path,
    *,
    run_impact: bool = True,
    run_safety: bool = True,
) -> PRReport:
    """Generate a full PR intelligence report.

    Args:
        changed_files: Paths of files in the changeset.
        project_root: Repository root directory.
        run_impact: Whether to run impact analysis (requires indexing).
        run_safety: Whether to run safety validation.
    """
    summary = build_change_summary(changed_files)

    impact = None
    if run_impact:
        try:
            impact = analyze_impact(changed_files, project_root)
        except Exception as exc:
            logger.debug("Impact analysis skipped: %s", exc)

    safety = None
    if run_safety:
        validator = SafetyValidator()
        code = ""
        for fpath in changed_files:
            try:
                code += Path(fpath).read_text(encoding="utf-8", errors="replace") + "\n"
            except Exception as exc:
                logger.debug("Could not read %s for safety check: %s", fpath, exc)
        safety = validator.validate(code)

    reviewers = suggest_reviewers(changed_files)
    risk = compute_risk(summary, safety_report=safety, impact=impact)

    return PRReport(
        change_summary=summary,
        impact=impact,
        reviewers=reviewers,
        risk=risk,
        safety=safety,
    )
