# Web Interface Reference

Auto-generated from the CodexA web module.

## Overview

CodexA ships an **optional** lightweight web interface (`codex web`) that
bundles a REST API and a browser UI on a single port (default 8080).
No external frameworks are required — the server uses Python's `http.server`.

## REST API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Server health / project metadata |
| GET | `/api/search?q=&top_k=&threshold=` | Semantic code search |
| GET | `/api/symbols?file=&kind=` | Symbol table browser |
| GET | `/api/deps?file=` | File dependency graph |
| GET | `/api/callgraph?symbol=` | Call graph edges |
| GET | `/api/summary` | Project summary |
| POST | `/api/ask` | Ask a natural-language question |
| POST | `/api/analyze` | Validate or explain a code snippet |

### POST `/api/ask` body

```json
{
  "question": "How does authentication work?",
  "top_k": 5
}
```

### POST `/api/analyze` body

```json
{
  "code": "def hello(): ...",
  "mode": "validate"
}
```

## Visualization (Mermaid)

The `codex viz` command and `/api/viz/{kind}` endpoint produce
Mermaid-compatible diagram source text.

| Kind | Description |
|------|-------------|
| `callgraph` | Caller → callee flowchart |
| `deps` | File dependency flowchart |
| `symbols` | Class diagram of symbols |
| `workspace` | Hub-and-spoke project map |

### Example output

````mermaid
flowchart LR
    main["main"] --> auth["auth"]
    auth["auth"] --> db["db"]
````

## Web UI Pages

| Path | Page |
|------|------|
| `/` | Search interface |
| `/symbols` | Symbol browser |
| `/workspace` | Project overview |
| `/viz` | Visualization viewer |

The UI is server-rendered HTML with inline CSS (dark theme) and
vanilla JavaScript — no build step or npm required.

## CLI Commands

- `codex web [--host HOST] [--port PORT] [--path PATH]` — start the web server
- `codex viz KIND [--target T] [--output FILE] [--json] [--path PATH]` — generate a diagram
