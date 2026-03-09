"""Interactive TUI — full-featured terminal user interface for code search.

Provides a split-pane search interface with:
- Live search input
- Scrollable results list
- Syntax-highlighted file preview
- Mode switching (semantic/keyword/regex/hybrid)

Uses ``textual`` when available; falls back to a simple REPL otherwise.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from semantic_code_intelligence.config.settings import AppConfig, load_config
from semantic_code_intelligence.services.search_service import SearchMode, search_codebase
from semantic_code_intelligence.utils.logging import get_logger

logger = get_logger("tui")


def _textual_available() -> bool:
    """Check if the textual library is installed."""
    try:
        import textual  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Textual TUI (rich split-pane interface)
# ---------------------------------------------------------------------------

def _run_textual_tui(
    project_root: Path,
    mode: SearchMode = "hybrid",
    top_k: int = 10,
) -> None:
    """Run the full Textual TUI."""
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical
    from textual.widgets import (
        Footer,
        Header,
        Input,
        Label,
        ListItem,
        ListView,
        Static,
    )

    class ResultItem(ListItem):
        """A single search result row."""

        def __init__(self, result: Any, index: int) -> None:
            self.result = result
            self.result_index = index
            path = Path(result.file_path).name
            label = f"#{index} [{result.score:.3f}]  {path}:L{result.start_line}-{result.end_line}  ({result.language})"
            super().__init__(Label(label), id=f"result-{index}")

    class CodexaTUI(App):
        """CodexA Interactive Search TUI."""

        TITLE = "CodexA Search"
        CSS = """
        Screen {
            layout: vertical;
        }
        #search-bar {
            dock: top;
            height: 3;
            padding: 0 1;
            border: tall $accent;
        }
        #mode-bar {
            dock: top;
            height: 1;
            color: $text-muted;
            padding: 0 2;
            background: $surface;
        }
        #main-pane {
            height: 1fr;
        }
        #results-pane {
            width: 2fr;
            min-width: 30;
            border-right: solid $primary;
        }
        #preview-pane {
            width: 3fr;
            min-width: 40;
            overflow-y: auto;
            padding: 0 1;
        }
        #preview-content {
            width: 1fr;
        }
        #status-bar {
            dock: bottom;
            height: 1;
            color: $text-muted;
            padding: 0 2;
            background: $surface;
        }
        ResultItem {
            height: auto;
            padding: 0 1;
        }
        ResultItem:hover {
            background: $boost;
        }
        ListView > ResultItem.-active {
            background: $accent 30%;
        }
        """

        BINDINGS = [
            Binding("ctrl+q", "quit", "Quit", show=True),
            Binding("ctrl+m", "cycle_mode", "Mode", show=True),
            Binding("ctrl+k", "increase_topk", "K+", show=True),
            Binding("ctrl+j", "decrease_topk", "K-", show=True),
            Binding("escape", "clear_search", "Clear", show=True),
        ]

        def __init__(self) -> None:
            super().__init__()
            self.current_mode: SearchMode = mode
            self.current_top_k: int = top_k
            self.current_results: list[Any] = []
            self.project_root = project_root

        def compose(self) -> ComposeResult:
            yield Header()
            yield Input(placeholder="Type a search query...", id="search-bar")
            yield Label(
                f"  Mode: {self.current_mode} | Top-K: {self.current_top_k} | Project: {project_root.name}",
                id="mode-bar",
            )
            with Horizontal(id="main-pane"):
                with Vertical(id="results-pane"):
                    yield ListView(id="results-list")
                yield Static("Select a result to preview code...", id="preview-pane")
            yield Label("  Ready", id="status-bar")
            yield Footer()

        async def on_input_submitted(self, event: Input.Submitted) -> None:
            query = event.value.strip()
            if not query:
                return
            status = self.query_one("#status-bar", Label)
            status.update(f"  Searching: {query!r} (mode={self.current_mode})...")
            try:
                results = search_codebase(
                    query=query,
                    project_root=self.project_root,
                    top_k=self.current_top_k,
                    mode=self.current_mode,
                    auto_index=True,
                )
                self.current_results = results
                lv = self.query_one("#results-list", ListView)
                await lv.clear()
                for i, r in enumerate(results, 1):
                    await lv.append(ResultItem(r, i))
                status.update(f"  Found {len(results)} results for: {query!r}")
                # Show preview of first result
                if results:
                    self._show_preview(results[0])
            except FileNotFoundError:
                status.update("  Index not found. Run 'codex index' first.")
            except Exception as e:
                status.update(f"  Error: {e}")

        def on_list_view_selected(self, event: ListView.Selected) -> None:
            item = event.item
            if isinstance(item, ResultItem):
                self._show_preview(item.result)

        def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
            item = event.item
            if isinstance(item, ResultItem):
                self._show_preview(item.result)

        def _show_preview(self, result: Any) -> None:
            """Render syntax-highlighted code in the preview pane."""
            lines = result.content.splitlines()
            numbered = []
            for i, line in enumerate(lines, start=result.start_line):
                numbered.append(f"{i:>5} | {line}")
            header = f"  {result.file_path}  L{result.start_line}-{result.end_line}  ({result.language})\n"
            separator = "  " + "-" * 60 + "\n"
            code_text = header + separator + "\n".join(numbered)
            preview = self.query_one("#preview-pane", Static)
            preview.update(code_text)

        def action_cycle_mode(self) -> None:
            modes: list[SearchMode] = ["semantic", "keyword", "regex", "hybrid"]
            idx = modes.index(self.current_mode)
            self.current_mode = modes[(idx + 1) % len(modes)]
            self._update_mode_bar()
            status = self.query_one("#status-bar", Label)
            status.update(f"  Mode changed to: {self.current_mode}")

        def action_increase_topk(self) -> None:
            self.current_top_k = min(self.current_top_k + 5, 50)
            self._update_mode_bar()
            status = self.query_one("#status-bar", Label)
            status.update(f"  Top-K set to: {self.current_top_k}")

        def action_decrease_topk(self) -> None:
            self.current_top_k = max(self.current_top_k - 5, 5)
            self._update_mode_bar()
            status = self.query_one("#status-bar", Label)
            status.update(f"  Top-K set to: {self.current_top_k}")

        def _update_mode_bar(self) -> None:
            mode_bar = self.query_one("#mode-bar", Label)
            mode_bar.update(
                f"  Mode: {self.current_mode} | Top-K: {self.current_top_k} | Project: {project_root.name}"
            )

        def action_clear_search(self) -> None:
            search_input = self.query_one("#search-bar", Input)
            search_input.value = ""
            search_input.focus()

    app = CodexaTUI()
    app.run()


# ---------------------------------------------------------------------------
# Fallback REPL (no textual dependency)
# ---------------------------------------------------------------------------


def _format_result_line(i: int, r: Any) -> str:
    """Format a single result as a compact line for TUI display."""
    path = r.file_path
    try:
        path = str(Path(r.file_path).name)
    except Exception:
        pass
    return f"  {i:>3}. [{r.score:.3f}] {path}:L{r.start_line}-{r.end_line}  {r.language}"


def _print_results(results: list[Any], query: str) -> None:
    """Print results in a compact format."""
    try:
        from rich.console import Console as RichConsole
        from rich.table import Table
        c = RichConsole()
        if not results:
            c.print(f"\n  [dim]No results for:[/dim] {query!r}\n")
            return
        c.print(f"\n  [bold green]{len(results)}[/bold green] results for: [cyan]{query!r}[/cyan]\n")
        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
        table.add_column("#", style="dim", width=4)
        table.add_column("Score", style="yellow", width=7)
        table.add_column("File", style="cyan")
        table.add_column("Lines", style="dim")
        table.add_column("Lang", style="magenta")
        for i, r in enumerate(results, 1):
            path = r.file_path
            try:
                path = str(Path(r.file_path).name)
            except Exception:
                pass
            table.add_row(str(i), f"{r.score:.3f}", path, f"L{r.start_line}-{r.end_line}", r.language)
        c.print(table)
        c.print()
    except ImportError:
        if not results:
            print(f"\n  No results for: {query!r}\n")
            return
        print(f"\n  Found {len(results)} results for: {query!r}\n")
        for i, r in enumerate(results, 1):
            print(_format_result_line(i, r))
        print()


def _show_detail(results: list[Any], index: int) -> None:
    """Show full content of a result."""
    if index < 1 or index > len(results):
        print(f"  Invalid selection. Enter 1-{len(results)}.")
        return
    r = results[index - 1]
    try:
        from rich.console import Console as RichConsole
        from rich.syntax import Syntax
        c = RichConsole()
        c.print(f"\n  [bold cyan]{r.file_path}[/bold cyan]  L{r.start_line}-{r.end_line}\n")
        c.rule(style="dim")
        lang = getattr(r, "language", "python") or "text"
        c.print(Syntax(r.content, lang, theme="monokai", line_numbers=True, start_line=r.start_line))
        c.print()
    except ImportError:
        print(f"\n  === {r.file_path} L{r.start_line}-{r.end_line} ===\n")
        for i, line in enumerate(r.content.splitlines(), start=r.start_line):
            print(f"  {i:>5} | {line}")
        print()


def _run_fallback_repl(
    project_root: Path,
    mode: SearchMode = "hybrid",
    top_k: int = 10,
) -> None:
    """Run the simple fallback REPL (no textual)."""
    project_root = project_root.resolve()

    try:
        from rich.console import Console as RichConsole
        c = RichConsole()
        try:
            c.rule("[bold cyan]CodexA Interactive Search[/bold cyan]", style="cyan")
            c.print(f"  [dim]Mode:[/dim] {mode}  [dim]Top-K:[/dim] {top_k}  [dim]Project:[/dim] {project_root.name}")
            c.print("  [dim]Commands:[/dim] /mode <m>  /topk <n>  /view <n>  /explain <sym>  /help  /quit")
            c.rule(style="dim")
            c.print()
        except (UnicodeEncodeError, OSError):
            print(f"\n  CodexA Interactive Search  (mode={mode}, top_k={top_k})")
            print(f"  Project: {project_root}")
            print("  Commands: /mode <m>  /topk <n>  /view <n>  /explain <sym>  /help  /quit\n")
    except ImportError:
        print(f"\n  CodexA Interactive Search  (mode={mode}, top_k={top_k})")
        print(f"  Project: {project_root}")
        print("  Commands: /mode <m>  /topk <n>  /view <n>  /explain <sym>  /help  /quit\n")

    current_mode: SearchMode = mode
    current_top_k: int = top_k
    last_results: list[Any] = []

    while True:
        try:
            line = input("  search> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Bye!\n")
            break

        if not line:
            continue

        if line.lower() in ("/quit", "/exit", "/q"):
            print("  Bye!\n")
            break

        if line.lower() == "/help":
            print("  Commands:")
            print("    /mode <semantic|keyword|regex|hybrid>  — change search mode")
            print("    /topk <n>                              — set number of results")
            print("    /view <n>                              — view result details")
            print("    /explain <symbol>                      — explain a symbol")
            print("    /quit                                  — exit")
            print()
            continue

        if line.lower().startswith("/mode "):
            new_mode = line.split(maxsplit=1)[1].lower()
            if new_mode in ("semantic", "keyword", "regex", "hybrid"):
                current_mode = new_mode  # type: ignore[assignment]
                print(f"  Mode set to: {current_mode}")
            else:
                print("  Valid modes: semantic, keyword, regex, hybrid")
            continue

        if line.lower().startswith("/topk "):
            try:
                current_top_k = max(1, min(50, int(line.split()[1])))
                print(f"  Top-K set to: {current_top_k}")
            except (ValueError, IndexError):
                print("  Usage: /topk <number>")
            continue

        if line.lower().startswith("/view "):
            try:
                idx = int(line.split()[1])
                _show_detail(last_results, idx)
            except (ValueError, IndexError):
                print("  Usage: /view <number>")
            continue

        if line.lower().startswith("/explain "):
            symbol_name = line.split(maxsplit=1)[1].strip()
            try:
                from semantic_code_intelligence.tools.executor import ToolExecutor
                from semantic_code_intelligence.tools.protocol import ToolInvocation
                executor = ToolExecutor(project_root)
                inv = ToolInvocation(tool_name="explain_symbol", arguments={"symbol_name": symbol_name})
                result = executor.execute(inv)
                if result.success and result.result_payload:
                    payload = result.result_payload
                    explanation = payload.get("explanation", "No explanation available.")
                    try:
                        from rich.console import Console as RichConsole
                        from rich.panel import Panel
                        rc = RichConsole()
                        rc.print(Panel(explanation, title=symbol_name, border_style="cyan"))
                    except ImportError:
                        print(f"\n  {symbol_name}: {explanation}\n")
                else:
                    err = result.error.error_message if result.error else "Unknown error"
                    print(f"  Error: {err}")
            except Exception as e:
                print(f"  Explain failed: {e}")
            continue

        # Execute search
        try:
            results = search_codebase(
                query=line,
                project_root=project_root,
                top_k=current_top_k,
                mode=current_mode,
                auto_index=True,
            )
            last_results = results
            _print_results(results, line)
        except FileNotFoundError:
            print("  Index not found. Run 'codex index' first.")
        except Exception as e:
            print(f"  Search error: {e}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_tui(
    project_root: Path,
    mode: SearchMode = "hybrid",
    top_k: int = 10,
) -> None:
    """Run the interactive TUI search interface.

    Uses the full Textual split-pane TUI when ``textual`` is installed,
    otherwise falls back to a simple input-loop REPL.

    Args:
        project_root: Project root directory.
        mode: Default search mode.
        top_k: Number of results per query.
    """
    if _textual_available():
        _run_textual_tui(project_root, mode=mode, top_k=top_k)
    else:
        _run_fallback_repl(project_root, mode=mode, top_k=top_k)
