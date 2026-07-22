# 02 — Functional Inventory (Corrected v2)

**Correction date:** 2026-07-22  
**Changes from v1:**
- Replaced "verified working" with correct terminology: Source-confirmed, Unit-tested, Environment-blocked, etc.
- Explicitly distinguished Python-fallback, Rust-native, VS Code live-host, HTTP/MCP external-client, and mocked LLM-provider behaviour paths
- Removed claims about Rust-native behaviour being "tested" (wheel not installed)

---

## Validation Terminology

| Term | Meaning |
|------|---------|
| **Source-confirmed** | Code path exists and is structured correctly; not executed during this audit |
| **Unit-tested** | pytest unit tests cover the Python-fallback path |
| **Integration-tested** | Multiple components tested together (HTTP, DB, etc.) |
| **Manually smoke-tested** | Manually executed and observed to function |
| **End-to-end validated** | Full user flow from UI/CLI to storage tested |
| **Environment-blocked** | Could not be validated; environment constraint prevented execution |
| **Unverified** | No evidence of correct behaviour |

---

## Feature Inventory

| Feature | Component | Entry Point | Python-Fallback Status | Rust-Native Status | VS Code Status | HTTP/MCP Status | Test Coverage | Notes |
|---------|-----------|------------|----------------------|--------------------|--------------|----------------|--------------|-------|
| **Repository indexing** | `services/indexing_service.py` | `codexa index` | Unit-tested | Environment-blocked (wheel absent) | Source-confirmed | Unverified | 84% | — |
| **Incremental indexing** | `services/indexing_service.py` | `codexa index --add` / watch | Unit-tested | Environment-blocked | Source-confirmed | Unverified | 84% (shared) | — |
| **Force re-index** | `services/indexing_service.py` | `codexa index --force` | Unit-tested | N/A | Source-confirmed | Unverified | Tested | — |
| **Model-consistency guard** | `indexing/ + storage/` | Automatic on `index` | Unit-tested | N/A | N/A | N/A | Tested | — |
| **`.codexaignore` support** | `indexing/scanner.py` | Automatic | Unit-tested | Environment-blocked | N/A | N/A | 90% | — |
| **Ctrl+C partial-save** | `cli/commands/index_cmd.py` | Signal handler | Unit-tested | N/A | N/A | N/A | Tested | Windows SIGINT may not work in all terminals |
| **Parallel indexing** | `indexing/parallel.py` | Automatic | Unit-tested | Environment-blocked | N/A | N/A | 97% | — |
| **Semantic search (Python/FAISS)** | `services/search_service.py` | `codexa search` | Unit-tested | Environment-blocked | Source-confirmed | Unverified | 94% | Requires `codexa[ml]` |
| **Keyword / BM25 search** | `search/keyword_search.py` | `codexa search --mode keyword` | Unit-tested | Environment-blocked | Source-confirmed | Unverified | 75% | — |
| **Hybrid search (RRF)** | `search/hybrid_search.py` | `codexa search --mode hybrid` | Unit-tested | Environment-blocked | Source-confirmed | Unverified | 90% | — |
| **Regex / grep search** | `search/grep.py` | `codexa grep` | Unverified (21% coverage) | N/A | Source-confirmed | Unverified | **21%** | Low coverage; subprocess paths untested |
| **File-watch daemon** | `daemon/watcher.py` | `codexa watch` | Unit-tested (75%) | N/A | Source-confirmed | Unverified | 75% | Native watcher platform layer not tested |
| **Symbol extraction / parsing** | `parsing/parser.py` | Core (internal) | Unit-tested | Environment-blocked | N/A | N/A | 97% | — |
| **Symbol explanation** | `analysis/ + tools` | `codexa explain` | Unit-tested | N/A | Source-confirmed | Unverified | 84% | — |
| **Code context windows** | `context/` | `codexa context` | Unit-tested | N/A | Source-confirmed | Unverified | 95% | — |
| **Repository summary** | `analysis/` | `codexa summary` | Unit-tested | N/A | Source-confirmed | Unverified | Tested | — |
| **Dependency map** | `analysis/` | `codexa deps` | Unit-tested | N/A | Source-confirmed | Unverified | Tested | — |
| **Call graph** | `analysis/` | `codexa tool run get_call_graph` | Unit-tested | N/A | Source-confirmed | Unverified | Tested | — |
| **Code quality** | `analysis/` | `codexa quality` | Unit-tested | N/A | Source-confirmed | Unverified | Tested | — |
| **Code metrics** | `analysis/` | `codexa metrics` | Unit-tested | N/A | Source-confirmed | Unverified | Tested | — |
| **Hotspots** | `analysis/` | `codexa hotspots` | Unit-tested | N/A | Source-confirmed | Unverified | Tested | — |
| **Quality gate (CI)** | `analysis/` | `codexa gate` | Unit-tested | N/A | N/A | N/A | Tested | — |
| **Impact analysis** | `analysis/` | `codexa impact` | Unit-tested | N/A | Source-confirmed | Unverified | Tested | `analyze_impact` D-complexity |
| **AI Q&A (LLM)** | `llm/` | `codexa ask` | Mocked-LLM tested | N/A | Source-confirmed | Unverified | 48–59% | Real API calls unverified |
| **Code review (LLM)** | `llm/` | `codexa review` | Mocked-LLM tested | N/A | Source-confirmed | Unverified | Low | — |
| **Refactor suggestions** | `llm/` | `codexa refactor` | Mocked-LLM tested | N/A | Source-confirmed | Unverified | Low | — |
| **RAG pipeline** | `llm/rag.py` | Internal | Mocked-LLM tested | N/A | N/A | N/A | 77% | — |
| **Streaming responses** | `llm/streaming.py` | Internal | Mocked-LLM tested | N/A | N/A | N/A | **49%** | Under-tested |
| **Multi-turn chat** | `llm/conversation.py` | `codexa chat` | Unit-tested | N/A | Source-confirmed | Unverified | 95% | — |
| **Autonomous investigation** | `llm/investigation.py` | `codexa investigate` | Mocked-LLM tested | N/A | Source-confirmed | Unverified | **59%** | Experimental |
| **Cross-refactor** | `llm/cross_refactor.py` | `codexa cross-refactor` | Mocked-LLM tested | N/A | Source-confirmed | Unverified | **53%** | Experimental |
| **Self-improving evolution** | `evolution/` | `codexa evolve` | Unverified (67–83%) | N/A | N/A | N/A | 67–83% | Experimental |
| **PR summary** | `cli/commands/pr_summary_cmd.py` | `codexa pr-summary` | Source-confirmed | N/A | N/A | N/A | Low | — |
| **HTTP bridge server** | `bridge/` | `codexa serve` | Source-confirmed | N/A | N/A | Unverified | Not directly tested | — |
| **MCP server** | `mcp/__init__.py` | `codexa mcp` | Unverified (30%) | N/A | N/A | Unverified | **30%** | External-client behaviour unverified |
| **Claude Desktop auto-config** | `mcp/claude_config.py` | `codexa mcp --claude-config` | Unverified (**0%**) | N/A | N/A | N/A | **0%** | Entirely untested |
| **AI Agent Tool Protocol** | `tools/` | `codexa tool run/list/schema` | Unit-tested | N/A | Source-confirmed | Unverified | 84–99% | — |
| **Plugin system** | `plugins/` | `codexa plugin` | Unit-tested | N/A | N/A | N/A | 97% | — |
| **Workspace (multi-repo)** | `workspace/` | `codexa workspace` | Unit-tested | N/A | N/A | N/A | 91% | — |
| **TUI (Textual)** | `tui/` | `codexa tui` | Unverified (21%) | N/A | N/A | N/A | **21%** | D-complexity fallback repl |
| **Web UI** | `web/` | `codexa web` | Unverified (16–20%) | N/A | N/A | Unverified | **16–20%** | Severely under-tested |
| **Visualization (Mermaid)** | `web/visualize.py` | `codexa viz` | Unit-tested | N/A | N/A | N/A | 98% | — |
| **LSP server** | `lsp/` | `codexa lsp` | Unverified (39%) | N/A | N/A | Unverified | **39%** | Likely incomplete |
| **Configuration** | `config/settings.py` | `codexa init` | Unit-tested | N/A | N/A | N/A | Tested | — |
| **Model management** | `embeddings/model_registry.py` | `codexa models` | Unit-tested | N/A | Source-confirmed | N/A | 94% | — |
| **Doctor / health check** | `cli/commands/doctor_cmd.py` | `codexa doctor` | Unit-tested | N/A | Source-confirmed | N/A | Tested | — |
| **Logging** | `utils/logging.py` | Internal | Unit-tested | N/A | N/A | N/A | 98% | — |
| **VS Code sidebar (4 panels)** | `vscode-extension/src/extension.ts` | Extension activation | Source-confirmed | N/A | **Unverified** | N/A | **No tests** | Live host not tested |
| **VS Code keybindings** | `extension.ts` | Ctrl+Shift+F5/E/Q | Source-confirmed | N/A | **Unverified** | N/A | No tests | — |
| **VS Code CodeLens** | `extension.ts` | Editor | **Not implemented** | N/A | N/A | N/A | — | README claims it; source does not implement it |
| **Rust vector store (flat)** | `codexa-core/src/ann.rs` | When wheel installed | Environment-blocked | Environment-blocked | N/A | N/A | Not testable | Wheel not built |
| **Rust HNSW** | `codexa-core/src/hnsw.rs` | When wheel installed | Environment-blocked | Environment-blocked | N/A | N/A | Not testable | Same |
| **Rust BM25** | `codexa-core/src/bm25.rs` | When wheel installed | Environment-blocked | Environment-blocked | N/A | N/A | Not testable | Same |
| **Rust AST chunker** | `codexa-core/src/ast_chunk.rs` | When wheel installed | Environment-blocked | Environment-blocked | N/A | N/A | Not testable | Same |
| **ONNX embedding** | `codexa-core/src/embed.rs` | Optional feature | Environment-blocked | Environment-blocked | N/A | N/A | Not testable | Optional compile feature |
| **Tantivy full-text** | `codexa-core/src/tantivy_search.rs` | Optional feature | Environment-blocked | Environment-blocked | N/A | N/A | Not testable | Optional compile feature |
| **Editor plugins (Zed, JetBrains, etc.)** | `editors/` | External | **Not implemented** | N/A | N/A | N/A | — | README lists them; no code exists |

---

## Features Requiring Immediate Attention

| Feature | Issue | Finding |
|---------|-------|---------|
| VS Code CodeLens | Claimed in README; not in source | F-19 |
| Editor plugins (Zed, JetBrains, etc.) | Listed in README; not in repository | F-20 |
| MCP Claude auto-config | 0% coverage, unverified | F-09 |
| LSP server | 39% coverage, likely incomplete | F-13 |
| Web server | 16% coverage, unverified | F-10 |
| grep/search | 21% coverage, unverified | F-12 |
| LLM streaming | 49% coverage, mocked LLM only | F-14 |
| Cross-refactor | 53% coverage, mocked LLM only | — |
