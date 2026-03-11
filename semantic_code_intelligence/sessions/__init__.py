"""Agent session manager — isolated contexts for concurrent AI agents.

Provides session-based isolation so multiple agents (e.g. two Copilot
instances, or Cursor + Claude Desktop) can share one CodexA server
without interfering with each other.

Each session has its own:
- Context window / search history
- Discovered symbol cache
- Coordinated context (shared discoveries across sessions)
"""

from __future__ import annotations

import time
import uuid
import threading
from dataclasses import dataclass, field
from typing import Any

from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("sessions")


@dataclass
class AgentSession:
    """An isolated agent session."""

    session_id: str
    agent_name: str = "anonymous"
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    context_cache: dict[str, Any] = field(default_factory=dict)
    search_history: list[dict[str, Any]] = field(default_factory=list)
    discovered_symbols: set[str] = field(default_factory=set)

    def touch(self) -> None:
        """Update last-active timestamp."""
        self.last_active = time.time()

    def add_search(self, query: str, result_count: int) -> None:
        """Record a search in this session's history."""
        self.search_history.append({
            "query": query,
            "result_count": result_count,
            "timestamp": time.time(),
        })
        self.touch()

    def add_discovered_symbol(self, symbol: str) -> None:
        """Record a discovered symbol for coordinated context."""
        self.discovered_symbols.add(symbol)
        self.touch()

    def to_dict(self) -> dict[str, Any]:
        """Serialize session metadata."""
        return {
            "session_id": self.session_id,
            "agent_name": self.agent_name,
            "created_at": self.created_at,
            "last_active": self.last_active,
            "search_count": len(self.search_history),
            "discovered_symbols": len(self.discovered_symbols),
        }


class SessionManager:
    """Thread-safe manager for concurrent agent sessions."""

    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._sessions: dict[str, AgentSession] = {}
        self._lock = threading.Lock()
        self._ttl = ttl_seconds
        # Shared discovery pool across all sessions
        self._shared_discoveries: dict[str, dict[str, Any]] = {}

    def create_session(self, agent_name: str = "anonymous") -> AgentSession:
        """Create a new isolated session."""
        session_id = uuid.uuid4().hex[:16]
        session = AgentSession(session_id=session_id, agent_name=agent_name)
        with self._lock:
            self._sessions[session_id] = session
        logger.info("Session created: %s (agent=%s)", session_id, agent_name)
        return session

    def get_session(self, session_id: str) -> AgentSession | None:
        """Retrieve a session by ID."""
        with self._lock:
            session = self._sessions.get(session_id)
        if session:
            session.touch()
        return session

    def get_or_create(self, session_id: str | None, agent_name: str = "anonymous") -> AgentSession:
        """Get an existing session or create a new one."""
        if session_id:
            session = self.get_session(session_id)
            if session:
                return session
        return self.create_session(agent_name)

    def close_session(self, session_id: str) -> bool:
        """Close and remove a session."""
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session:
            logger.info("Session closed: %s", session_id)
            return True
        return False

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all active sessions."""
        self._cleanup_expired()
        with self._lock:
            return [s.to_dict() for s in self._sessions.values()]

    def share_discovery(self, source_session_id: str, key: str, data: dict[str, Any]) -> None:
        """Share a discovered context item across all sessions.

        Enables coordinated context: when one agent discovers useful
        context, other agents can access it to avoid redundant searches.
        """
        with self._lock:
            self._shared_discoveries[key] = {
                "data": data,
                "source_session": source_session_id,
                "timestamp": time.time(),
            }

    def get_shared_discoveries(self, exclude_session: str | None = None) -> list[dict[str, Any]]:
        """Get all shared discoveries, optionally excluding one session's own."""
        with self._lock:
            results = []
            for key, item in self._shared_discoveries.items():
                if exclude_session and item["source_session"] == exclude_session:
                    continue
                results.append({"key": key, **item})
            return results

    def _cleanup_expired(self) -> None:
        """Remove sessions that haven't been active within the TTL."""
        cutoff = time.time() - self._ttl
        with self._lock:
            expired = [
                sid for sid, s in self._sessions.items()
                if s.last_active < cutoff
            ]
            for sid in expired:
                del self._sessions[sid]
                logger.debug("Session expired: %s", sid)

    @property
    def active_count(self) -> int:
        """Number of active sessions."""
        with self._lock:
            return len(self._sessions)
