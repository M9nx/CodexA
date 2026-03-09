"""Lightweight server-rendered web UI for CodexA.

Serves a minimal HTML interface using only the Python standard library.
The UI uses inline CSS and vanilla JavaScript — no build step, no npm,
no framework dependencies.

Pages:
    /           → dashboard / search page
    /symbols    → symbol browser
    /workspace  → workspace repo viewer
    /viz        → visualization viewer (call graph, deps)

The UI pages call the JSON API endpoints (``/api/...``) via ``fetch()``.
"""

from __future__ import annotations

import html
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

from semantic_code_intelligence.utils.logging import get_logger
from semantic_code_intelligence.web.visualize import (
    render_call_graph,
    render_dependency_graph,
    render_symbol_map,
)

logger = get_logger("web.ui")


# ------------------------------------------------------------------
# HTML templates (inline — no external files needed)
# ------------------------------------------------------------------

_CSS = """\
:root { --bg: #0d1117; --surface: #161b22; --border: #30363d;
        --text: #e6edf3; --dim: #8b949e; --accent: #58a6ff;
        --green: #56d364; --red: #f85149; --yellow: #e3b341; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
       background: var(--bg); color: var(--text); line-height: 1.6; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
nav { background: var(--surface); border-bottom: 1px solid var(--border);
      padding: 0.75rem 1.5rem; display: flex; align-items: center; gap: 2rem; }
nav .logo { font-weight: 700; font-size: 1.1rem; }
nav .links { display: flex; gap: 1rem; }
.container { max-width: 960px; margin: 2rem auto; padding: 0 1rem; }
h1 { font-size: 1.5rem; margin-bottom: 1rem; }
.search-box { display: flex; gap: 0.5rem; margin-bottom: 1.5rem; }
.search-box input { flex: 1; padding: 0.6rem 1rem; background: var(--surface);
    border: 1px solid var(--border); border-radius: 6px; color: var(--text);
    font-size: 0.95rem; }
.search-box input:focus { outline: none; border-color: var(--accent); }
.search-box button { padding: 0.6rem 1.2rem; background: var(--accent); color: #fff;
    border: none; border-radius: 6px; cursor: pointer; font-weight: 600; }
.search-box button:hover { opacity: 0.9; }
.card { background: var(--surface); border: 1px solid var(--border);
        border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }
.card h3 { font-size: 0.95rem; margin-bottom: 0.5rem; }
.card .meta { color: var(--dim); font-size: 0.8rem; margin-bottom: 0.5rem; }
pre { background: #0d1117; border: 1px solid var(--border); border-radius: 6px;
      padding: 0.75rem; overflow-x: auto; font-size: 0.85rem; line-height: 1.5; }
code { font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace; }
.badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 12px;
         font-size: 0.75rem; font-weight: 600; }
.badge-fn { background: #1f3a5f; color: var(--accent); }
.badge-cls { background: #2d1f3f; color: #d2a8ff; }
.badge-method { background: #1f3f2f; color: var(--green); }
.badge-import { background: #3f2f1f; color: var(--yellow); }
.score { color: var(--green); font-weight: 600; }
.mermaid { background: var(--surface); border: 1px solid var(--border);
           border-radius: 8px; padding: 1rem; text-align: center; }
table { width: 100%; border-collapse: collapse; margin-bottom: 1rem; }
th, td { text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border); }
th { color: var(--dim); font-weight: 600; font-size: 0.85rem; }
.status-ok { color: var(--green); }
.status-err { color: var(--red); }
#loading { color: var(--dim); display: none; }
.empty { color: var(--dim); text-align: center; padding: 2rem; }
"""

_NAV = """\
<nav>
  <span class="logo">&#9883; CodexA</span>
  <div class="links">
    <a href="/">Search</a>
    <a href="/symbols">Symbols</a>
    <a href="/tools">Tools</a>
    <a href="/quality">Quality</a>
    <a href="/ask">Ask</a>
    <a href="/workspace">Workspace</a>
    <a href="/viz">Visualize</a>
  </div>
</nav>
"""


def _page(title: str, body: str, script: str = "", *, mermaid: bool = False) -> str:
    """Wrap content in a full HTML page."""
    mermaid_tag = (
        '<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>\n'
        '<script>mermaid.initialize({startOnLoad:false, theme:"dark"});</script>'
        if mermaid else ""
    )
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} — CodexA</title>
<style>{_CSS}</style>
{mermaid_tag}
</head>
<body>
{_NAV}
<div class="container">
{body}
</div>
<script>{script}</script>
</body>
</html>"""


# ------------------------------------------------------------------
# Page builders
# ------------------------------------------------------------------

def page_search() -> str:
    """Search page with live results."""
    body = """\
<h1>Semantic Code Search</h1>
<div class="search-box">
  <input type="text" id="q" placeholder="Search your codebase..." autofocus>
  <button onclick="doSearch()">Search</button>
</div>
<div id="loading">Searching...</div>
<div id="results"></div>
"""
    script = """\
document.getElementById('q').addEventListener('keydown', e => {
  if (e.key === 'Enter') doSearch();
});
async function doSearch() {
  const q = document.getElementById('q').value.trim();
  if (!q) return;
  document.getElementById('loading').style.display = 'block';
  document.getElementById('results').innerHTML = '';
  try {
    const res = await fetch('/api/search?q=' + encodeURIComponent(q) + '&top_k=10');
    const data = await res.json();
    document.getElementById('loading').style.display = 'none';
    const snippets = data.snippets || [];
    if (!snippets.length) {
      document.getElementById('results').innerHTML = '<div class="empty">No results found.</div>';
      return;
    }
    let html = '';
    snippets.forEach((s, i) => {
      const esc = s => (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
      html += '<div class="card">' +
        '<h3>#' + (i+1) + ' ' + esc(s.file_path) + '</h3>' +
        '<div class="meta">Lines ' + s.start_line + '-' + s.end_line +
        ' &middot; <span class="score">score: ' + (s.score||0).toFixed(4) + '</span></div>' +
        '<pre><code>' + esc(s.content) + '</code></pre></div>';
    });
    document.getElementById('results').innerHTML = html;
  } catch (err) {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('results').innerHTML = '<div class="card"><p class="status-err">' + err + '</p></div>';
  }
}
"""
    return _page("Search", body, script)


def page_symbols() -> str:
    """Symbol browser page."""
    body = """\
<h1>Symbol Browser</h1>
<div class="search-box">
  <input type="text" id="filter" placeholder="Filter by file or symbol name...">
  <select id="kind">
    <option value="">All kinds</option>
    <option value="function">Functions</option>
    <option value="class">Classes</option>
    <option value="method">Methods</option>
    <option value="import">Imports</option>
  </select>
  <button onclick="loadSymbols()">Load</button>
</div>
<div id="loading">Loading...</div>
<div id="results"></div>
"""
    script = """\
async function loadSymbols() {
  const file = document.getElementById('filter').value.trim();
  const kind = document.getElementById('kind').value;
  document.getElementById('loading').style.display = 'block';
  let url = '/api/symbols?';
  if (file) url += 'file=' + encodeURIComponent(file) + '&';
  if (kind) url += 'kind=' + encodeURIComponent(kind);
  try {
    const res = await fetch(url);
    const data = await res.json();
    document.getElementById('loading').style.display = 'none';
    const syms = data.symbols || [];
    if (!syms.length) {
      document.getElementById('results').innerHTML = '<div class="empty">No symbols found. Make sure the project is indexed.</div>';
      return;
    }
    let html = '<table><tr><th>Name</th><th>Kind</th><th>File</th><th>Lines</th></tr>';
    syms.forEach(s => {
      const esc = t => (t||'').replace(/&/g,'&amp;').replace(/</g,'&lt;');
      const badge = {'function':'badge-fn','class':'badge-cls','method':'badge-method','import':'badge-import'}[s.kind] || '';
      html += '<tr><td><code>' + esc(s.name) + '</code></td>' +
        '<td><span class="badge ' + badge + '">' + esc(s.kind) + '</span></td>' +
        '<td>' + esc(s.file_path) + '</td>' +
        '<td>' + s.start_line + '-' + s.end_line + '</td></tr>';
    });
    html += '</table>';
    if (data.count > syms.length) html += '<div class="empty">Showing ' + syms.length + ' of ' + data.count + ' symbols.</div>';
    document.getElementById('results').innerHTML = html;
  } catch(e) {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('results').innerHTML = '<div class="card status-err">' + e + '</div>';
  }
}
"""
    return _page("Symbols", body, script)


def page_workspace() -> str:
    """Workspace repo browser page."""
    body = """\
<h1>Workspace</h1>
<div id="health"></div>
<div id="summary" style="margin-top:1rem;"></div>
"""
    script = """\
async function load() {
  try {
    const hRes = await fetch('/health');
    const health = await hRes.json();
    document.getElementById('health').innerHTML =
      '<div class="card"><h3>Project Status</h3>' +
      '<table><tr><td>Root</td><td><code>' + (health.project_root||'') + '</code></td></tr>' +
      '<tr><td>Indexed</td><td class="' + (health.indexed?'status-ok':'status-err') + '">' + health.indexed + '</td></tr>' +
      '<tr><td>Config</td><td class="' + (health.config_found?'status-ok':'status-err') + '">' + health.config_found + '</td></tr></table></div>';
  } catch(e) {
    document.getElementById('health').innerHTML = '<div class="card status-err">' + e + '</div>';
  }
  try {
    const sRes = await fetch('/api/summary');
    const summary = await sRes.json();
    const langs = summary.languages || summary.language_breakdown || {};
    let langHtml = '';
    for (const [lang, count] of Object.entries(langs)) {
      langHtml += '<tr><td>' + lang + '</td><td>' + count + '</td></tr>';
    }
    document.getElementById('summary').innerHTML =
      '<div class="card"><h3>Repository Summary</h3>' +
      (langHtml ? '<table><tr><th>Language</th><th>Files</th></tr>' + langHtml + '</table>' : '<p class="empty">No summary available. Index the project first.</p>') +
      '</div>';
  } catch(e) {}
}
load();
"""
    return _page("Workspace", body, script)


def page_viz() -> str:
    """Visualization page with Mermaid rendering."""
    body = """\
<h1>Visualizations</h1>
<p style="color:var(--dim);margin-bottom:1rem;">
  Generate Mermaid-compatible diagrams from your codebase analysis.
</p>
<div style="display:flex;gap:0.5rem;margin-bottom:1rem;">
  <button onclick="loadViz('callgraph')">Call Graph</button>
  <button onclick="loadViz('deps')">Dependencies</button>
</div>
<div class="search-box">
  <input type="text" id="target" placeholder="Symbol or file name (optional)">
</div>
<div id="diagram"></div>
<div id="mermaid-source" style="margin-top:1rem;"></div>
"""
    script = """\
async function loadViz(kind) {
  const target = document.getElementById('target').value.trim();
  const diagram = document.getElementById('diagram');
  const source = document.getElementById('mermaid-source');
  diagram.innerHTML = '<div class="empty">Loading…</div>';
  source.innerHTML = '';
  try {
    const vizRes = await fetch('/api/viz/' + kind + '?target=' + encodeURIComponent(target));
    const vizData = await vizRes.json();
    if (vizData.error) { diagram.innerHTML = '<div class="card status-err">' + vizData.error + '</div>'; return; }
    const src = vizData.mermaid || '';
    const title = kind === 'callgraph' ? 'Call Graph' : 'Dependencies';
    // Render with Mermaid
    const container = document.createElement('div');
    container.className = 'card';
    const heading = document.createElement('h3');
    heading.textContent = title;
    container.appendChild(heading);
    const mermaidDiv = document.createElement('div');
    mermaidDiv.className = 'mermaid';
    const id = 'mermaid-' + Date.now();
    try {
      const { svg } = await mermaid.render(id, src);
      mermaidDiv.innerHTML = svg;
    } catch(_) {
      mermaidDiv.innerHTML = '<pre>' + src.replace(/&/g,'&amp;').replace(/</g,'&lt;') + '</pre>';
    }
    container.appendChild(mermaidDiv);
    diagram.innerHTML = '';
    diagram.appendChild(container);
    source.innerHTML =
      '<details><summary style="color:var(--dim);cursor:pointer;">Raw Mermaid source</summary>' +
      '<pre><code>' + src.replace(/&/g,'&amp;').replace(/</g,'&lt;') + '</code></pre></details>';
  } catch(e) {
    diagram.innerHTML = '<div class="card status-err">' + e + '</div>';
  }
}
"""
    return _page("Visualize", body, script, mermaid=True)


def page_tools() -> str:
    """Tool runner page — focused quick actions for code exploration."""
    body = """\
<h1>Tools</h1>
<p style="color:var(--dim);margin-bottom:1.5rem;">Quick code exploration — explain symbols, trace call graphs, and inspect dependencies.</p>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1rem;margin-bottom:1.5rem;">
  <div class="card" style="cursor:pointer;" onclick="showTool('explain_symbol')">
    <h3>&#128269; Explain Symbol</h3>
    <div class="meta">Structural explanation of a class, function, or method</div>
  </div>
  <div class="card" style="cursor:pointer;" onclick="showTool('explain_file')">
    <h3>&#128196; Explain File</h3>
    <div class="meta">List and explain all symbols in a source file</div>
  </div>
  <div class="card" style="cursor:pointer;" onclick="showTool('get_call_graph')">
    <h3>&#128300; Call Graph</h3>
    <div class="meta">Show callers and callees for a symbol</div>
  </div>
  <div class="card" style="cursor:pointer;" onclick="showTool('get_dependencies')">
    <h3>&#128279; Dependencies</h3>
    <div class="meta">Import and dependency map for a file</div>
  </div>
</div>
<div id="tool-form" style="display:none;">
  <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.75rem;">
    <span id="tool-title" style="font-weight:600;font-size:1.1rem;"></span>
    <span style="flex:1;"></span>
    <button onclick="hideTool()" style="padding:0.3rem 0.75rem;background:var(--surface);
      border:1px solid var(--border);border-radius:6px;color:var(--dim);cursor:pointer;">Back</button>
  </div>
  <div class="search-box">
    <input type="text" id="tool-input" placeholder="" autofocus>
    <button id="tool-run" onclick="runTool()">Run</button>
  </div>
</div>
<div id="loading">Running...</div>
<div id="results"></div>
"""
    script = """\
const TOOLS = {
  explain_symbol: {title:'Explain Symbol', placeholder:'Symbol name (e.g. MyClass)', arg:'symbol_name'},
  explain_file:   {title:'Explain File',   placeholder:'File path (e.g. src/auth.py)', arg:'file_path'},
  get_call_graph: {title:'Call Graph',      placeholder:'Symbol name (e.g. handle_request)', arg:'symbol_name'},
  get_dependencies:{title:'Dependencies',   placeholder:'File path (e.g. src/main.py)', arg:'file_path'},
};
let currentTool = null;
function showTool(name) {
  currentTool = name;
  const t = TOOLS[name];
  document.getElementById('tool-title').textContent = t.title;
  document.getElementById('tool-input').placeholder = t.placeholder;
  document.getElementById('tool-input').value = '';
  document.getElementById('tool-form').style.display = 'block';
  document.getElementById('results').innerHTML = '';
  document.getElementById('tool-input').focus();
}
function hideTool() {
  document.getElementById('tool-form').style.display = 'none';
  document.getElementById('results').innerHTML = '';
  currentTool = null;
}
document.addEventListener('keydown', e => {
  if (e.key === 'Enter' && currentTool) runTool();
});
async function runTool() {
  if (!currentTool) return;
  const t = TOOLS[currentTool];
  const val = document.getElementById('tool-input').value.trim();
  if (!val) return;
  document.getElementById('loading').style.display = 'block';
  document.getElementById('results').innerHTML = '';
  const args = {}; args[t.arg] = val;
  try {
    const res = await fetch('/api/tools/run', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({tool_name: currentTool, arguments: args}),
    });
    const data = await res.json();
    document.getElementById('loading').style.display = 'none';
    const esc = s => (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    const payload = data.result_payload || data;
    const ok = data.success !== false;
    let html = '';
    if (!ok) {
      const err = data.error || {};
      html = '<div class="card" style="border-color:var(--red);"><p class="status-err">'
        + esc(err.error_message || JSON.stringify(data)) + '</p></div>';
    } else if (currentTool === 'explain_symbol' || currentTool === 'explain_file') {
      const d = payload.data || payload;
      const syms = d.symbols || d.explanations || [];
      if (typeof syms === 'object' && !Array.isArray(syms)) {
        html = '<div class="card"><pre><code>' + esc(JSON.stringify(d, null, 2)) + '</code></pre></div>';
      } else if (Array.isArray(syms)) {
        syms.forEach(s => {
          html += '<div class="card"><h3><span class="badge badge-' + (s.kind||'fn') + '">' + esc(s.kind||'symbol') + '</span> ' + esc(s.name||s.symbol_name||'') + '</h3>'
            + '<div class="meta">' + esc(s.file_path||'') + ' &middot; ' + esc(s.lines||s.summary||'') + '</div></div>';
        });
      }
      if (!html) html = '<div class="card"><pre><code>' + esc(JSON.stringify(d, null, 2)) + '</code></pre></div>';
    } else {
      html = '<div class="card"><pre><code>' + esc(JSON.stringify(payload.data || payload, null, 2)) + '</code></pre></div>';
    }
    document.getElementById('results').innerHTML = html;
  } catch(e) {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('results').innerHTML = '<div class="card"><p class="status-err">' + e + '</p></div>';
  }
}
"""
    return _page("Tools", body, script)


def page_quality() -> str:
    """Quality analysis page — metrics, hotspots, complexity."""
    body = """\
<h1>Code Quality</h1>
<div style="display:flex;gap:0.5rem;margin-bottom:1.5rem;">
  <button onclick="load('quality')" style="padding:0.6rem 1.2rem;background:var(--accent);color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:600;">Quality</button>
  <button onclick="load('metrics')" style="padding:0.6rem 1.2rem;background:var(--surface);color:var(--text);border:1px solid var(--border);border-radius:6px;cursor:pointer;">Metrics</button>
  <button onclick="load('hotspots')" style="padding:0.6rem 1.2rem;background:var(--surface);color:var(--text);border:1px solid var(--border);border-radius:6px;cursor:pointer;">Hotspots</button>
</div>
<div id="loading">Analyzing...</div>
<div id="results"></div>
"""
    script = """\
async function load(kind) {
  document.getElementById('loading').style.display = 'block';
  document.getElementById('results').innerHTML = '';
  try {
    const res = await fetch('/api/' + kind);
    const data = await res.json();
    document.getElementById('loading').style.display = 'none';
    const esc = s => (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    if (kind === 'quality') {
      const issues = data.complexity_issues || [];
      let html = '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.5rem;margin-bottom:1rem;">';
      html += stat(data.files_analyzed || 0, 'Files');
      html += stat(data.symbol_count || 0, 'Symbols');
      html += stat(data.issue_count || 0, 'Issues');
      html += stat(issues.length, 'Complex');
      html += '</div>';
      if (issues.length) {
        html += '<h3>High Complexity</h3>';
        issues.slice(0, 20).forEach(i => {
          const cls = i.complexity > 20 ? 'status-err' : i.complexity > 10 ? '' : 'status-ok';
          html += '<div class="card"><h3>' + esc(i.symbol_name) + ' <span class="' + cls + '">' + i.complexity + '</span></h3>'
            + '<div class="meta">' + esc(i.file_path) + ':' + i.start_line + '</div></div>';
        });
      }
      document.getElementById('results').innerHTML = html;
    } else if (kind === 'metrics') {
      let html = '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.5rem;">';
      html += stat(data.total_loc || 0, 'Lines of Code');
      html += stat(data.total_symbols || 0, 'Symbols');
      html += stat((data.avg_complexity || 0).toFixed(1), 'Avg Complexity');
      html += stat(data.max_complexity || 0, 'Max Complexity');
      html += stat(data.files_analyzed || 0, 'Files');
      html += stat((data.maintainability_index || 0).toFixed(1), 'Maintainability');
      html += stat((data.comment_ratio || 0).toFixed(3), 'Comment Ratio');
      html += stat(data.total_comment_lines || 0, 'Comment Lines');
      html += '</div>';
      document.getElementById('results').innerHTML = html;
    } else if (kind === 'hotspots') {
      const spots = data.hotspots || [];
      let html = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem;margin-bottom:1rem;">';
      html += stat(data.files_analyzed || 0, 'Files');
      html += stat(spots.length, 'Hotspots');
      html += '</div>';
      spots.forEach(h => {
        const cls = h.risk_score > 20 ? 'status-err' : h.risk_score > 10 ? '' : 'status-ok';
        html += '<div class="card"><h3>' + esc(h.name) + ' <span class="badge ' + cls + '">risk ' + (h.risk_score||0).toFixed(1) + '</span></h3>'
          + '<div class="meta">' + esc(h.file_path||'') + '</div></div>';
      });
      document.getElementById('results').innerHTML = html || '<div class="empty">No hotspots found.</div>';
    }
  } catch(e) {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('results').innerHTML = '<div class="card"><p class="status-err">' + e + '</p></div>';
  }
}
function stat(val, label) {
  return '<div class="card" style="text-align:center;padding:1rem;"><div style="font-size:1.5rem;font-weight:700;">' + val + '</div><div style="font-size:0.75rem;color:var(--dim);text-transform:uppercase;">' + label + '</div></div>';
}
"""
    return _page("Quality", body, script)


def page_ask() -> str:
    """AI Q&A page — ask questions about the codebase."""
    body = """\
<h1>Ask CodexA</h1>
<p style="color:var(--dim);margin-bottom:1rem;">Ask a natural-language question and get an AI-generated answer grounded in your codebase.</p>
<div class="search-box">
  <input type="text" id="question" placeholder="How does authentication work?" autofocus>
  <button onclick="doAsk()">Ask</button>
</div>
<div id="loading">Thinking...</div>
<div id="answer"></div>
<div id="context"></div>
"""
    script = """\
document.getElementById('question').addEventListener('keydown', e => {
  if (e.key === 'Enter') doAsk();
});
async function doAsk() {
  const q = document.getElementById('question').value.trim();
  if (!q) return;
  document.getElementById('loading').style.display = 'block';
  document.getElementById('answer').innerHTML = '';
  document.getElementById('context').innerHTML = '';
  try {
    const res = await fetch('/api/ask', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({question: q, top_k: 5}),
    });
    const data = await res.json();
    document.getElementById('loading').style.display = 'none';
    const esc = s => (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    // Render the answer
    const answer = data.answer || 'No answer available.';
    const elapsed = (data.elapsed_ms || 0).toFixed(0);
    document.getElementById('answer').innerHTML = '<div class="card" style="border-color:var(--accent);">'
      + '<h3 style="color:var(--accent);">Answer</h3>'
      + '<div style="white-space:pre-wrap;line-height:1.7;">' + esc(answer) + '</div>'
      + '<div class="meta" style="margin-top:0.75rem;">' + elapsed + 'ms</div></div>';
    // Render context snippets (collapsed)
    const snippets = data.snippets || data.context_snippets || [];
    if (snippets.length) {
      let ctx = '<details style="margin-top:0.5rem;"><summary style="cursor:pointer;color:var(--dim);font-size:0.9rem;">'
        + snippets.length + ' supporting code snippets</summary>';
      snippets.forEach((s, i) => {
        ctx += '<div class="card" style="margin-top:0.5rem;"><h3>#' + (i+1) + ' ' + esc(s.file_path||'') + '</h3>'
          + '<div class="meta">Lines ' + (s.start_line||'?') + '-' + (s.end_line||'?')
          + '</div><pre><code>' + esc(s.content||s.chunk||'') + '</code></pre></div>';
      });
      ctx += '</details>';
      document.getElementById('context').innerHTML = ctx;
    }
  } catch(e) {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('answer').innerHTML = '<div class="card"><p class="status-err">' + e + '</p></div>';
  }
}
"""
    return _page("Ask", body, script)


# ------------------------------------------------------------------
# HTTP handler mixin
# ------------------------------------------------------------------

class UIHandler(BaseHTTPRequestHandler):
    """Serves HTML pages for the CodexA web interface.

    Class-level attributes must be injected before use:
        provider  — a ContextProvider instance
    """

    provider: Any  # ContextProvider — avoids circular import at module level

    def log_message(self, fmt: str, *args: Any) -> None:
        logger.debug(fmt, *args)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = urllib.parse.parse_qs(parsed.query)

        ui_routes: dict[str, str] = {
            "/": page_search(),
            "/symbols": page_symbols(),
            "/tools": page_tools(),
            "/quality": page_quality(),
            "/ask": page_ask(),
            "/workspace": page_workspace(),
            "/viz": page_viz(),
        }

        if path in ui_routes:
            self._html(200, ui_routes[path])
        elif path.startswith("/api/viz/"):
            self._handle_viz_api(path, qs)
        else:
            self._html(404, _page("Not Found", '<div class="empty">Page not found.</div>'))

    def _handle_viz_api(self, path: str, qs: dict[str, list[str]]) -> None:
        """Handle /api/viz/{kind}?target=... — return Mermaid source as JSON."""
        kind = path.replace("/api/viz/", "").strip("/")
        target = (qs.get("target", [""])[0])

        try:
            if kind == "callgraph":
                data = self.provider.get_call_graph(symbol_name=target)
                edges = data.get("edges", [])
                mermaid = render_call_graph(edges)
            elif kind == "deps":
                data = self.provider.get_dependencies(file_path=target)
                mermaid = render_dependency_graph(data)
            else:
                self._json(400, {"error": f"Unknown viz kind: {kind}"})
                return

            self._json(200, {"kind": kind, "mermaid": mermaid})
        except Exception as exc:
            self._json(500, {"error": str(exc)})

    def _html(self, status: int, content: str) -> None:
        payload = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _json(self, status: int, body: dict[str, Any]) -> None:
        payload = json.dumps(body, indent=2, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)
