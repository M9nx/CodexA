"""Safety validator — checks LLM outputs before they are applied.

Provides basic guardrails to ensure LLM-generated code does not contain
obviously dangerous patterns. This is not a comprehensive security tool;
it is a first line of defence within the coding assistant workflow.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("llm.safety")

# Patterns that should never appear in AI-generated code destined for execution.
_DANGEROUS_PATTERNS: list[tuple[str, str]] = [
    (r"\bos\.system\s*\(", "os.system() call — use subprocess with shell=False instead"),
    (r"\beval\s*\(", "eval() call — avoid dynamic code execution"),
    (r"\bexec\s*\(", "exec() call — avoid dynamic code execution"),
    (r"\b__import__\s*\(", "Dynamic __import__() — use explicit imports"),
    (r"subprocess\..*shell\s*=\s*True", "subprocess with shell=True — potential command injection"),
    (r"\brm\s+-rf\s+/", "Destructive rm -rf / command"),
    (r"DROP\s+TABLE|DROP\s+DATABASE", "SQL DROP statement — potential data loss"),
    (r"TRUNCATE\s+TABLE", "SQL TRUNCATE statement — potential data loss"),
]


@dataclass
class SafetyIssue:
    """A single safety issue found in LLM output."""

    pattern: str
    description: str
    line_number: int = 0
    severity: str = "warning"

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern": self.pattern,
            "description": self.description,
            "line_number": self.line_number,
            "severity": self.severity,
        }


@dataclass
class SafetyReport:
    """Result of a safety validation pass."""

    safe: bool = True
    issues: list[SafetyIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "safe": self.safe,
            "issue_count": len(self.issues),
            "issues": [i.to_dict() for i in self.issues],
        }


class SafetyValidator:
    """Validates LLM-generated code for known dangerous patterns."""

    def __init__(self, extra_patterns: list[tuple[str, str]] | None = None) -> None:
        self._patterns = list(_DANGEROUS_PATTERNS)
        if extra_patterns:
            self._patterns.extend(extra_patterns)

    def validate(self, code: str) -> SafetyReport:
        """Scan ``code`` for dangerous patterns.

        Returns a SafetyReport. If any issues are found, ``safe`` is False.
        """
        issues: list[SafetyIssue] = []
        for line_no, line in enumerate(code.splitlines(), start=1):
            for pattern, description in self._patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append(
                        SafetyIssue(
                            pattern=pattern,
                            description=description,
                            line_number=line_no,
                        )
                    )

        return SafetyReport(safe=len(issues) == 0, issues=issues)

    def is_safe(self, code: str) -> bool:
        """Quick boolean check — True if no safety issues found."""
        return self.validate(code).safe
