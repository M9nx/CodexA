"""Web interface and REST API layer for CodexA.

Provides an optional lightweight web UI and developer-friendly REST API
that wraps existing CodexA services.  Built on the Python standard library
(``http.server``) — no framework dependencies.

Components:
    api      — REST API endpoints (search, ask, analyze, health)
    ui       — Server-rendered HTML interface for browser access
    visualize — Mermaid-compatible text graph generators
"""
