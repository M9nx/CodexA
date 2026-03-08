"""Conversation memory — persistent multi-turn chat sessions.

Provides:
- **ConversationSession**: an ordered list of LLMMessage turns with metadata,
  serialisable to / from disk.
- **SessionStore**: manages multiple named sessions under ``.codex/sessions/``
  with create, resume, list, and delete operations.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from semantic_code_intelligence.llm.provider import LLMMessage, MessageRole
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("llm.conversation")


# ---------------------------------------------------------------------------
# Conversation session
# ---------------------------------------------------------------------------

@dataclass
class ConversationSession:
    """A multi-turn conversation with an LLM."""

    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str = ""
    messages: list[LLMMessage] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    # --- turn management ---

    def add_message(self, role: MessageRole, content: str) -> LLMMessage:
        """Append a message to the conversation."""
        msg = LLMMessage(role=role, content=content)
        self.messages.append(msg)
        self.updated_at = time.time()
        return msg

    def add_user(self, content: str) -> LLMMessage:
        """Append a user message to the session."""
        return self.add_message(MessageRole.USER, content)

    def add_assistant(self, content: str) -> LLMMessage:
        """Append an assistant message to the session."""
        return self.add_message(MessageRole.ASSISTANT, content)

    def add_system(self, content: str) -> LLMMessage:
        """Append a system message to the session."""
        return self.add_message(MessageRole.SYSTEM, content)

    @property
    def turn_count(self) -> int:
        """Number of user+assistant exchanges."""
        return sum(1 for m in self.messages if m.role in (MessageRole.USER, MessageRole.ASSISTANT))

    @property
    def last_message(self) -> LLMMessage | None:
        """Return the most recent message, or None if empty."""
        return self.messages[-1] if self.messages else None

    def get_messages_for_llm(self, max_turns: int | None = None) -> list[LLMMessage]:
        """Return messages formatted for LLM consumption.

        Always includes system messages.  When *max_turns* is specified, keeps
        the most recent user/assistant pairs to stay within context budget.
        """
        system_msgs = [m for m in self.messages if m.role == MessageRole.SYSTEM]
        conversation = [m for m in self.messages if m.role != MessageRole.SYSTEM]

        if max_turns is not None and len(conversation) > max_turns * 2:
            conversation = conversation[-(max_turns * 2):]

        return system_msgs + conversation

    # --- serialisation ---

    def to_dict(self) -> dict[str, Any]:
        """Serialize the conversation session to a plain dictionary."""
        return {
            "session_id": self.session_id,
            "title": self.title,
            "messages": [{"role": m.role.value, "content": m.content} for m in self.messages],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConversationSession:
        """Reconstruct a conversation session from a dictionary."""
        messages = [
            LLMMessage(role=MessageRole(m["role"]), content=m["content"])
            for m in data.get("messages", [])
        ]
        return cls(
            session_id=data["session_id"],
            title=data.get("title", ""),
            messages=messages,
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            metadata=data.get("metadata", {}),
        )


# ---------------------------------------------------------------------------
# Session store (persistent, file-backed)
# ---------------------------------------------------------------------------

SESSIONS_DIR = "sessions"


class SessionStore:
    """File-backed store for conversation sessions.

    Sessions live under ``<project_root>/.codex/sessions/<id>.json``.
    """

    def __init__(self, project_root: Path) -> None:
        from semantic_code_intelligence.config.settings import AppConfig

        self._dir = AppConfig.config_dir(project_root) / SESSIONS_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    def _session_path(self, session_id: str) -> Path:
        # Sanitise session_id to prevent path traversal
        safe_id = "".join(c for c in session_id if c.isalnum() or c in "-_")
        return self._dir / f"{safe_id}.json"

    def save(self, session: ConversationSession) -> Path:
        """Persist a session to disk."""
        path = self._session_path(session.session_id)
        path.write_text(json.dumps(session.to_dict(), indent=2), encoding="utf-8")
        logger.debug("Saved session %s (%d messages)", session.session_id, len(session.messages))
        return path

    def load(self, session_id: str) -> ConversationSession | None:
        """Load a session by ID.  Returns *None* if not found."""
        path = self._session_path(session_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return ConversationSession.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError):
            logger.warning("Corrupt session file %s", path)
            return None

    def list_sessions(self) -> list[dict[str, Any]]:
        """Return a summary of all stored sessions (newest first)."""
        sessions: list[dict[str, Any]] = []
        for p in self._dir.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                sessions.append({
                    "session_id": data["session_id"],
                    "title": data.get("title", ""),
                    "turns": len(data.get("messages", [])),
                    "created_at": data.get("created_at", 0),
                    "updated_at": data.get("updated_at", 0),
                })
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
        sessions.sort(key=lambda s: s["updated_at"], reverse=True)
        return sessions

    def delete(self, session_id: str) -> bool:
        """Delete a session file.  Returns True if it existed."""
        path = self._session_path(session_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def get_or_create(self, session_id: str | None = None) -> ConversationSession:
        """Load an existing session or create a new one."""
        if session_id:
            existing = self.load(session_id)
            if existing:
                return existing
        return ConversationSession()
