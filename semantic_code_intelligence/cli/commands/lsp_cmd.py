"""CLI command: lsp — start the CodexA LSP server."""

from __future__ import annotations

from pathlib import Path

import click

from semantic_code_intelligence.config.settings import AppConfig
from semantic_code_intelligence.utils.logging import get_logger, print_error

logger = get_logger("cli.lsp")


@click.command("lsp")
@click.option(
    "--path",
    "-p",
    default=".",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Project root path.",
)
@click.pass_context
def lsp_cmd(ctx: click.Context, path: str) -> None:
    """Start the CodexA Language Server Protocol server.

    Runs over stdio using standard LSP Content-Length framing.
    Compatible with any LSP client: VS Code, Neovim, Sublime, JetBrains.

    \b
    VS Code settings.json:
      "codex.lsp.path": "/path/to/your/project"

    \b
    Neovim (nvim-lspconfig):
      require('lspconfig').codex.setup {
        cmd = { "codex", "lsp", "--path", "/your/project" },
      }
    """
    root = Path(path).resolve()
    config_dir = AppConfig.config_dir(root)

    if not config_dir.exists():
        print_error(f"Project not initialized at {root}. Run 'codex init' first.")
        ctx.exit(1)
        return

    from semantic_code_intelligence.lsp import run_lsp_server
    run_lsp_server(root)
