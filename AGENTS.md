# Tempo AI v2

## Structure

- `src/ai_v2/` - Single Python package
  - `extractors/` - 10 source extractors (Slack, Linear, GitHub, GCal, Gmail, GDrive, Granola, Attio, Pylon, BetterStack)
  - `routers/` - FastAPI route handlers (search, query, sync, secrets, health)
  - `sandbox/` - Codex+Docker sandbox builder
  - `app.py` - FastAPI application
  - `mcp_server.py` - MCP server (7 tools)
  - `pipeline.py` - ETL pipeline orchestrator
  - `cli.py` - Unified CLI (sync, serve, embed, sandbox, etc.)
  - `config.py` - All settings (DB, API, extractor credentials)
- `migrations/` - Alembic PG migrations
- `scripts/` - Deployment and migration scripts
- `sandbox/` - Dockerfile + entrypoint for sandbox images

## Commands

```bash
make install                    # Install all deps
make lint                       # Lint
make test                       # Test
make fmt                        # Auto-fix lint + format
make migrate                    # Run Postgres migrations
make sync                       # Run ETL pipeline
make api                        # Start API server
make sandbox-build              # Build sandbox Docker image
make sandbox-update-repos       # Update repos in sandbox
```

## CLI

```bash
ai-v2 sync                     # Run ETL pipeline
ai-v2 serve                    # Start API server
ai-v2 embed                    # Generate embeddings
ai-v2 status                   # Show sync status
ai-v2 search "query"           # Test hybrid search
ai-v2 continuous               # Run continuous sync loop
ai-v2 migrate-from-sqlite PATH # Import from metronome SQLite
ai-v2 sandbox sync-repos       # Clone/update repos
ai-v2 sandbox build             # Build sandbox Docker image
```

## Rules

- Python 3.11+, use `uv` for all dependency management — never pip/poetry/pipenv
- `ruff` for linting and formatting (line-length=100)
- All secrets via environment variables, never hardcode credentials
- Use `asyncpg` for Postgres connections, `pgvector` for embeddings
- No staging views or mart views — query `raw_records` JSONB directly via `data->>'field'`
- Alembic for all schema migrations — never modify the DB manually
- All API endpoints require `Authorization: Bearer <key>` auth
- Tests use pytest with pytest-asyncio in `tests/` directory
- Follow conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
- Only extract company knowledge base sources (Slack, Linear, GitHub, GCal, Gmail, GDrive, Granola, Attio, Pylon, BetterStack)
- Do NOT add extractors for external tools (allium, defillama, etc.) — those are called on-demand, not stored

## CI

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run mypy src/ai_v2
```
