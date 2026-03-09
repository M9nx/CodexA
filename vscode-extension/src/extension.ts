/**
 * CodexA VS Code Extension
 *
 * Provides semantic code search, call-graph visualisation, and
 * AI-powered Q&A by invoking the `codex` CLI under the hood.
 */

import * as vscode from "vscode";
import { execFile } from "child_process";
import { promisify } from "util";
import * as path from "path";
import * as fs from "fs";

const execFileAsync = promisify(execFile);

/**
 * Resolve the `codex` binary.  Priority:
 *  1. User setting `codexa.binaryPath`
 *  2. `.venv/Scripts/codex.exe`  (Windows)  or `.venv/bin/codex` (Unix)
 *     inside the workspace root
 *  3. Bare `codex` (hope it's on PATH)
 */
function codexBin(): string {
  const cfg = vscode.workspace.getConfiguration("codexa");
  const explicit = cfg.get<string>("binaryPath");
  if (explicit) { return explicit; }

  const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (root) {
    const isWin = process.platform === "win32";
    const venvBin = isWin
      ? path.join(root, ".venv", "Scripts", "codex.exe")
      : path.join(root, ".venv", "bin", "codex");
    if (fs.existsSync(venvBin)) { return venvBin; }
  }
  return "codex";
}

/** Return the workspace root or throw. */
function workspaceRoot(): string {
  const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (!root) { throw new Error("No workspace folder open."); }
  return root;
}

/**
 * Run a codex CLI command and return stdout.
 * `argv` is the argument array **without** the binary name.
 */
async function runCodex(argv: string[]): Promise<string> {
  const root = workspaceRoot();
  const bin = codexBin();
  const { stdout } = await execFileAsync(bin, argv, {
    cwd: root,
    maxBuffer: 10 * 1024 * 1024,
    windowsHide: true,
  });
  return stdout;
}

/**
 * Extract the first valid JSON object / array from raw CLI output
 * that may contain Rich log lines mixed in.
 */
function extractJson(raw: string): any {
  // Try full string first
  try { return JSON.parse(raw); } catch { /* ignore */ }
  // Find the first '{' or '['
  for (const ch of ["{", "["]) {
    const idx = raw.indexOf(ch);
    if (idx >= 0) {
      try { return JSON.parse(raw.slice(idx)); } catch { /* ignore */ }
    }
  }
  throw new Error("No valid JSON found in codex output");
}

// ---------------------------------------------------------------------------
// Webview search panel
// ---------------------------------------------------------------------------

class SearchViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = "codexaSearchView";

  constructor(private readonly _extensionUri: vscode.Uri) {}

  resolveWebviewView(
    webviewView: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken
  ): void {
    webviewView.webview.options = { enableScripts: true };
    webviewView.webview.html = this._getHtml();

    webviewView.webview.onDidReceiveMessage(async (msg) => {
      if (msg.type === "search") {
        try {
          const root = workspaceRoot();
          const raw = await runCodex(["search", msg.query, "-p", root, "--json"]);
          webviewView.webview.postMessage({ type: "results", data: extractJson(raw) });
        } catch (err: any) {
          webviewView.webview.postMessage({ type: "error", message: err.message });
        }
      } else if (msg.type === "open") {
        // Open a file at a specific line
        const uri = vscode.Uri.file(msg.filePath);
        const line = Math.max(0, (msg.line || 1) - 1);
        const doc = await vscode.workspace.openTextDocument(uri);
        const editor = await vscode.window.showTextDocument(doc, { preview: true });
        const pos = new vscode.Position(line, 0);
        editor.selection = new vscode.Selection(pos, pos);
        editor.revealRange(new vscode.Range(pos, pos), vscode.TextEditorRevealType.InCenter);
      }
    });
  }

  private _getHtml(): string {
    return /* html */ `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <style>
    body { font-family: var(--vscode-font-family); padding: 8px; margin: 0; }
    input {
      width: 100%; padding: 6px 8px; box-sizing: border-box;
      background: var(--vscode-input-background);
      color: var(--vscode-input-foreground);
      border: 1px solid var(--vscode-input-border);
      border-radius: 3px;
      outline: none;
    }
    input:focus { border-color: var(--vscode-focusBorder); }
    #status { font-size: 0.85em; color: var(--vscode-descriptionForeground); margin: 4px 0; }
    .result {
      margin: 6px 0; padding: 6px 8px;
      border: 1px solid var(--vscode-panel-border);
      border-radius: 4px; cursor: pointer;
    }
    .result:hover { background: var(--vscode-list-hoverBackground); }
    .file { font-weight: bold; font-size: 0.9em; }
    .meta { color: var(--vscode-descriptionForeground); font-size: 0.8em; }
    pre {
      white-space: pre-wrap; font-size: 0.82em; margin: 4px 0 0;
      max-height: 150px; overflow: auto;
      background: var(--vscode-textCodeBlock-background);
      padding: 4px; border-radius: 3px;
    }
  </style>
</head>
<body>
  <input id="q" placeholder="Search codebase…" />
  <div id="status"></div>
  <div id="results"></div>
  <script>
    const vscode = acquireVsCodeApi();
    const q = document.getElementById('q');
    const resultsEl = document.getElementById('results');
    const statusEl = document.getElementById('status');

    q.addEventListener('keydown', e => {
      if (e.key === 'Enter' && q.value.trim()) {
        vscode.postMessage({ type: 'search', query: q.value.trim() });
        resultsEl.innerHTML = '';
        statusEl.textContent = 'Searching…';
      }
    });

    window.addEventListener('message', e => {
      const msg = e.data;
      if (msg.type === 'results') {
        const items = msg.data.results || [];
        statusEl.textContent = items.length + ' result' + (items.length !== 1 ? 's' : '');
        resultsEl.innerHTML = items.length
          ? items.map((r, i) =>
              '<div class="result" data-file="' + escapeAttr(r.file_path) + '" data-line="' + r.start_line + '">' +
              '<div class="file">' + escapeHtml(shortPath(r.file_path)) +
              ':' + r.start_line + '-' + r.end_line + '</div>' +
              '<div class="meta">' + r.language + ' &middot; score ' + r.score.toFixed(4) + '</div>' +
              '<pre>' + escapeHtml(r.content.slice(0, 400)) + '</pre>' +
              '</div>'
            ).join('')
          : '<em>No results.</em>';
      } else if (msg.type === 'error') {
        statusEl.textContent = '';
        resultsEl.innerHTML = '<em style="color:var(--vscode-errorForeground);">' + escapeHtml(msg.message) + '</em>';
      }
    });

    resultsEl.addEventListener('click', e => {
      const card = e.target.closest('.result');
      if (card) {
        vscode.postMessage({
          type: 'open',
          filePath: card.dataset.file,
          line: parseInt(card.dataset.line, 10)
        });
      }
    });

    function escapeHtml(s) {
      return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }
    function escapeAttr(s) {
      return s.replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    }
    function shortPath(p) {
      const parts = p.replace(/\\\\/g, '/').split('/');
      return parts.length > 3 ? '…/' + parts.slice(-3).join('/') : p;
    }
  </script>
</body>
</html>`;
  }
}

// ---------------------------------------------------------------------------
// Extension activation
// ---------------------------------------------------------------------------

export function activate(context: vscode.ExtensionContext): void {
  // Sidebar search webview
  const provider = new SearchViewProvider(context.extensionUri);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(SearchViewProvider.viewType, provider)
  );

  // Command: search
  context.subscriptions.push(
    vscode.commands.registerCommand("codexa.search", async () => {
      const query = await vscode.window.showInputBox({ prompt: "CodexA: Enter search query" });
      if (!query) { return; }
      try {
        const root = workspaceRoot();
        const raw = await runCodex(["search", query, "-p", root, "--json"]);
        const data = extractJson(raw);
        const doc = await vscode.workspace.openTextDocument({
          content: JSON.stringify(data, null, 2),
          language: "json",
        });
        await vscode.window.showTextDocument(doc);
      } catch (err: any) {
        vscode.window.showErrorMessage(`CodexA search failed: ${err.message}`);
      }
    })
  );

  // Command: ask
  context.subscriptions.push(
    vscode.commands.registerCommand("codexa.askCodexA", async () => {
      const question = await vscode.window.showInputBox({ prompt: "Ask CodexA a question" });
      if (!question) { return; }
      try {
        const root = workspaceRoot();
        const raw = await runCodex(["ask", question, "-p", root]);
        const doc = await vscode.workspace.openTextDocument({ content: raw, language: "markdown" });
        await vscode.window.showTextDocument(doc);
      } catch (err: any) {
        vscode.window.showErrorMessage(`CodexA ask failed: ${err.message}`);
      }
    })
  );

  // Command: call graph
  context.subscriptions.push(
    vscode.commands.registerCommand("codexa.callGraph", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) { return; }
      const word = editor.document.getText(editor.document.getWordRangeAtPosition(editor.selection.active));
      if (!word) { return; }
      try {
        const raw = await runCodex(["tool", "run", "get_call_graph", "--arg", `symbol_name=${word}`]);
        const doc = await vscode.workspace.openTextDocument({ content: raw, language: "json" });
        await vscode.window.showTextDocument(doc);
      } catch (err: any) {
        vscode.window.showErrorMessage(`CodexA call graph failed: ${err.message}`);
      }
    })
  );

  // Command: models
  context.subscriptions.push(
    vscode.commands.registerCommand("codexa.models", async () => {
      try {
        const raw = await runCodex(["models", "list", "--json"]);
        const data = extractJson(raw);
        const doc = await vscode.workspace.openTextDocument({
          content: JSON.stringify(data, null, 2),
          language: "json",
        });
        await vscode.window.showTextDocument(doc);
      } catch (err: any) {
        vscode.window.showErrorMessage(`CodexA models failed: ${err.message}`);
      }
    })
  );
}

export function deactivate(): void {}
