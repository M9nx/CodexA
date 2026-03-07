"""Bridge layer — external AI assistant interoperability for CodexA.

Provides:
- AgentRequest / AgentResponse: standard cooperation protocol
- ContextProvider: structured context generation for IDE AI pipelines
- BridgeServer: lightweight HTTP/JSON server exposing CodexA tools
- VSCodeBridge: VSCode extension communication helpers
"""

from __future__ import annotations

from semantic_code_intelligence.bridge.protocol import (
    AgentRequest,
    AgentResponse,
    BridgeCapabilities,
)
from semantic_code_intelligence.bridge.context_provider import ContextProvider
from semantic_code_intelligence.bridge.server import BridgeServer
from semantic_code_intelligence.bridge.vscode import VSCodeBridge

__all__ = [
    "AgentRequest",
    "AgentResponse",
    "BridgeCapabilities",
    "ContextProvider",
    "BridgeServer",
    "VSCodeBridge",
]
