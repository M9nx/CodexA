# Quick Start

Get from zero to semantic code search in under 60 seconds.

## 1. Initialize & Index

```bash
cd /path/to/your-project
codex init          # Creates .codex/ directory
codex index .       # Index the entire codebase
codex doctor        # Verify everything is healthy
```

## 2. Search Your Code

```bash
# Semantic search (natural language)
codex search "authentication middleware"

# Get JSON output for tooling
codex search "error handling" --json
```

## 3. Explore Symbols

```bash
# Explain a function or class
codex explain process_payment

# Get rich context
codex context process_payment

# Trace dependencies
codex deps src/api/handlers.py
```

## 4. AI-Powered Analysis

::: tip Requires LLM Configuration
Set up an LLM provider in `.codex/config.json` first. See [Installation](installation#llm-configuration-optional).
:::

```bash
# Ask questions about your code
codex ask "How does the authentication flow work?"

# Multi-turn conversation
codex chat

# AI code review
codex review src/api/auth.py

# Autonomous investigation
codex investigate "Find all security vulnerabilities"
```

## 5. Quality & Metrics

```bash
# Analyze code quality
codex quality src/

# Find risky hotspots
codex hotspots

# Impact analysis (what breaks if I change this?)
codex impact

# Enforce quality gates in CI
codex gate
```

## 6. VS Code Integration

Add CodexA as a Copilot instruction source for your project:

```bash
mkdir -p .github
```

Create `.github/copilot-instructions.md` referencing CodexA commands. See the [AI Agent Setup](ai-agent-setup) for the full integration guide.

Configure VS Code settings:

```json
{
  "github.copilot.chat.codeGeneration.instructions": [
    { "file": ".github/copilot-instructions.md" }
  ]
}
```

Now Copilot Chat in Agent mode will automatically use CodexA for code understanding.

## 7. Start the Bridge Server (Optional)

For persistent IDE or agent connections:

```bash
codex serve --port 24842
```

Agents can then call `http://127.0.0.1:24842/tools/invoke` directly.

## What's Next?

- [CLI Reference](../reference/cli) — All 36 commands
- [Architecture](../reference/architecture) — How CodexA works internally
- [Plugin System](../features/plugin-system) — Extend with custom hooks
- [AI Workflows](../features/ai-tools) — Multi-turn chat, investigation chains
