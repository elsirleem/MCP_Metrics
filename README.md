# GitHub MCP Productivity Engine

Foundational scaffold for the system described in the PRD/TechnicalStack documents. Includes a FastAPI orchestrator, Next.js frontend, Postgres, and the GitHub MCP server via Docker Compose.

## Stack
- FastAPI (Python 3.12) for orchestration, MCP tool calling, DORA + insights endpoints
- Next.js (App Router) for dashboard, chat, daily briefings
- PostgreSQL for metrics + insights storage
- GitHub MCP server (Docker) as the retrieval layer
- Optional OpenAI (or API-compatible) model for AI chat + insight generation

## Run the full stack (Docker + MCP)
Prereqs: Docker & Compose, GitHub PAT with `repo:read`, optional OpenAI/Anthropic key if you want LLM chat/summarization.

1) Configure environment
```bash
cp infra/env/.env.example .env
# Required
GITHUB_PAT=ghp_your_pat_here   # needs repo:read for target repos
# Optional (enables LLM-backed chat/insight rewriting)
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
# Ingestion defaults
INGEST_REPOSITORIES=owner/repo   # comma-separated
INGEST_LOOKBACK_DAYS=7
```

2) Start everything
```bash
cd infra
docker compose --env-file ../.env up --build
# add -d to run detached
```

3) Where things run
- Frontend: http://localhost:3000
- API: http://localhost:8000 (docs at /docs, health at /health)
- MCP server: http://localhost:3001
- Postgres: localhost:5432 (db `mcp_metrics`, user `mcp`, pass `mcp_password`)

4) Use the app
- In the UI, set repository to `owner/repo` (required) and click **Run ingestion**.
- Use **Refresh metrics** / **Refresh insights** as needed.
- Drilldowns and chat rely on MCP; ensure the PAT is valid and the MCP container is healthy.

Troubleshooting
- “Failed to fetch” in UI: confirm API is up (`http://localhost:8000/health`) and that `NEXT_PUBLIC_API_BASE_URL` inside frontend is `http://localhost:8000` (default in compose). API CORS allows `http://localhost:3000`.
- MCP errors: verify `GITHUB_PAT` in `.env` and that MCP health (`http://localhost:3001/health`) returns ok.
- If using npm dev instead of Docker, export `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` before `npm run dev`.

## Daily automation (ingestion + insights)
- Set `INGEST_REPOSITORIES` env (comma-separated owner/repo) and optionally `INGEST_LOOKBACK_DAYS`.
- Run the job once: `cd api && INGEST_REPOSITORIES=owner/repo uvicorn app.main:app --reload` for API, or `python -m app.jobs` for the batch job.
- To schedule daily via cron: `0 2 * * * cd /path/to/api && INGEST_REPOSITORIES=owner/repo python -m app.jobs >> /tmp/mcp_cron.log 2>&1`

## Recently added
- **Dashboard-configurable GitHub PAT**: Enter your PAT directly in the UI to analyze any repository without restarting services.
- **Enhanced AI Chat**: Ask questions about DORA metrics, MCP concepts, or your repository's performance. Works with or without OpenAI API key:
  - With OpenAI: Full conversational AI with context about your metrics and GitHub data
  - Without OpenAI: Intelligent fallback responses for common DORA/MCP questions
- MCP health check surfaced on `/health`.
- DORA CFR/MTTR heuristics and contributor-risk endpoint.
- Frontend charts, drilldowns, org view toggle, contributor risk card.
- CI for backend/frontend and scheduled ingestion workflow templates (`.github/workflows`).

## Chat Features
The chat can answer questions about:
- **DORA Metrics**: "What are DORA metrics?", "Explain lead time", "What is a good deployment frequency?"
- **MCP Concepts**: "What is MCP?", "How does the Model Context Protocol work?"
- **Your Repository**: "What shipped last week?", "Who are the top contributors?", "How is my repo doing?"
- **Risk Analysis**: "What are the risk flags?", "Is there bus factor risk?"

For the best experience, configure `OPENAI_API_KEY` in your `.env` file. The system will provide helpful fallback responses even without it.

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
