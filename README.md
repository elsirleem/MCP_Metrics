# GitHub MCP Productivity Engine

Foundational scaffold for the system described in the PRD/TechnicalStack documents. Includes a FastAPI orchestrator, Next.js frontend, Postgres, and the GitHub MCP server via Docker Compose.

## Stack
- FastAPI (Python 3.12) for orchestration, MCP tool calling, DORA + insights endpoints
- Next.js (App Router) for dashboard, chat, daily briefings
- PostgreSQL for metrics + insights storage
- GitHub MCP server (Docker) as the retrieval layer

## Quick start (local with Docker)
1. Copy env template and fill secrets:
   ```bash
   cp infra/env/.env.example .env
   # fill GITHUB_PAT, OPENAI_API_KEY or ANTHROPIC_API_KEY
   ```
2. Bring up the stack:
   ```bash
   cd infra
   docker compose up --build
   ```
3. Services:
   - API: http://localhost:8000 (FastAPI docs at /docs)
   - Frontend: http://localhost:3000
   - MCP server: http://localhost:3001
   - Postgres: localhost:5432 (db: mcp_metrics, user: mcp, pass: mcp_password)

## Daily automation (ingestion + insights)
- Set `INGEST_REPOSITORIES` env (comma-separated owner/repo) and optionally `INGEST_LOOKBACK_DAYS`.
- Run the job once: `cd api && INGEST_REPOSITORIES=owner/repo uvicorn app.main:app --reload` for API, or `python -m app.jobs` for the batch job.
- To schedule daily via cron: `0 2 * * * cd /path/to/api && INGEST_REPOSITORIES=owner/repo python -m app.jobs >> /tmp/mcp_cron.log 2>&1`

## Next steps
- Implement real MCP client usage in `api/app/mcp_client.py` and wire to ingestion + chat endpoints.
- Add persistence layer for `dora_metrics` and `daily_insights` tables (see `OtherInfo.md`).
- Build dashboard + chat UI pages that consume the API.
- Add cron/worker to run daily ingestion + AI insight generation.

## Development without Docker
- API: `cd api && uvicorn app.main:app --reload`
- Frontend: `cd frontend && npm install && npm run dev`

## Notes
- Compose expects Docker to supply the MCP server image `ghcr.io/modelcontextprotocol/github-mcp-server:latest`. Ensure your PAT has repo:read scope for your targets.
