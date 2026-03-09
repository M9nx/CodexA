# AI Workflows Reference

Auto-generated documentation for CodexA's advanced AI workflow features.

## Multi-Turn Conversations

Use `codex chat` for persistent multi-turn conversations about your codebase.

| Option | Description |
|--------|-------------|
| `--session <id>` | Resume an existing conversation |
| `--list-sessions` | Show all stored sessions |
| `--max-turns <n>` | Context window limit (default: 20) |
| `--json` | JSON output |
| `--pipe` | Machine-readable output |

### Session Persistence

Sessions are stored in `.codex/sessions/<id>.json` with full message history.
Each session tracks: session_id, title, messages, created_at, updated_at.

### API

| Class | Method | Description |
|-------|--------|-------------|
| `ConversationSession` | `add_user(content)` | Add user message |
| `ConversationSession` | `add_assistant(content)` | Add assistant response |
| `ConversationSession` | `get_messages_for_llm(max_turns)` | Get context-windowed messages |
| `SessionStore` | `save(session)` | Persist to disk |
| `SessionStore` | `load(session_id)` | Load from disk |
| `SessionStore` | `list_sessions()` | List all sessions |
| `SessionStore` | `delete(session_id)` | Remove a session |
| `SessionStore` | `get_or_create(session_id)` | Resume or create |

---

## Autonomous Investigation Chains

Use `codex investigate` for multi-step autonomous code exploration.

| Option | Description |
|--------|-------------|
| `--max-steps <n>` | Step limit (default: 6) |
| `--json` | JSON output |
| `--pipe` | Machine-readable output |

### How It Works

1. The LLM planner receives the user's question
2. It decides an action: `search`, `analyze`, `deps`, or `conclude`
3. The action is executed and results fed back to the planner
4. Loop continues until `conclude` or step limit is reached

### Investigation Actions

| Action | Description |
|--------|-------------|
| `search` | Semantic search over the codebase |
| `analyze` | Symbol lookup and context analysis |
| `deps` | Dependency analysis for a file |
| `conclude` | Final answer delivery |

---

## Cross-Repo Refactoring

Use `codex cross-refactor` to find duplicate logic across workspace repos.

| Option | Description |
|--------|-------------|
| `--threshold <f>` | Similarity threshold (default: 0.70) |
| `--json` | JSON output |
| `--pipe` | Machine-readable output |

### Analysis Pipeline

1. Collect symbols from all registered workspace repositories
2. Compare function/method bodies using trigram Jaccard similarity
3. Only cross-repo matches are reported (not intra-repo)
4. If LLM is configured, generates actionable refactoring suggestions

---

## Streaming LLM Responses

The `stream_chat()` function delivers tokens incrementally from any provider.

### Supported Providers

| Provider | Streaming Method |
|----------|-----------------|
| Ollama | Native HTTP streaming (`stream: true`) |
| OpenAI | Native streaming API (`stream=True`) |
| Mock | Word-by-word simulation |
| Other | Fallback single-token emit |

### Plugin Integration

The `PluginHook.ON_STREAM` hook is dispatched for each token event,
allowing plugins to monitor, transform, or log streaming output.

### StreamEvent Types

| Kind | Description |
|------|-------------|
| `start` | Stream initialization with provider metadata |
| `token` | A token of generated text |
| `done` | Stream completed successfully |
| `error` | An error occurred during streaming |
