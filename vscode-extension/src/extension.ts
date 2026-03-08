/**
 * CodexA VS Code Extension
 *
 * Provides semantic code search, call-graph visualisation, and
 * AI-powered Q&A by invoking the `codex` CLI under the hood.
 */

import * as vscode from "vscode";
import { exec } from "child_process";
import { promisify } from "util";

const execAsync = promisify(exec);

/** Resolve the `codex` binary — honours the config override or falls back to PATH. */
function codexBin(): string {
  const cfg = vscode.workspace.getConfiguration("codexa");
  return cfg.get<string>("binaryPath") || "codex";
}

/** Run a codex CLI command in the workspace root and return stdout. */
async function runCodex(args: string): Promise<string> {
  const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (!root) {
    throw new Error("No workspace folder open.");
  }
  const cmd = `${codexBin()} ${args} --path "${root}" --json`;
  const { stdout } = await execAsync(cmd, { cwd: root, maxBuffer: 10 * 1024 * 1024 });
  return stdout;
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
          const raw = await runCodex(`search "${msg.query}"`);
          webviewView.webview.postMessage({ type: "results", data: JSON.parse(raw) });
        } catch (err: any) {
          webviewView.webview.postMessage({ type: "error", message: err.message });
        }
      }
    });
  }

  private _getHtml(): string {
    return /* html */ `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <style>
    body { font-family: var(--vscode-font-family); padding: 8px; }
    input { width: 100%; padding: 6px; box-sizing: border-box; }
    .result { margin: 8px 0; padding: 6px; border: 1px solid var(--vscode-panel-border); border-radius: 4px; cursor: pointer; }
    .result:hover { background: var(--vscode-list-hoverBackground); }
    .file { font-weight: bold; }
    .score { color: var(--vscode-descriptionForeground); font-size: 0.85em; }
    pre { white-space: pre-wrap; font-size: 0.85em; max-height: 200px; overflow: auto; }
  </style>
</head>
<body>
  <input id="q" placeholder="Search codebase…" />
  <div id="results"></div>
  <script>
    const vscode = acquireVsCodeApi();
    const q = document.getElementById('q');
    const resultsEl = document.getElementById('results');

    q.addEventListener('keydown', e => {
      if (e.key === 'Enter' && q.value.trim()) {
        vscode.postMessage({ type: 'search', query: q.value.trim() });
        resultsEl.innerHTML = '<em>Searching…</em>';
      }
    });

    window.addEventListener('message', e => {
      const msg = e.data;
      if (msg.type === 'results') {
        const items = msg.data.results || [];
        resultsEl.innerHTML = items.length
          ? items.map(r =>
              '<div class="result">' +
              '<div class="file">' + r.file_path + ' <span class="score">(' + r.score.toFixed(4) + ')</span></div>' +
              '<pre>' + escapeHtml(r.content.slice(0, 500)) + '</pre>' +
              '</div>'
            ).join('')
          : '<em>No results.</em>';
      } else if (msg.type === 'error') {
        resultsEl.innerHTML = '<em style="color:red;">' + msg.message + '</em>';
      }
    });

    function escapeHtml(s) {
      return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
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
        const raw = await runCodex(`search "${query}"`);
        const data = JSON.parse(raw);
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
        const raw = await runCodex(`ask "${question}"`);
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
        const raw = await runCodex(`tool run get_call_graph --arg symbol_name="${word}"`);
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
        const raw = await runCodex("models list");
        const doc = await vscode.workspace.openTextDocument({
          content: raw,
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
