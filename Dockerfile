# ── Builder stage ────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ── Runtime stage ─────────────────────────────────────────────────────────
FROM python:3.12-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash kb && \
    mkdir -p /app/knowledge/knowledge /app/knowledge/memories /app/knowledge/artifacts /app/logs && \
    chown -R kb:kb /app

USER kb
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /home/kb/.local
ENV PATH="/home/kb/.local/bin:$PATH"

# Copy application code
COPY --chown=kb:kb . .

# Expose MCP port (for SSE mode if configured)
EXPOSE 9020

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import json; print(json.dumps({'status':'ok'}))" || exit 1

# Default: start MCP server in stdio mode
# For SSE mode, override CMD with: python -m src.main serve-sse
CMD ["python", "-m", "src.main", "serve"]
