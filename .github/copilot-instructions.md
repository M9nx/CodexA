# Copilot Custom Instructions

## CodexA Integration

This project uses **CodexA** — a local developer intelligence engine.
You have access to the `codexa` CLI for semantic code search, symbol
explanation, dependency analysis, and more.

### Available Commands

Before answering questions about this codebase, use CodexA to gather context:

- **Search the codebase:**
  ```bash
  codexa search "<natural language query>" --json
  ```

- **Explain a symbol (function/class/method):**
  ```bash
  codexa tool run explain_symbol --arg symbol_name="<name>" --json
  ```

- **Get the call graph of a function:**
  ```bash
  codexa tool run get_call_graph --arg symbol_name="<name>" --json
  ```

- **Get file dependencies/imports:**
  ```bash
  codexa tool run get_dependencies --arg file_path="<path>" --json
  ```

- **Find all references to a symbol:**
  ```bash
  codexa tool run find_references --arg symbol_name="<name>" --json
  ```

- **Get rich context for a symbol:**
  ```bash
  codexa tool run get_context --arg symbol_name="<name>" --json
  ```

- **Summarize the entire repo:**
  ```bash
  codexa tool run summarize_repo --json
  ```

- **Explain all symbols in a file:**
  ```bash
  codexa tool run explain_file --arg file_path="<path>" --json
  ```

- **Code quality analysis:**
  ```bash
  codexa quality <path> --json
  ```

- **Impact analysis (blast radius):**
  ```bash
  codexa impact --json
  ```

### Rules

1. Always use `--json` flag for machine-readable output when running codexa commands.
2. When asked about code structure, search with `codexa search` first.
3. When explaining a function or class, use `codexa tool run explain_symbol`.
4. When analyzing impact of changes, use `codexa impact`.
5. When reviewing code, run `codexa quality <path>` first.
6. Prefer CodexA tools over reading large files manually — they provide
   structured, indexed results.
7. Use `codexa tool run get_call_graph` to understand function relationships.
8. Use `codexa tool run find_references` to assess change impact.

### Project Structure

- `semantic_code_intelligence/` — Main Python package
  - `cli/` — 32 CLI commands (click-based)
  - `tools/` — AI Agent Tooling Protocol (13 built-in tools)
  - `bridge/` — HTTP bridge server (port 24842)
  - `llm/` — LLM providers (OpenAI, Ollama, Mock)
  - `ci/` — Quality analysis, metrics, hotspots, impact
  - `evolution/` — Self-improving development loop (engine, budget, tasks, patches)
  - `web/` — Web UI and REST API
  - `plugins/` — Plugin system (22 hooks)
  - `parsing/` — Tree-sitter AST parsing (12 languages)
  - `indexing/` — Code chunking and scanning
  - `search/` — FAISS vector search
  - `embeddings/` — Sentence-transformer embeddings
  - `workspace/` — Multi-repo workspace management
