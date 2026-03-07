"""Analysis package — AI features, repository summaries, code explanations."""

from semantic_code_intelligence.analysis.ai_features import (
    CodeExplanation,
    LanguageStats,
    RepoSummary,
    explain_file,
    explain_symbol,
    generate_ai_context,
    summarize_repository,
)

__all__ = [
    "CodeExplanation",
    "LanguageStats",
    "RepoSummary",
    "explain_file",
    "explain_symbol",
    "generate_ai_context",
    "summarize_repository",
]
