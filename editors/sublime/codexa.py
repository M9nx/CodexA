"""CodexA — Sublime Text 4 plugin.

Provides semantic code search via the command palette and inline annotations.
Communicates with the CodexA bridge server at http://localhost:24842.
"""

import json
import urllib.request
import urllib.error
import sublime
import sublime_plugin

BRIDGE_URL = "http://localhost:24842"


def _bridge_post(endpoint: str, body: dict) -> dict | None:
    """POST JSON to the CodexA bridge server."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{BRIDGE_URL}{endpoint}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError) as exc:
        sublime.error_message(f"CodexA: {exc}\n\nMake sure 'codexa serve' is running.")
        return None


class CodexaSearchCommand(sublime_plugin.WindowCommand):
    """Semantic search via the command palette."""

    def run(self) -> None:
        self.window.show_input_panel(
            "CodexA Search:",
            "",
            self._on_done,
            None,
            None,
        )

    def _on_done(self, query: str) -> None:
        if not query.strip():
            return
        resp = _bridge_post("/request", {
            "kind": "semantic_search",
            "params": {"query": query, "top_k": 10},
        })
        if not resp or "data" not in resp:
            return
        results = resp.get("data", {}).get("results", [])
        if not results:
            sublime.status_message("CodexA: No results")
            return

        items = []
        self._results = results
        for r in results:
            fp = r.get("file_path", "?")
            ln = r.get("start_line", 0)
            snippet = (r.get("content", "") or "")[:100].replace("\n", " ")
            items.append([f"{fp}:{ln}", snippet])

        self.window.show_quick_panel(items, self._on_select)

    def _on_select(self, idx: int) -> None:
        if idx < 0:
            return
        r = self._results[idx]
        fp = r.get("file_path", "")
        ln = r.get("start_line", 1)
        view = self.window.open_file(f"{fp}:{ln}", sublime.ENCODED_POSITION)


class CodexaExplainSymbolCommand(sublime_plugin.TextCommand):
    """Explain the symbol under the cursor."""

    def run(self, edit: sublime.Edit) -> None:
        sel = self.view.sel()
        if not sel:
            return
        word = self.view.substr(self.view.word(sel[0]))
        if not word.strip():
            return

        resp = _bridge_post("/request", {
            "kind": "explain_symbol",
            "params": {"symbol_name": word},
        })
        if resp and "data" in resp:
            content = json.dumps(resp["data"], indent=2)
            panel = self.view.window().create_output_panel("codexa")
            panel.run_command("append", {"characters": content})
            self.view.window().run_command("show_panel", {"panel": "output.codexa"})


class CodexaReindexCommand(sublime_plugin.WindowCommand):
    """Trigger a re-index of the project."""

    def run(self) -> None:
        resp = _bridge_post("/request", {
            "kind": "invoke_tool",
            "params": {"tool_name": "reindex", "arguments": {"force": False}},
        })
        if resp:
            sublime.status_message("CodexA: Re-index complete")
