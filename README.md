# GitHub MCP Productivity Engine

Foundational scaffold for the system described in the PRD/TechnicalStack documents. Includes a FastAPI orchestrator, Next.js frontend, Postgres, and the GitHub MCP server via Docker Compose.

## Stack
- FastAPI (Python 3.12) for orchestration, MCP tool calling, DORA + insights endpoints
- Next.js (App Router) for dashboard, chat, daily briefings
- PostgreSQL for metrics + insights storage
- GitHub MCP server (Docker) as the retrieval layer
- Optional OpenAI (or API-compatible) model for AI chat + insight generation

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

## Recently added
- MCP health check surfaced on `/health`.
- DORA CFR/MTTR heuristics and contributor-risk endpoint.
- Optional LLM-backed chat and insight summarization (set `OPENAI_API_KEY`).
- Frontend charts, drilldowns, org view toggle, contributor risk card.
- CI for backend/frontend and scheduled ingestion workflow templates (`.github/workflows`).

## Development without Docker
- API: `cd api && uvicorn app.main:app --reload`
- Frontend: `cd frontend && npm install && npm run dev`

### Frontend dev tips
- You only need `npm install` when `package.json` / lockfile changes or on a fresh clone. Otherwise go straight to `npm run dev`.
- Keep Node versions consistent (e.g., via `nvm use`) to avoid repeated reinstalls.
- If you develop in Docker, cache or bake `node_modules` to prevent it being wiped on each container start.

### Tests
- Backend: `cd api && pip install .[dev] && pytest`
- Frontend: `cd frontend && npm run lint && npm run build`

## Notes
- Compose expects Docker to supply the MCP server image `ghcr.io/modelcontextprotocol/github-mcp-server:latest`. Ensure your PAT has repo:read scope for your targets.
