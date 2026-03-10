FROM python:3.12-slim AS base

LABEL maintainer="M9nx <https://github.com/M9nx>"
LABEL description="CodexA — Developer intelligence CLI"
LABEL version="0.4.0"

# Install ripgrep for fast filesystem grep
RUN apt-get update && \
    apt-get install -y --no-install-recommends ripgrep git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY semantic_code_intelligence/ semantic_code_intelligence/

RUN pip install --no-cache-dir -e ".[tui]"

# Pre-download default embedding model
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')" 2>/dev/null || true

WORKDIR /workspace
ENTRYPOINT ["codexa"]
CMD ["--help"]
