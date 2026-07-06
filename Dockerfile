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

# Expose MCP HTTP port (for SSE/HTTP mode — agents connect here)
EXPOSE 9020

# Health check via HTTP endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:9020/health || exit 1

# Default: start MCP server (mode determined by config.json)
# Set MCP mode via: MCP_MODE=sse or MCP_MODE=stdio
CMD ["python", "-m", "src.main", "serve"]
