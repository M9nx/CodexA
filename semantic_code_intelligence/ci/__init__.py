"""CI/CD integration and contribution safety pipeline.

Submodules
----------
- ``quality``: Code quality analyzers (dead code, duplicates, complexity, security).
- ``metrics``: Maintainability index, metric snapshots, trend tracking, quality gates.
- ``pr``: Pull request intelligence (change summary, impact, risk scoring).
- ``hooks``: Pre-commit validation hook support.
- ``templates``: GitHub Actions workflow template generation.
- ``hotspots``: Hotspot detection engine (complexity, duplication, fan-in/out, churn).
- ``impact``: Impact analysis engine (blast radius prediction via call graph / deps).
- ``trace``: Symbol trace tool (upstream callers, downstream callees, cross-file paths).
"""
