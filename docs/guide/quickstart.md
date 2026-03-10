# Quick Start

Get from zero to semantic code search in under 60 seconds.

## 1. Initialize & Index

```bash
cd /path/to/your-project
codexa init --index  # Creates .codexa/ and builds index in one step
codexa doctor        # Verify everything is healthy
```

Or step by step:

```bash
codexa init          # Creates .codexa/ directory (auto-detects best model for your RAM)
codexa index .       # Index the entire codebase
```

::: tip Model Profiles
Pick an embedding model tier to match your hardware:

```bash
codexa init --profile fast       # Tiny model, <1 GB RAM
codexa init --profile balanced   # Default, ~2 GB RAM
codexa init --profile precise    # Best quality, ~4 GB RAM
```

Compare models on your codebase: `codexa models benchmark`
:::

## 2. Search Your Code

```bash
# Semantic search (natural language)
codexa search "authentication middleware"

# Get JSON output for tooling
codexa search "error handling" --json
```

## 3. Explore Symbols

```bash
# Explain a function or class
codexa explain process_payment

# Get rich context
codexa context process_payment

# Trace dependencies
codexa deps src/api/handlers.py
```

## 4. AI-Powered Analysis

::: tip Requires LLM Configuration
Set up an LLM provider in `.codexa/config.json` first. See [Installation](installation#llm-configuration-optional).
:::

```bash
# Ask questions about your code
codexa ask "How does the authentication flow work?"

# Multi-turn conversation
codexa chat

# AI code review
codexa review src/api/auth.py

# Autonomous investigation
codexa investigate "Find all security vulnerabilities"
```

## 5. Quality & Metrics

```bash
# Analyze code quality
codexa quality src/

# Find risky hotspots
codexa hotspots

# Impact analysis (what breaks if I change this?)
codexa impact

# Enforce quality gates in CI
codexa gate
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
codexa serve --port 24842
```

Agents can then call `http://127.0.0.1:24842/tools/invoke` directly.

## What's Next?

- [CLI Reference](../reference/cli) — All 39 commands
- [Architecture](../reference/architecture) — How CodexA works internally
- [Plugin System](../features/plugin-system) — Extend with custom hooks
- [AI Workflows](../features/ai-tools) — Multi-turn chat, investigation chains
