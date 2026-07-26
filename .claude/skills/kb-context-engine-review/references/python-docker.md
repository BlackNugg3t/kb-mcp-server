# Python & Docker Hygiene Checklist

## Python

- **Async discipline**: since this stack is bot/webhook/MCP-server heavy, almost everything should be `async`. Grep for `requests.get(`/`requests.post(` inside `async def` — these block the event loop. Should be `httpx.AsyncClient` or `aiohttp`.
- **Config/secrets**: use `pydantic-settings` or plain `os.environ` reads validated at startup, not scattered `os.getenv` calls with silent `None` fallbacks for required secrets.
- **Logging**: structured logging (not bare `print`), and confirm nothing logs full request/response bodies that could contain tokens or PII.
- **Dependency pinning**: `requirements.txt`/`pyproject.toml` should pin versions (or use a lockfile) — unpinned deps in a Docker build means the image isn't reproducible.
- **Error handling granularity**: bare `except Exception: pass` swallowing errors in webhook handlers or ingestion jobs hides real failures — check for at least logging, ideally alerting/dead-letter handling.

## Docker / docker-compose

- **Multi-service topology**: does docker-compose separate the MCP server, each bot/integration adapter, and the vector DB into distinct services (recommended for failure isolation and independent scaling), or is everything jammed into one container/process? Flag the latter if any single integration is flaky.
- **Base image**: prefer `python:3.x-slim` over full `python:3.x` unless there's a specific need (build tooling) — check for unnecessary image bloat.
- **Multi-stage builds**: if there are compiled dependencies, confirm a multi-stage build is used so build tools don't ship in the final image.
- **Non-root user**: containers should not run as root; check for a `USER` directive.
- **Secrets in the image**: confirm no `.env` file or credentials are `COPY`'d into the image — should be injected at runtime via env vars / secret mounts / compose `env_file` (and that `env_file` isn't itself committed to git).
- **Healthchecks**: check for `HEALTHCHECK` (or compose `healthcheck:`) on long-running services (MCP server, bots) so orchestration can detect a hung process.
- **Restart policy**: `restart: unless-stopped` (or similar) on bot/server services so a transient crash (e.g. an unhandled Discord gateway disconnect) doesn't take the service down permanently.
- **.dockerignore**: confirm `.git`, `.env`, `__pycache__`, and test data aren't being copied into the build context/image.
- **Volume for persistent data**: if the vector store/KB data is file-based (e.g. local Chroma/FAISS), confirm it's on a named volume, not ephemeral container storage that vanishes on rebuild.
