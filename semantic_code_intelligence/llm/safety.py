"""Safety validator — checks LLM outputs before they are applied.

Provides basic guardrails to ensure LLM-generated code does not contain
obviously dangerous patterns. This is not a comprehensive security tool;
it is a first line of defence within the coding assistant workflow.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("llm.safety")

# Patterns that should never appear in AI-generated code destined for execution.
_DANGEROUS_PATTERNS: list[tuple[str, str]] = [
    # Command execution
    (r"\bos\.system\s*\(", "os.system() call — use subprocess with shell=False instead"),
    (r"subprocess\..*shell\s*=\s*True", "subprocess with shell=True — potential command injection"),
    (r"\brm\s+-rf\s+/", "Destructive rm -rf / command"),
    # Dynamic code execution
    (r"\beval\s*\(", "eval() call — avoid dynamic code execution"),
    # Negative lookbehinds exclude OOP/PHP method calls (e.g. $pdo->exec(),
    # PDO::exec()).  Whitespace normalisation in SafetyValidator.validate()
    # ensures spaced forms ($pdo -> exec(), SomeClass :: exec()) are also
    # excluded before these patterns are applied.
    (r"(?<!->)(?<!::)\bexec\s*\(", "exec() call — avoid dynamic code execution"),
    (r"\b__import__\s*\(", "Dynamic __import__() — use explicit imports"),
    # SQL injection risk
    (r"DROP\s+TABLE|DROP\s+DATABASE", "SQL DROP statement — potential data loss"),
    (r"TRUNCATE\s+TABLE", "SQL TRUNCATE statement — potential data loss"),
    # Path traversal
    (r"\.\./\.\./", "Path traversal pattern — potential directory escape"),
    # Hardcoded secrets (Phase 12)
    (r"""(?:password|secret|api_key|token)\s*=\s*["'][^"']{8,}["']""",
     "Hardcoded secret — use environment variables or a secrets manager"),
    # XSS risk (Phase 12)
    (r"innerHTML\s*=", "innerHTML assignment — potential XSS vulnerability"),
    (r"document\.write\s*\(", "document.write() — potential XSS vulnerability"),
    # Insecure crypto (Phase 12)
    (r"\bMD5\s*\(|\bmd5\s*\(", "MD5 hash — use SHA-256 or stronger for security"),
    (r"\bSHA1\s*\(|\bsha1\s*\(", "SHA-1 hash — use SHA-256 or stronger for security"),
    # Insecure network (Phase 12)
    (r"http://(?!localhost|127\.0\.0\.1)", "Insecure HTTP URL — use HTTPS instead"),
    (r"verify\s*=\s*False", "SSL verification disabled — potential MITM vulnerability"),
]


@dataclass
class SafetyIssue:
    """A single safety issue found in LLM output."""

    pattern: str
    description: str
    line_number: int = 0
    severity: str = "warning"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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


# Regex used to collapse optional whitespace around PHP/OOP method-call
# operators before safety patterns are applied.  This ensures that both the
# compact form  ($pdo->exec())  and the spaced form  ($pdo -> exec())  are
# normalised to the same token sequence, allowing the fixed-width
# lookbehinds in _DANGEROUS_PATTERNS to work correctly in all cases.
_PHP_OPERATOR_WS = re.compile(r"\s*(->|::)\s*")


class SafetyValidator:
    """Validates LLM-generated code for known dangerous patterns."""

    def __init__(self, extra_patterns: list[tuple[str, str]] | None = None) -> None:
        self._patterns = list(_DANGEROUS_PATTERNS)
        if extra_patterns:
            self._patterns.extend(extra_patterns)

    def validate(self, code: str) -> SafetyReport:
        """Scan ``code`` for dangerous patterns.

        Returns a SafetyReport. If any issues are found, ``safe`` is False.

        Each source line is normalised before matching: whitespace surrounding
        OOP/PHP method-call operators (``->`` and ``::``) is collapsed so that
        both compact forms (``$pdo->exec()``) and spaced forms
        (``$pdo -> exec()``) are treated identically by the lookbehind
        assertions in the pattern list.
        """
        issues: list[SafetyIssue] = []
        for line_no, line in enumerate(code.splitlines(), start=1):
            # Normalise  "-> "  and  ":: "  (with any surrounding whitespace)
            # to the compact forms  "->"  and  "::"  so that the fixed-width
            # negative lookbehinds  (?<!->)  and  (?<!::)  fire correctly even
            # when the source code uses spaces around these operators.
            normalised = _PHP_OPERATOR_WS.sub(r"\1", line)
            for pattern, description in self._patterns:
                if re.search(pattern, normalised, re.IGNORECASE):
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
