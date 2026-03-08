"""Context memory — workspace memory, session context, and multi-step reasoning.

Provides persistent and session-scoped memory so that the AI assistant can:
- Remember previous interactions within a session
- Cache insights across sessions (workspace memory)
- Maintain multi-step reasoning chains
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("context.memory")


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class MemoryEntry:
    """A single memory entry (question/answer, insight, or reasoning step)."""

    key: str
    content: str
    kind: str = "general"  # general | qa | reasoning | insight
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the memory entry to a plain dictionary."""
        return {
            "key": self.key,
            "content": self.content,
            "kind": self.kind,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryEntry":
        """Create a MemoryEntry from a dictionary."""
        return cls(
            key=data["key"],
            content=data["content"],
            kind=data.get("kind", "general"),
            timestamp=data.get("timestamp", time.time()),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ReasoningStep:
    """A single step in a multi-step reasoning chain."""

    step_id: int
    action: str  # e.g. "search", "analyze", "ask_llm", "conclude"
    input_text: str
    output_text: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the reasoning step to a plain dictionary."""
        return {
            "step_id": self.step_id,
            "action": self.action,
            "input": self.input_text,
            "output": self.output_text,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Session Memory (in-process, per-session)
# ---------------------------------------------------------------------------

class SessionMemory:
    """In-process memory for the current session / conversation."""

    def __init__(self, max_entries: int = 200) -> None:
        self._entries: list[MemoryEntry] = []
        self._reasoning_chains: dict[str, list[ReasoningStep]] = {}
        self._max = max_entries

    @property
    def entries(self) -> list[MemoryEntry]:
        """Return a shallow copy of all session memory entries."""
        return list(self._entries)

    def add(self, key: str, content: str, kind: str = "general", **metadata: Any) -> MemoryEntry:
        """Add a memory entry to the session."""
        entry = MemoryEntry(key=key, content=content, kind=kind, metadata=metadata)
        self._entries.append(entry)
        if len(self._entries) > self._max:
            self._entries.pop(0)
        return entry

    def search(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        """Simple keyword search over session memory."""
        query_lower = query.lower()
        scored = []
        for entry in self._entries:
            text = f"{entry.key} {entry.content}".lower()
            if query_lower in text:
                scored.append(entry)
        return scored[-limit:]

    def get_recent(self, limit: int = 10) -> list[MemoryEntry]:
        """Return the most recent entries."""
        return self._entries[-limit:]

    def clear(self) -> None:
        """Clear all session memory."""
        self._entries.clear()
        self._reasoning_chains.clear()

    # --- Reasoning chains ---

    def start_chain(self, chain_id: str) -> None:
        """Start a new reasoning chain."""
        self._reasoning_chains[chain_id] = []

    def add_step(
        self,
        chain_id: str,
        action: str,
        input_text: str,
        output_text: str,
    ) -> ReasoningStep:
        """Add a step to an existing reasoning chain."""
        chain = self._reasoning_chains.setdefault(chain_id, [])
        step = ReasoningStep(
            step_id=len(chain) + 1,
            action=action,
            input_text=input_text,
            output_text=output_text,
        )
        chain.append(step)
        return step

    def get_chain(self, chain_id: str) -> list[ReasoningStep]:
        """Retrieve all steps in a reasoning chain."""
        return list(self._reasoning_chains.get(chain_id, []))

    def to_dict(self) -> dict[str, Any]:
        """Serialize all session memory and reasoning chains to a dictionary."""
        return {
            "entries": [e.to_dict() for e in self._entries],
            "chains": {
                cid: [s.to_dict() for s in steps]
                for cid, steps in self._reasoning_chains.items()
            },
        }


# ---------------------------------------------------------------------------
# Workspace Memory (persistent, stored in .codex/)
# ---------------------------------------------------------------------------

MEMORY_FILE = "memory.json"


class WorkspaceMemory:
    """Persistent memory stored in the project's .codex/ directory.

    Survives across sessions. Cached insights, frequently-asked questions,
    and project-specific knowledge live here.
    """

    def __init__(self, project_root: Path) -> None:
        from semantic_code_intelligence.config.settings import AppConfig

        self._config_dir = AppConfig.config_dir(project_root)
        self._path = self._config_dir / MEMORY_FILE
        self._entries: dict[str, MemoryEntry] = {}
        self._load()

    def _load(self) -> None:
        """Load memory from disk."""
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                for entry_data in data.get("entries", []):
                    entry = MemoryEntry.from_dict(entry_data)
                    self._entries[entry.key] = entry
                logger.debug("Loaded %d workspace memory entries", len(self._entries))
            except (json.JSONDecodeError, KeyError, TypeError):
                logger.warning("Corrupt workspace memory file; starting fresh.")
                self._entries = {}

    def _save(self) -> None:
        """Persist memory to disk."""
        self._config_dir.mkdir(parents=True, exist_ok=True)
        data = {"entries": [e.to_dict() for e in self._entries.values()]}
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @property
    def entries(self) -> list[MemoryEntry]:
        """Return a list of all persisted workspace memory entries."""
        return list(self._entries.values())

    def add(self, key: str, content: str, kind: str = "general", **metadata: Any) -> MemoryEntry:
        """Add or update a memory entry."""
        entry = MemoryEntry(key=key, content=content, kind=kind, metadata=metadata)
        self._entries[key] = entry
        self._save()
        return entry

    def get(self, key: str) -> MemoryEntry | None:
        """Retrieve a specific memory entry by key."""
        return self._entries.get(key)

    def search(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        """Simple keyword search over workspace memory."""
        query_lower = query.lower()
        results = []
        for entry in self._entries.values():
            text = f"{entry.key} {entry.content}".lower()
            if query_lower in text:
                results.append(entry)
        return results[:limit]

    def remove(self, key: str) -> bool:
        """Remove a memory entry."""
        if key in self._entries:
            del self._entries[key]
            self._save()
            return True
        return False

    def clear(self) -> None:
        """Clear all workspace memory."""
        self._entries.clear()
        self._save()

    def to_dict(self) -> dict[str, Any]:
        """Serialize all workspace memory entries to a dictionary."""
        return {"entries": [e.to_dict() for e in self._entries.values()]}
