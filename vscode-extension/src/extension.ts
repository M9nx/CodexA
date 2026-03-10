/**
 * CodexA VS Code Extension — Developer Intelligence Engine
 *
 * Multi-panel sidebar with semantic search, symbol explorer, quality
 * analysis, tool runner, and AI Q&A — all powered by the `codexa` CLI.
 */

import * as vscode from "vscode";
import { execFile } from "child_process";
import { promisify } from "util";
import * as path from "path";
import * as fs from "fs";

const execFileAsync = promisify(execFile);
let outputChannel: vscode.OutputChannel;
let statusBarItem: vscode.StatusBarItem;

// ── Binary resolution ────────────────────────────────────────────────
function codexBin(): string {
  const cfg = vscode.workspace.getConfiguration("codexa");
  const explicit = cfg.get<string>("binaryPath");
  if (explicit) { return explicit; }
  const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (root) {
    const isWin = process.platform === "win32";
    const venvBin = isWin
      ? path.join(root, ".venv", "Scripts", "codexa.exe")
      : path.join(root, ".venv", "bin", "codexa");
    if (fs.existsSync(venvBin)) { return venvBin; }
  }
  return "codexa";
}

function workspaceRoot(): string {
  const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (!root) { throw new Error("No workspace folder open."); }
  return root;
}

// ── CLI runner — always uses --pipe for clean stdout ─────────────────
async function runCodex(argv: string[]): Promise<string> {
  const root = workspaceRoot();
  const bin = codexBin();
  // --pipe is a GLOBAL flag (before subcommand) that disables Rich
  // console formatting so stdout is clean text/JSON.
  const fullArgv = ["--pipe", ...argv];
  outputChannel.appendLine(`$ codexa ${fullArgv.join(" ")}`);
  const { stdout, stderr } = await execFileAsync(bin, fullArgv, {
    cwd: root,
    maxBuffer: 10 * 1024 * 1024,
    windowsHide: true,
  });
  if (stderr) { outputChannel.appendLine(stderr.slice(0, 500)); }
  return stdout;
}

function extractJson(raw: string): any {
  try { return JSON.parse(raw); } catch { /* ignore */ }
  for (const ch of ["{", "["]) {
    const idx = raw.indexOf(ch);
    if (idx >= 0) {
      try { return JSON.parse(raw.slice(idx)); } catch { /* ignore */ }
    }
  }
  throw new Error("No valid JSON found in codexa output");
}

function setStatus(text: string, timeout = 5000): void {
  statusBarItem.text = `$(telescope) ${text}`;
  statusBarItem.show();
  if (timeout > 0) { setTimeout(() => statusBarItem.hide(), timeout); }
}

// ── Shared helpers for webview HTML ──────────────────────────────────
const SHARED_CSS = /* css */ `
  :root { --radius: 4px; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: var(--vscode-font-family); font-size: 13px;
         color: var(--vscode-foreground); padding: 8px; }
  input, select, textarea {
    width: 100%; padding: 6px 8px;
    background: var(--vscode-input-background);
    color: var(--vscode-input-foreground);
    border: 1px solid var(--vscode-input-border, transparent);
    border-radius: var(--radius); outline: none; font-size: 12px;
  }
  input:focus, select:focus, textarea:focus { border-color: var(--vscode-focusBorder); }
  button {
    padding: 5px 12px; border: none; border-radius: var(--radius);
    background: var(--vscode-button-background);
    color: var(--vscode-button-foreground);
    cursor: pointer; font-size: 12px; font-weight: 600;
  }
  button:hover { background: var(--vscode-button-hoverBackground); }
  button.secondary {
    background: var(--vscode-button-secondaryBackground);
    color: var(--vscode-button-secondaryForeground);
  }
  .row { display: flex; gap: 6px; margin-bottom: 6px; align-items: center; }
  .grow { flex: 1; }
  .status { font-size: 11px; color: var(--vscode-descriptionForeground); padding: 4px 0; }
  .card {
    margin: 6px 0; padding: 8px; border-radius: var(--radius);
    border: 1px solid var(--vscode-panel-border); cursor: pointer;
    transition: background 0.1s;
  }
  .card:hover { background: var(--vscode-list-hoverBackground); }
  .card-title { font-weight: 600; font-size: 12px; }
  .card-meta { color: var(--vscode-descriptionForeground); font-size: 11px; margin-top: 2px; }
  pre {
    white-space: pre-wrap; font-size: 11px; margin: 4px 0 0;
    max-height: 120px; overflow: auto;
    background: var(--vscode-textCodeBlock-background);
    padding: 6px; border-radius: var(--radius);
  }
  .badge {
    display: inline-block; padding: 1px 6px; border-radius: 10px;
    font-size: 10px; font-weight: 600;
  }
  .badge-green { background: var(--vscode-testing-iconPassed); color: #fff; }
  .badge-red { background: var(--vscode-testing-iconFailed); color: #fff; }
  .badge-yellow { background: var(--vscode-editorWarning-foreground); color: #000; }
  .badge-blue { background: var(--vscode-textLink-foreground); color: #fff; }
  .empty { text-align: center; color: var(--vscode-descriptionForeground);
           padding: 20px 0; font-style: italic; }
  .section-title { font-weight: 700; font-size: 12px; padding: 8px 0 4px;
                    border-bottom: 1px solid var(--vscode-panel-border);
                    margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px; }
  .tag { display: inline-block; padding: 1px 5px; font-size: 10px;
         background: var(--vscode-badge-background); color: var(--vscode-badge-foreground);
         border-radius: 3px; margin: 1px 2px; }
  .progress { width: 100%; height: 3px; background: var(--vscode-progressBar-background);
              border-radius: 2px; overflow: hidden; }
  .progress-bar { height: 100%; background: var(--vscode-textLink-foreground);
                  transition: width 0.3s; }
  @keyframes spin { to { transform: rotate(360deg); } }
  @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
  .spinner { display: inline-block; width: 14px; height: 14px;
             border: 2px solid var(--vscode-descriptionForeground);
             border-top-color: var(--vscode-textLink-foreground);
             border-radius: 50%; animation: spin 0.8s linear infinite;
             vertical-align: middle; margin-right: 4px; }
  .fade-in { animation: fadeIn 0.3s ease; }
  .separator { border: none; border-top: 1px solid var(--vscode-panel-border); margin: 10px 0; }
  .param-group { margin: 6px 0; }
  .param-label { font-size: 11px; font-weight: 600; display: flex; align-items: center; gap: 4px; margin-bottom: 2px; }
  .param-req { color: var(--vscode-errorForeground); font-weight: 700; }
  .param-desc { font-size: 10px; color: var(--vscode-descriptionForeground); margin-bottom: 2px; }
  .tool-desc { font-size: 11px; color: var(--vscode-descriptionForeground); padding: 4px 0 8px; font-style: italic; }
  .success-text { color: var(--vscode-testing-iconPassed); }
  .error-text { color: var(--vscode-testing-iconFailed); }
`;

const SHARED_JS = /* js */ `
  const vscode = acquireVsCodeApi();
  function escapeHtml(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }
  function shortPath(p) {
    const parts = p.replace(/\\\\/g,'/').split('/');
    return parts.length > 3 ? '…/' + parts.slice(-3).join('/') : p;
  }
  function post(type, data) { vscode.postMessage({ type, ...data }); }
`;

// Helper to open a file at a specific line
async function openFileAtLine(filePath: string, line: number): Promise<void> {
  const uri = vscode.Uri.file(filePath);
  const doc = await vscode.workspace.openTextDocument(uri);
  const editor = await vscode.window.showTextDocument(doc, { preview: true });
  const pos = new vscode.Position(Math.max(0, line - 1), 0);
  editor.selection = new vscode.Selection(pos, pos);
  editor.revealRange(new vscode.Range(pos, pos), vscode.TextEditorRevealType.InCenter);
}

// ══════════════════════════════════════════════════════════════════════
// PANEL 1: SEARCH (multi-mode with filters)
// ══════════════════════════════════════════════════════════════════════
class SearchViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = "codexaSearchView";
  constructor(private readonly _extensionUri: vscode.Uri) {}

  resolveWebviewView(wv: vscode.WebviewView): void {
    wv.webview.options = { enableScripts: true };
    wv.webview.html = this._html();
    wv.webview.onDidReceiveMessage(async (msg) => {
      if (msg.type === "search") {
        try {
          setStatus("Searching…", 0);
          const root = workspaceRoot();
          const args = ["search", msg.query, "-p", root, "--json"];
          if (msg.mode && msg.mode !== "semantic") { args.push("--mode", msg.mode); }
          if (msg.topK) { args.push("--top-k", String(msg.topK)); }
          const raw = await runCodex(args);
          const data = extractJson(raw);
          wv.webview.postMessage({ type: "results", data });
          setStatus(`${(data.results || []).length} results`);
        } catch (err: any) {
          wv.webview.postMessage({ type: "error", message: err.message });
          setStatus("Search failed");
        }
      } else if (msg.type === "open") {
        await openFileAtLine(msg.filePath, msg.line || 1);
      }
    });
  }

  private _html(): string {
    return /* html */ `<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>${SHARED_CSS}</style></head><body>
  <div class="row">
    <input id="q" class="grow" placeholder="Search codebase… (Enter)" />
  </div>
  <div class="row">
    <select id="mode" style="width:auto; flex:1">
      <option value="semantic">Semantic</option>
      <option value="keyword">Keyword</option>
      <option value="hybrid">Hybrid</option>
      <option value="regex">Regex</option>
    </select>
    <select id="topk" style="width:auto; flex:1">
      <option value="5">Top 5</option>
      <option value="10" selected>Top 10</option>
      <option value="20">Top 20</option>
    </select>
    <button id="go">Search</button>
  </div>
  <div id="status" class="status"></div>
  <div id="results"></div>
  <script>${SHARED_JS}
    const q = document.getElementById('q');
    const mode = document.getElementById('mode');
    const topk = document.getElementById('topk');
    const statusEl = document.getElementById('status');
    const resultsEl = document.getElementById('results');

    function doSearch() {
      if (!q.value.trim()) return;
      post('search', { query: q.value.trim(), mode: mode.value, topK: topk.value });
      resultsEl.innerHTML = '';
      statusEl.textContent = 'Searching…';
    }
    q.addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });
    document.getElementById('go').addEventListener('click', doSearch);

    window.addEventListener('message', e => {
      const msg = e.data;
      if (msg.type === 'results') {
        const items = msg.data.results || msg.data.snippets || [];
        statusEl.textContent = items.length + ' result' + (items.length !== 1 ? 's' : '');
        if (!items.length) { resultsEl.innerHTML = '<div class="empty">No results found.</div>'; return; }
        resultsEl.innerHTML = items.map(r => {
          const score = (r.score || 0).toFixed(4);
          return '<div class="card" data-file="' + escapeHtml(r.file_path) + '" data-line="' + r.start_line + '">'
            + '<div class="card-title">' + escapeHtml(shortPath(r.file_path))
            + ':' + r.start_line + '-' + r.end_line + '</div>'
            + '<div class="card-meta"><span class="tag">' + escapeHtml(r.language || '?') + '</span> score ' + score + '</div>'
            + '<pre>' + escapeHtml((r.content || '').slice(0, 500)) + '</pre></div>';
        }).join('');
      } else if (msg.type === 'error') {
        statusEl.textContent = '';
        resultsEl.innerHTML = '<div class="empty" style="color:var(--vscode-errorForeground)">' + escapeHtml(msg.message) + '</div>';
      }
    });
    resultsEl.addEventListener('click', e => {
      const c = e.target.closest('.card');
      if (c) post('open', { filePath: c.dataset.file, line: +c.dataset.line });
    });
  </script></body></html>`;
  }
}

// ══════════════════════════════════════════════════════════════════════
// PANEL 2: SYMBOLS (browse indexed symbols)
// ══════════════════════════════════════════════════════════════════════
class SymbolsViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = "codexaSymbolsView";
  constructor(private readonly _extensionUri: vscode.Uri) {}

  resolveWebviewView(wv: vscode.WebviewView): void {
    wv.webview.options = { enableScripts: true };
    wv.webview.html = this._html();
    wv.webview.onDidReceiveMessage(async (msg) => {
      if (msg.type === "explain") {
        try {
          setStatus("Explaining…", 0);
          const raw = await runCodex(["tool", "run", "explain_symbol", "--arg", `symbol_name=${msg.symbol}`, "--json"]);
          wv.webview.postMessage({ type: "explain-result", data: extractJson(raw) });
          setStatus("Done");
        } catch (err: any) {
          wv.webview.postMessage({ type: "error", message: err.message });
        }
      } else if (msg.type === "deps") {
        try {
          const editor = vscode.window.activeTextEditor;
          const filePath = msg.filePath || editor?.document.uri.fsPath || "";
          const rel = path.relative(workspaceRoot(), filePath);
          const raw = await runCodex(["tool", "run", "get_dependencies", "--arg", `file_path=${rel}`, "--json"]);
          wv.webview.postMessage({ type: "deps-result", data: extractJson(raw) });
        } catch (err: any) {
          wv.webview.postMessage({ type: "error", message: err.message });
        }
      } else if (msg.type === "callgraph") {
        try {
          const raw = await runCodex(["tool", "run", "get_call_graph", "--arg", `symbol_name=${msg.symbol}`, "--json"]);
          wv.webview.postMessage({ type: "callgraph-result", data: extractJson(raw) });
        } catch (err: any) {
          wv.webview.postMessage({ type: "error", message: err.message });
        }
      } else if (msg.type === "references") {
        try {
          const raw = await runCodex(["tool", "run", "find_references", "--arg", `symbol_name=${msg.symbol}`, "--json"]);
          wv.webview.postMessage({ type: "references-result", data: extractJson(raw) });
        } catch (err: any) {
          wv.webview.postMessage({ type: "error", message: err.message });
        }
      } else if (msg.type === "open") {
        await openFileAtLine(msg.filePath, msg.line || 1);
      }
    });
  }

  private _html(): string {
    return /* html */ `<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>${SHARED_CSS}
  .tool-row { display: flex; gap: 4px; margin-bottom: 8px; }
  .tool-row input { flex: 1; }
  .tool-row button { white-space: nowrap; }
  .result-box { max-height: 400px; overflow: auto; }
</style></head><body>
  <div class="section-title">Explain Symbol</div>
  <div class="tool-row">
    <input id="sym" placeholder="Symbol name…" />
    <button id="explain-btn">Explain</button>
  </div>
  <div class="section-title">Call Graph</div>
  <div class="tool-row">
    <input id="cg-sym" placeholder="Function name…" />
    <button id="cg-btn">Graph</button>
  </div>
  <div class="section-title">File Dependencies</div>
  <div class="tool-row">
    <button id="deps-btn" style="width:100%">Show deps of active file</button>
  </div>
  <div class="section-title">Find References</div>
  <div class="tool-row">
    <input id="ref-sym" placeholder="Symbol name…" />
    <button id="ref-btn">Find</button>
  </div>
  <div id="status" class="status"></div>
  <div id="output" class="result-box"></div>
  <script>${SHARED_JS}
    const outputEl = document.getElementById('output');
    const statusEl = document.getElementById('status');

    document.getElementById('explain-btn').addEventListener('click', () => {
      const v = document.getElementById('sym').value.trim();
      if (v) { post('explain', { symbol: v }); statusEl.textContent = 'Loading…'; outputEl.innerHTML = ''; }
    });
    document.getElementById('sym').addEventListener('keydown', e => {
      if (e.key === 'Enter') document.getElementById('explain-btn').click();
    });
    document.getElementById('cg-btn').addEventListener('click', () => {
      const v = document.getElementById('cg-sym').value.trim();
      if (v) { post('callgraph', { symbol: v }); statusEl.textContent = 'Loading…'; outputEl.innerHTML = ''; }
    });
    document.getElementById('cg-sym').addEventListener('keydown', e => {
      if (e.key === 'Enter') document.getElementById('cg-btn').click();
    });    document.getElementById('ref-btn').addEventListener('click', () => {
      const v = document.getElementById('ref-sym').value.trim();
      if (v) { post('references', { symbol: v }); statusEl.textContent = 'Finding references\u2026'; outputEl.innerHTML = ''; }
    });
    document.getElementById('ref-sym').addEventListener('keydown', e => {
      if (e.key === 'Enter') document.getElementById('ref-btn').click();
    });    document.getElementById('deps-btn').addEventListener('click', () => {
      post('deps', {}); statusEl.textContent = 'Loading…'; outputEl.innerHTML = '';
    });

    window.addEventListener('message', e => {
      const msg = e.data;
      statusEl.textContent = '';
      if (msg.type === 'explain-result') {
        const d = msg.data.result_payload || msg.data;
        outputEl.innerHTML = '<pre>' + escapeHtml(JSON.stringify(d, null, 2)) + '</pre>';
      } else if (msg.type === 'callgraph-result') {
        const d = msg.data.result_payload || msg.data;
        outputEl.innerHTML = '<pre>' + escapeHtml(JSON.stringify(d, null, 2)) + '</pre>';
      } else if (msg.type === 'deps-result') {
        const d = msg.data.result_payload || msg.data;
        const deps = d.data?.dependencies || d.dependencies || {};
        let html = '';
        for (const [file, imports] of Object.entries(deps)) {
          html += '<div class="section-title">' + escapeHtml(shortPath(String(file))) + '</div>';
          const arr = Array.isArray(imports) ? imports : [];
          arr.forEach(imp => {
            const text = typeof imp === 'string' ? imp : (imp.import_text || JSON.stringify(imp));
            html += '<div class="card"><div class="card-meta">' + escapeHtml(String(text)) + '</div></div>';
          });
        }
        outputEl.innerHTML = html || '<div class="empty">No dependencies found.</div>';
      } else if (msg.type === 'references-result') {
        const d = msg.data.result_payload || msg.data;
        const refs = d.data?.references || d.references || [];
        if (!refs.length) { outputEl.innerHTML = '<div class="empty">No references found.</div>'; return; }
        let html = '<div class="section-title fade-in">References (' + refs.length + ')</div>';
        refs.forEach(r => {
          html += '<div class="card fade-in" data-file="' + escapeHtml(r.file_path || '') + '" data-line="' + (r.start_line || 1) + '">'
            + '<div class="card-title">' + escapeHtml(r.name || r.referencing_symbol || 'ref')
            + ' <span class="badge badge-blue">' + escapeHtml(r.kind || '') + '</span></div>'
            + '<div class="card-meta">' + escapeHtml(shortPath(r.file_path || '')) + ':' + (r.start_line || '?') + '</div></div>';
        });
        outputEl.innerHTML = html;
      } else if (msg.type === 'error') {
        outputEl.innerHTML = '<div class="empty" style="color:var(--vscode-errorForeground)">' + escapeHtml(msg.message) + '</div>';
      }
    });

    // Click-to-open on cards
    outputEl.addEventListener('click', e => {
      const c = e.target.closest('.card');
      if (c && c.dataset.file) post('open', { filePath: c.dataset.file, line: +c.dataset.line });
    });
  </script></body></html>`;
  }
}

// ══════════════════════════════════════════════════════════════════════
// PANEL 3: QUALITY (code quality, metrics, hotspots)
// ══════════════════════════════════════════════════════════════════════
class QualityViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = "codexaQualityView";
  constructor(private readonly _extensionUri: vscode.Uri) {}

  resolveWebviewView(wv: vscode.WebviewView): void {
    wv.webview.options = { enableScripts: true };
    wv.webview.html = this._html();
    wv.webview.onDidReceiveMessage(async (msg) => {
      if (msg.type === "quality") {
        try {
          setStatus("Analyzing quality…", 0);
          const raw = await runCodex(["quality", "--json"]);
          wv.webview.postMessage({ type: "quality-result", data: extractJson(raw) });
          setStatus("Quality done");
        } catch (err: any) {
          wv.webview.postMessage({ type: "error", message: err.message });
        }
      } else if (msg.type === "metrics") {
        try {
          setStatus("Computing metrics…", 0);
          const raw = await runCodex(["metrics", "--json"]);
          wv.webview.postMessage({ type: "metrics-result", data: extractJson(raw) });
          setStatus("Metrics done");
        } catch (err: any) {
          wv.webview.postMessage({ type: "error", message: err.message });
        }
      } else if (msg.type === "hotspots") {
        try {
          setStatus("Finding hotspots…", 0);
          const raw = await runCodex(["hotspots", "--json"]);
          wv.webview.postMessage({ type: "hotspots-result", data: extractJson(raw) });
          setStatus("Hotspots done");
        } catch (err: any) {
          wv.webview.postMessage({ type: "error", message: err.message });
        }
      } else if (msg.type === "open") {
        await openFileAtLine(msg.filePath, msg.line || 1);
      }
    });
  }

  private _html(): string {
    return /* html */ `<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>${SHARED_CSS}
  .stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin: 8px 0; }
  .stat-card { padding: 8px; border-radius: var(--radius);
               background: var(--vscode-textCodeBlock-background); text-align: center; }
  .stat-value { font-size: 18px; font-weight: 700; }
  .stat-label { font-size: 10px; color: var(--vscode-descriptionForeground); text-transform: uppercase; }
</style></head><body>
  <div class="row">
    <button id="quality-btn" style="flex:1">Quality</button>
    <button id="metrics-btn" class="secondary" style="flex:1">Metrics</button>
    <button id="hotspots-btn" class="secondary" style="flex:1">Hotspots</button>
  </div>
  <div id="status" class="status"></div>
  <div id="output"></div>
  <script>${SHARED_JS}
    const outputEl = document.getElementById('output');
    const statusEl = document.getElementById('status');

    document.getElementById('quality-btn').addEventListener('click', () => {
      post('quality', {}); statusEl.textContent = 'Analyzing…'; outputEl.innerHTML = '';
    });
    document.getElementById('metrics-btn').addEventListener('click', () => {
      post('metrics', {}); statusEl.textContent = 'Computing…'; outputEl.innerHTML = '';
    });
    document.getElementById('hotspots-btn').addEventListener('click', () => {
      post('hotspots', {}); statusEl.textContent = 'Scanning…'; outputEl.innerHTML = '';
    });

    window.addEventListener('message', e => {
      const msg = e.data;
      statusEl.textContent = '';
      if (msg.type === 'quality-result') {
        const d = msg.data;
        let html = '<div class="stat-grid">'
          + stat(d.files_analyzed || 0, 'Files')
          + stat(d.symbol_count || 0, 'Symbols')
          + stat(d.issue_count || 0, 'Issues')
          + stat((d.complexity_issues || []).length, 'Complex')
          + '</div>';
        const issues = d.complexity_issues || [];
        if (issues.length) {
          html += '<div class="section-title">High Complexity</div>';
          issues.slice(0, 15).forEach(i => {
            const badge = i.complexity > 20 ? 'badge-red' : i.complexity > 10 ? 'badge-yellow' : 'badge-green';
            html += '<div class="card" data-file="' + escapeHtml(i.file_path) + '" data-line="' + i.start_line + '">'
              + '<div class="card-title">' + escapeHtml(i.symbol_name) + ' <span class="badge ' + badge + '">' + i.complexity + '</span></div>'
              + '<div class="card-meta">' + escapeHtml(shortPath(i.file_path)) + ':' + i.start_line + '</div></div>';
          });
        }
        outputEl.innerHTML = html;
      } else if (msg.type === 'metrics-result') {
        const d = msg.data;
        outputEl.innerHTML = '<div class="stat-grid">'
          + stat(d.total_loc || 0, 'Lines of Code')
          + stat(d.total_symbols || 0, 'Symbols')
          + stat((d.avg_complexity || 0).toFixed(1), 'Avg Complexity')
          + stat(d.max_complexity || 0, 'Max Complexity')
          + stat(d.files_analyzed || 0, 'Files')
          + stat((d.maintainability_index || 0).toFixed(1), 'Maintainability')
          + stat((d.comment_ratio || 0).toFixed(3), 'Comment Ratio')
          + stat(d.total_comment_lines || 0, 'Comment Lines')
          + '</div>';
      } else if (msg.type === 'hotspots-result') {
        const d = msg.data;
        const spots = d.hotspots || [];
        let html = '<div class="stat-grid">'
          + stat(d.files_analyzed || 0, 'Files')
          + stat(spots.length, 'Hotspots')
          + '</div>';
        if (spots.length) {
          html += '<div class="section-title">Risk Hotspots</div>';
          spots.forEach(h => {
            const badge = h.risk_score > 20 ? 'badge-red' : h.risk_score > 10 ? 'badge-yellow' : 'badge-green';
            html += '<div class="card" data-file="' + escapeHtml(h.file_path || '') + '" data-line="1">'
              + '<div class="card-title">' + escapeHtml(h.name) + ' <span class="badge ' + badge + '">risk ' + (h.risk_score || 0).toFixed(1) + '</span></div>'
              + '<div class="card-meta">' + escapeHtml(shortPath(h.file_path || '')) + '</div></div>';
          });
        }
        outputEl.innerHTML = html || '<div class="empty">No hotspots.</div>';
      } else if (msg.type === 'error') {
        outputEl.innerHTML = '<div class="empty" style="color:var(--vscode-errorForeground)">' + escapeHtml(msg.message) + '</div>';
      }
    });

    // Click-to-open on cards
    outputEl.addEventListener('click', e => {
      const c = e.target.closest('.card');
      if (c && c.dataset.file) post('open', { filePath: c.dataset.file, line: +c.dataset.line });
    });

    function stat(value, label) {
      return '<div class="stat-card"><div class="stat-value">' + escapeHtml(String(value)) + '</div>'
        + '<div class="stat-label">' + escapeHtml(label) + '</div></div>';
    }
  </script></body></html>`;
  }
}

// ══════════════════════════════════════════════════════════════════════
// PANEL 4: TOOLS (AI agent tool runner + doctor + impact)
// ══════════════════════════════════════════════════════════════════════
class ToolsViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = "codexaToolsView";
  constructor(private readonly _extensionUri: vscode.Uri) {}

  resolveWebviewView(wv: vscode.WebviewView): void {
    wv.webview.options = { enableScripts: true };
    wv.webview.html = this._html();
    wv.webview.onDidReceiveMessage(async (msg) => {
      if (msg.type === "doctor") {
        try {
          const raw = await runCodex(["doctor"]);
          wv.webview.postMessage({ type: "doctor-result", data: raw });
        } catch (err: any) {
          wv.webview.postMessage({ type: "error", message: err.message });
        }
      } else if (msg.type === "tool-list") {
        try {
          const raw = await runCodex(["tool", "list", "--json"]);
          wv.webview.postMessage({ type: "tool-list-result", data: extractJson(raw) });
        } catch (err: any) {
          wv.webview.postMessage({ type: "error", message: err.message });
        }
      } else if (msg.type === "tool-run") {
        try {
          setStatus(`Running ${msg.tool}…`, 0);
          const args = ["tool", "run", msg.tool];
          if (msg.args) {
            for (const [k, v] of Object.entries(msg.args)) {
              args.push("--arg", `${k}=${v}`);
            }
          }
          args.push("--json");
          const raw = await runCodex(args);
          wv.webview.postMessage({ type: "tool-run-result", data: extractJson(raw) });
          setStatus("Done");
        } catch (err: any) {
          wv.webview.postMessage({ type: "error", message: err.message });
        }
      } else if (msg.type === "models") {
        try {
          const raw = await runCodex(["models", "list", "--json"]);
          wv.webview.postMessage({ type: "models-result", data: extractJson(raw) });
        } catch (err: any) {
          wv.webview.postMessage({ type: "error", message: err.message });
        }
      } else if (msg.type === "index") {
        try {
          setStatus("Indexing…", 0);
          const raw = await runCodex(["index"]);
          wv.webview.postMessage({ type: "index-result", data: raw });
          setStatus("Index complete");
        } catch (err: any) {
          wv.webview.postMessage({ type: "error", message: err.message });
        }
      } else if (msg.type === "impact") {
        try {
          setStatus("Analyzing impact…", 0);
          const raw = await runCodex(["impact", "--json"]);
          wv.webview.postMessage({ type: "impact-result", data: extractJson(raw) });
          setStatus("Impact done");
        } catch (err: any) {
          wv.webview.postMessage({ type: "error", message: err.message });
        }
      } else if (msg.type === "summary") {
        try {
          setStatus("Summarizing…", 0);
          const raw = await runCodex(["tool", "run", "summarize_repo", "--json"]);
          wv.webview.postMessage({ type: "summary-result", data: extractJson(raw) });
          setStatus("Summary done");
        } catch (err: any) {
          wv.webview.postMessage({ type: "error", message: err.message });
        }
      }
    });
  }

  private _html(): string {
    return /* html */ `<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>${SHARED_CSS}
  .btn-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 4px; margin-bottom: 8px; }
  .btn-grid button { font-size: 11px; padding: 6px; }
  .tool-form { margin: 8px 0; }
  .tool-form > label { font-size: 11px; font-weight: 600; display: block; margin: 4px 0 2px; }
  #param-fields .param-group { margin-bottom: 6px; }
  #param-fields input { margin-top: 2px; }
</style></head><body>
  <div class="section-title">Quick Actions</div>
  <div class="btn-grid">
    <button id="doctor-btn">Doctor</button>
    <button id="index-btn">Re-Index</button>
    <button id="models-btn">Models</button>
    <button id="tools-btn">List Tools</button>
    <button id="impact-btn">Impact</button>
    <button id="summary-btn">Summary</button>
  </div>
  <hr class="separator">
  <div class="section-title">Run Tool</div>
  <div class="tool-form">
    <label>Tool</label>
    <select id="tool-select">
      <option value="semantic_search">semantic_search</option>
      <option value="explain_symbol">explain_symbol</option>
      <option value="explain_file">explain_file</option>
      <option value="get_dependencies">get_dependencies</option>
      <option value="get_call_graph">get_call_graph</option>
      <option value="get_context">get_context</option>
      <option value="find_references">find_references</option>
      <option value="summarize_repo">summarize_repo</option>
    </select>
    <div id="tool-desc" class="tool-desc"></div>
    <div id="param-fields"></div>
    <button id="run-tool-btn" style="width:100%; margin-top:6px">Run Tool</button>
  </div>
  <div id="status" class="status"></div>
  <div id="output" style="max-height:400px; overflow:auto;"></div>
  <script>${SHARED_JS}
    const outputEl = document.getElementById('output');
    const statusEl = document.getElementById('status');

    const SCHEMAS = {
      semantic_search: { desc: 'Search the codebase using natural language.', params: [
        {name:'query', type:'string', required:true, desc:'Search query'},
        {name:'top_k', type:'integer', required:false, def:'10', desc:'Max results'},
        {name:'threshold', type:'float', required:false, def:'0.3', desc:'Min similarity'},
      ]},
      explain_symbol: { desc: 'Explain a code symbol (function, class, method).', params: [
        {name:'symbol_name', type:'string', required:true, desc:'Symbol name'},
        {name:'file_path', type:'string', required:false, desc:'File containing the symbol'},
      ]},
      explain_file: { desc: 'Explain all symbols in a source file.', params: [
        {name:'file_path', type:'string', required:true, desc:'Path to the source file'},
      ]},
      get_dependencies: { desc: 'Get the import map for a file.', params: [
        {name:'file_path', type:'string', required:true, desc:'Source file path'},
      ]},
      get_call_graph: { desc: 'Get callers and callees for a symbol.', params: [
        {name:'symbol_name', type:'string', required:true, desc:'Symbol to analyze'},
      ]},
      get_context: { desc: 'Build a rich context window around a symbol.', params: [
        {name:'symbol_name', type:'string', required:true, desc:'Focal symbol name'},
      ]},
      find_references: { desc: 'Find all references to a symbol.', params: [
        {name:'symbol_name', type:'string', required:true, desc:'Name to search for'},
      ]},
      summarize_repo: { desc: 'Get a structured summary of the entire repo.', params: []},
    };

    function buildParams() {
      const tool = document.getElementById('tool-select').value;
      const schema = SCHEMAS[tool];
      document.getElementById('tool-desc').textContent = schema ? schema.desc : '';
      const el = document.getElementById('param-fields');
      el.innerHTML = '';
      if (!schema) return;
      schema.params.forEach(p => {
        const g = document.createElement('div'); g.className = 'param-group';
        const lbl = document.createElement('div'); lbl.className = 'param-label';
        lbl.innerHTML = escapeHtml(p.name)
          + (p.required ? ' <span class="param-req">*</span>' : '')
          + ' <span style="font-weight:400;color:var(--vscode-descriptionForeground)">(' + p.type + ')</span>';
        g.appendChild(lbl);
        if (p.desc) {
          const d = document.createElement('div'); d.className = 'param-desc'; d.textContent = p.desc; g.appendChild(d);
        }
        const inp = document.createElement('input'); inp.id = 'param-' + p.name;
        inp.placeholder = p.desc || p.name;
        if (p.def !== undefined) inp.value = p.def;
        inp.addEventListener('keydown', e => { if (e.key === 'Enter') document.getElementById('run-tool-btn').click(); });
        g.appendChild(inp);
        el.appendChild(g);
      });
    }
    document.getElementById('tool-select').addEventListener('change', buildParams);
    buildParams();

    document.getElementById('doctor-btn').addEventListener('click', () => {
      post('doctor', {}); statusEl.innerHTML = '<span class="spinner"></span> Running doctor\\u2026'; outputEl.innerHTML = '';
    });
    document.getElementById('index-btn').addEventListener('click', () => {
      post('index', {}); statusEl.innerHTML = '<span class="spinner"></span> Indexing\\u2026'; outputEl.innerHTML = '';
    });
    document.getElementById('models-btn').addEventListener('click', () => {
      post('models', {}); statusEl.innerHTML = '<span class="spinner"></span> Loading\\u2026'; outputEl.innerHTML = '';
    });
    document.getElementById('tools-btn').addEventListener('click', () => {
      post('tool-list', {}); statusEl.innerHTML = '<span class="spinner"></span> Loading\\u2026'; outputEl.innerHTML = '';
    });
    document.getElementById('impact-btn').addEventListener('click', () => {
      post('impact', {}); statusEl.innerHTML = '<span class="spinner"></span> Analyzing impact\\u2026'; outputEl.innerHTML = '';
    });
    document.getElementById('summary-btn').addEventListener('click', () => {
      post('summary', {}); statusEl.innerHTML = '<span class="spinner"></span> Summarizing\\u2026'; outputEl.innerHTML = '';
    });

    document.getElementById('run-tool-btn').addEventListener('click', () => {
      const tool = document.getElementById('tool-select').value;
      const schema = SCHEMAS[tool];
      if (!schema) return;
      const args = {};
      const missing = [];
      schema.params.forEach(p => {
        const inp = document.getElementById('param-' + p.name);
        const val = inp ? inp.value.trim() : '';
        if (val) { args[p.name] = val; }
        else if (p.required) {
          missing.push(p.name);
          if (inp) { inp.style.borderColor = 'var(--vscode-errorForeground)'; setTimeout(() => inp.style.borderColor = '', 2000); }
        }
      });
      if (missing.length) {
        statusEl.innerHTML = '<span class="error-text">Missing required: ' + missing.join(', ') + '</span>';
        return;
      }
      post('tool-run', { tool, args });
      statusEl.innerHTML = '<span class="spinner"></span> Running ' + escapeHtml(tool) + '\\u2026';
      outputEl.innerHTML = '';
    });

    function renderResult(data) {
      const d = data.result_payload || data;
      if (!d) return '<pre class="fade-in">' + escapeHtml(JSON.stringify(data, null, 2)) + '</pre>';
      if (d.data && d.data.explanations) {
        return d.data.explanations.map(e =>
          '<div class="card fade-in"><div class="card-title">' + escapeHtml(e.name || e.symbol_name || '')
          + ' <span class="badge badge-blue">' + escapeHtml(e.kind || '') + '</span></div>'
          + (e.docstring ? '<div class="card-meta">' + escapeHtml(e.docstring) + '</div>' : '')
          + (e.file_path ? '<div class="card-meta">' + escapeHtml(shortPath(e.file_path)) + '</div>' : '')
          + (e.signature ? '<pre>' + escapeHtml(e.signature) + '</pre>' : '') + '</div>'
        ).join('');
      }
      if (d.data && d.data.results) {
        const rr = d.data.results;
        if (!rr.length) return '<div class="empty">No results.</div>';
        return rr.map((r, i) =>
          '<div class="card fade-in"><div class="card-title">#' + (i+1) + ' ' + escapeHtml(shortPath(r.file_path || ''))
          + ' <span class="badge badge-green">' + (r.score||0).toFixed(3) + '</span></div>'
          + '<div class="card-meta">L' + r.start_line + '-' + r.end_line + '</div>'
          + (r.content ? '<pre>' + escapeHtml(r.content.slice(0,300)) + '</pre>' : '') + '</div>'
        ).join('');
      }
      if (d.data && d.data.references) {
        const refs = d.data.references;
        if (!refs.length) return '<div class="empty">No references.</div>';
        return '<div class="section-title fade-in">References (' + refs.length + ')</div>'
          + refs.map(r => '<div class="card fade-in"><div class="card-title">'
          + escapeHtml(r.name || r.referencing_symbol || '') + ' <span class="badge badge-blue">'
          + escapeHtml(r.kind || '') + '</span></div><div class="card-meta">'
          + escapeHtml(shortPath(r.file_path || '')) + ':' + (r.start_line||'?') + '</div></div>').join('');
      }
      if (d.data && d.data.callers !== undefined) {
        let h = '';
        if (d.data.callers.length) {
          h += '<div class="section-title fade-in">Callers (' + d.data.callers.length + ')</div>';
          d.data.callers.forEach(c => { h += '<div class="card fade-in"><div class="card-title">' + escapeHtml(c.caller || JSON.stringify(c)) + '</div></div>'; });
        }
        if (d.data.callees && d.data.callees.length) {
          h += '<div class="section-title fade-in">Callees (' + d.data.callees.length + ')</div>';
          d.data.callees.forEach(c => { h += '<div class="card fade-in"><div class="card-title">' + escapeHtml(c.callee || JSON.stringify(c)) + '</div></div>'; });
        }
        return h || '<div class="empty">No call graph data.</div>';
      }
      if (d.data && d.data.dependencies) {
        let h = '';
        for (const [file, imports] of Object.entries(d.data.dependencies)) {
          h += '<div class="section-title">' + escapeHtml(shortPath(String(file))) + '</div>';
          const arr = Array.isArray(imports) ? imports : [];
          arr.forEach(imp => {
            const t = typeof imp === 'string' ? imp : (imp.import_text || JSON.stringify(imp));
            h += '<div class="card fade-in"><div class="card-meta">' + escapeHtml(String(t)) + '</div></div>';
          });
        }
        return h || '<div class="empty">No dependencies.</div>';
      }
      if (d.data && d.data.symbols) {
        return d.data.symbols.map(s =>
          '<div class="card fade-in"><div class="card-title">' + escapeHtml(s.name || '')
          + ' <span class="badge badge-blue">' + escapeHtml(s.kind || '') + '</span></div>'
          + (s.docstring ? '<div class="card-meta">' + escapeHtml(s.docstring) + '</div>' : '')
          + (s.signature ? '<pre>' + escapeHtml(s.signature) + '</pre>' : '') + '</div>'
        ).join('');
      }
      if (d.data && d.data.contexts) {
        return d.data.contexts.map(c =>
          '<div class="card fade-in"><div class="card-title">' + escapeHtml(c.symbol_name || c.name || 'Context') + '</div>'
          + (c.file_path ? '<div class="card-meta">' + escapeHtml(shortPath(c.file_path)) + '</div>' : '')
          + (c.body || c.source ? '<pre>' + escapeHtml((c.body||c.source||'').slice(0,500)) + '</pre>' : '') + '</div>'
        ).join('');
      }
      return '<pre class="fade-in">' + escapeHtml(JSON.stringify(d, null, 2)) + '</pre>';
    }

    window.addEventListener('message', e => {
      const msg = e.data;
      statusEl.textContent = '';
      if (msg.type === 'doctor-result' || msg.type === 'index-result') {
        outputEl.innerHTML = '<pre class="fade-in">' + escapeHtml(msg.data) + '</pre>';
      } else if (msg.type === 'models-result') {
        const models = Array.isArray(msg.data) ? msg.data : [];
        outputEl.innerHTML = models.map(m =>
          '<div class="card fade-in"><div class="card-title">' + escapeHtml(m.display_name || m.name)
          + (m.is_default ? ' <span class="badge badge-green">default</span>' : '')
          + '</div><div class="card-meta">' + m.dimension + 'd &middot; ' + escapeHtml(m.description || '') + '</div></div>'
        ).join('') || '<div class="empty">No models found.</div>';
      } else if (msg.type === 'tool-list-result') {
        const tools = msg.data.tools || [];
        outputEl.innerHTML = tools.map(t =>
          '<div class="card fade-in"><div class="card-title">' + escapeHtml(t.name)
          + ' <span class="badge badge-blue">' + escapeHtml(t.source || 'built-in') + '</span></div>'
          + '<div class="card-meta">' + escapeHtml(t.description || '') + '</div></div>'
        ).join('') || '<div class="empty">No tools.</div>';
      } else if (msg.type === 'tool-run-result') {
        const d = msg.data;
        if (d && d.success === false) {
          const err = d.error || {};
          outputEl.innerHTML = '<div class="card fade-in" style="border-color:var(--vscode-errorForeground)">'
            + '<div class="card-title error-text">' + escapeHtml(err.error_code || 'Error') + '</div>'
            + '<div class="card-meta">' + escapeHtml(err.error_message || 'Unknown error') + '</div></div>';
        } else {
          outputEl.innerHTML = renderResult(d);
        }
      } else if (msg.type === 'impact-result' || msg.type === 'summary-result') {
        outputEl.innerHTML = '<pre class="fade-in">' + escapeHtml(JSON.stringify(msg.data, null, 2)) + '</pre>';
      } else if (msg.type === 'error') {
        outputEl.innerHTML = '<div class="card fade-in" style="border-color:var(--vscode-errorForeground)">'
          + '<div class="error-text">' + escapeHtml(msg.message) + '</div></div>';
      }
    });
  </script></body></html>`;
  }
}

// ══════════════════════════════════════════════════════════════════════
// Decorations: inline complexity badges
// ══════════════════════════════════════════════════════════════════════
const highComplexityDecoration = vscode.window.createTextEditorDecorationType({
  after: { margin: "0 0 0 1em", color: "#f85149", fontStyle: "italic", fontWeight: "bold" },
});

// ══════════════════════════════════════════════════════════════════════
// Extension activation
// ══════════════════════════════════════════════════════════════════════
export function activate(context: vscode.ExtensionContext): void {
  outputChannel = vscode.window.createOutputChannel("CodexA");
  statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 50);
  statusBarItem.command = "codexa.search";
  context.subscriptions.push(outputChannel, statusBarItem);

  // ── Sidebar panels ────────────────────────────────────────────────
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(SearchViewProvider.viewType, new SearchViewProvider(context.extensionUri)),
    vscode.window.registerWebviewViewProvider(SymbolsViewProvider.viewType, new SymbolsViewProvider(context.extensionUri)),
    vscode.window.registerWebviewViewProvider(QualityViewProvider.viewType, new QualityViewProvider(context.extensionUri)),
    vscode.window.registerWebviewViewProvider(ToolsViewProvider.viewType, new ToolsViewProvider(context.extensionUri)),
  );

  // ── Command: search (input box → JSON doc) ────────────────────────
  context.subscriptions.push(
    vscode.commands.registerCommand("codexa.search", async () => {
      const query = await vscode.window.showInputBox({ prompt: "CodexA: Enter search query" });
      if (!query) { return; }
      try {
        setStatus("Searching…", 0);
        const root = workspaceRoot();
        const raw = await runCodex(["search", query, "-p", root, "--json"]);
        const data = extractJson(raw);
        const doc = await vscode.workspace.openTextDocument({
          content: JSON.stringify(data, null, 2), language: "json",
        });
        await vscode.window.showTextDocument(doc);
        setStatus(`${(data.results || []).length} results`);
      } catch (err: any) {
        vscode.window.showErrorMessage(`CodexA search failed: ${err.message}`);
        setStatus("Search failed");
      }
    })
  );

  // ── Command: ask ───────────────────────────────────────────────────
  context.subscriptions.push(
    vscode.commands.registerCommand("codexa.askCodexA", async () => {
      const question = await vscode.window.showInputBox({ prompt: "Ask CodexA a question" });
      if (!question) { return; }
      try {
        setStatus("Thinking…", 0);
        const root = workspaceRoot();
        const raw = await runCodex(["ask", question, "-p", root]);
        const doc = await vscode.workspace.openTextDocument({ content: raw, language: "markdown" });
        await vscode.window.showTextDocument(doc);
        setStatus("Done");
      } catch (err: any) {
        vscode.window.showErrorMessage(`CodexA ask failed: ${err.message}`);
      }
    })
  );

  // ── Command: call graph ────────────────────────────────────────────
  context.subscriptions.push(
    vscode.commands.registerCommand("codexa.callGraph", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) { return; }
      const range = editor.document.getWordRangeAtPosition(editor.selection.active);
      const word = range ? editor.document.getText(range) : "";
      if (!word) { return; }
      try {
        setStatus(`Call graph: ${word}`, 0);
        const raw = await runCodex(["tool", "run", "get_call_graph", "--arg", `symbol_name=${word}`, "--json"]);
        const data = extractJson(raw);
        const doc = await vscode.workspace.openTextDocument({
          content: JSON.stringify(data, null, 2), language: "json",
        });
        await vscode.window.showTextDocument(doc);
        setStatus("Done");
      } catch (err: any) {
        vscode.window.showErrorMessage(`CodexA call graph failed: ${err.message}`);
      }
    })
  );

  // ── Command: models ────────────────────────────────────────────────
  context.subscriptions.push(
    vscode.commands.registerCommand("codexa.models", async () => {
      try {
        const raw = await runCodex(["models", "list", "--json"]);
        const data = extractJson(raw);
        const items = (Array.isArray(data) ? data : []).map((m: any) => ({
          label: m.display_name || m.name,
          description: `${m.dimension}d — ${m.description || ""}`,
          detail: m.is_default ? "$(star) Default model" : undefined,
        }));
        await vscode.window.showQuickPick(items, { title: "CodexA Embedding Models" });
      } catch (err: any) {
        vscode.window.showErrorMessage(`CodexA models failed: ${err.message}`);
      }
    })
  );

  // ── Command: quality ───────────────────────────────────────────────
  context.subscriptions.push(
    vscode.commands.registerCommand("codexa.quality", async () => {
      try {
        setStatus("Analyzing quality…", 0);
        const raw = await runCodex(["quality", "--json"]);
        const data = extractJson(raw);
        const doc = await vscode.workspace.openTextDocument({
          content: JSON.stringify(data, null, 2), language: "json",
        });
        await vscode.window.showTextDocument(doc);
        setStatus(`${data.issue_count || 0} issues`);
      } catch (err: any) {
        vscode.window.showErrorMessage(`CodexA quality failed: ${err.message}`);
      }
    })
  );

  // ── Command: explain symbol at cursor ──────────────────────────────
  context.subscriptions.push(
    vscode.commands.registerCommand("codexa.explainSymbol", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) { return; }
      const range = editor.document.getWordRangeAtPosition(editor.selection.active);
      const word = range ? editor.document.getText(range) : "";
      if (!word) { return; }
      try {
        setStatus(`Explaining ${word}…`, 0);
        const raw = await runCodex(["tool", "run", "explain_symbol", "--arg", `symbol_name=${word}`, "--json"]);
        const data = extractJson(raw);
        const doc = await vscode.workspace.openTextDocument({
          content: JSON.stringify(data, null, 2), language: "json",
        });
        await vscode.window.showTextDocument(doc);
        setStatus("Done");
      } catch (err: any) {
        vscode.window.showErrorMessage(`CodexA explain failed: ${err.message}`);
      }
    })
  );

  // ── Command: doctor ────────────────────────────────────────────────
  context.subscriptions.push(
    vscode.commands.registerCommand("codexa.doctor", async () => {
      try {
        const raw = await runCodex(["doctor"]);
        outputChannel.appendLine(raw);
        outputChannel.show();
        vscode.window.showInformationMessage("CodexA doctor results shown in Output panel.");
      } catch (err: any) {
        vscode.window.showErrorMessage(`CodexA doctor failed: ${err.message}`);
      }
    })
  );

  // ── Command: index ─────────────────────────────────────────────────
  context.subscriptions.push(
    vscode.commands.registerCommand("codexa.index", async () => {
      try {
        setStatus("Indexing codebase…", 0);
        const raw = await runCodex(["index"]);
        outputChannel.appendLine(raw);
        outputChannel.show();
        setStatus("Index complete");
        vscode.window.showInformationMessage("CodexA indexing complete.");
      } catch (err: any) {
        vscode.window.showErrorMessage(`CodexA index failed: ${err.message}`);
      }
    })
  );

  // ── Codelens provider for complexity hints ─────────────────────────
  context.subscriptions.push(
    vscode.languages.registerCodeLensProvider(
      { scheme: "file", language: "python" },
      new CodexACodeLensProvider()
    )
  );

  // ── Status bar ─────────────────────────────────────────────────────
  statusBarItem.text = "$(telescope) CodexA";
  statusBarItem.tooltip = "Click to search with CodexA";
  statusBarItem.show();

  outputChannel.appendLine(`CodexA extension activated — binary: ${codexBin()}`);
}

// ── CodeLens provider ────────────────────────────────────────────────
class CodexACodeLensProvider implements vscode.CodeLensProvider {
  provideCodeLenses(document: vscode.TextDocument): vscode.CodeLens[] {
    const lenses: vscode.CodeLens[] = [];
    const text = document.getText();
    const defRegex = /^(def|class|async def)\s+(\w+)/gm;
    let match: RegExpExecArray | null;
    while ((match = defRegex.exec(text)) !== null) {
      const line = document.positionAt(match.index).line;
      const range = new vscode.Range(line, 0, line, 0);
      lenses.push(new vscode.CodeLens(range, {
        title: "$(telescope) Explain",
        command: "codexa.explainSymbol",
      }));
    }
    return lenses;
  }
}

export function deactivate(): void {
  statusBarItem?.dispose();
  outputChannel?.dispose();
}
