from __future__ import annotations

import datetime as dt
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from app.db import init_pool
from app.dora import compute_dora_from_prs, upsert_dora_metrics
from app.mcp_client import MCPClient
from app.insights import generate_insight_summary, upsert_daily_insight


mcp_client = MCPClient()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await init_pool()
    yield
    await app.state.pool.close()


app = FastAPI(title="GitHub MCP Productivity Engine", version="0.1.0", lifespan=lifespan)


async def pool_dep(request: Request):
    return request.app.state.pool


class HealthResponse(BaseModel):
    status: str
    service: str = "api"
    mcp_url: str | None = None


class IngestRequest(BaseModel):
    repositories: list[str] = Field(..., example=["owner/repo1", "owner/repo2"])
    lookback_days: int = Field(7, ge=1, le=90)


class ChatRequest(BaseModel):
    repo: str
    message: str
    lookback_days: int = Field(7, ge=1, le=90)


class ChatResponse(BaseModel):
    answer: str
    data_used: dict | None = None
    tool: str | None = None


MCP_BASE_URL = os.getenv("MCP_BASE_URL", "http://mcp:3001")


@app.get("/health", response_model=HealthResponse)
async def health(request: Request):
    pool_ok = False
    try:
        pool = request.app.state.pool
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        pool_ok = True
    except Exception:
        pool_ok = False
    return HealthResponse(status="ok" if pool_ok else "degraded", mcp_url=MCP_BASE_URL)


@app.post("/ingest")
async def ingest(req: IngestRequest, pool=Depends(pool_dep)):
    since_dt = dt.datetime.utcnow() - dt.timedelta(days=req.lookback_days)
    since_iso = since_dt.isoformat() + "Z"

    results: list[dict[str, Any]] = []
    for repo in req.repositories:
        raw_prs = await mcp_client.list_pull_requests(repo=repo, state="closed", since=since_iso)
        prs = raw_prs if isinstance(raw_prs, list) else raw_prs.get("items", [])
        metrics_per_day = compute_dora_from_prs(prs)
        await upsert_dora_metrics(pool, repo, metrics_per_day)
        # generate a simple daily insight for the most recent day with data
        if metrics_per_day:
            latest_day = max(metrics_per_day.keys())
            insight_text, risk_flags, top_contrib = generate_insight_summary(repo, metrics_per_day, prs, latest_day)
            await upsert_daily_insight(pool, repo, latest_day, insight_text, risk_flags, top_contrib)
        results.append({"repo": repo, "days": len(metrics_per_day)})

    return {"message": "Ingestion complete", "results": results}


@app.get("/metrics/dora")
async def get_dora_metrics(repo: str, range_days: int = 30, pool=Depends(pool_dep)):
    if range_days < 1 or range_days > 180:
        raise HTTPException(status_code=400, detail="range_days must be between 1 and 180")

    query = """
    SELECT date, deployment_frequency, avg_lead_time_minutes, change_failure_rate, mttr_minutes
    FROM dora_metrics
    WHERE repo_id = $1 AND date >= (CURRENT_DATE - $2 * INTERVAL '1 day')
    ORDER BY date ASC;
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, repo, range_days)
    metrics = [dict(row) for row in rows]
    return {"repo": repo, "range_days": range_days, "metrics": metrics}


@app.get("/metrics/org")
async def get_org_metrics(range_days: int = 30, pool=Depends(pool_dep)):
    """Aggregate metrics across all repos for organization view (FR010)."""
    if range_days < 1 or range_days > 180:
        raise HTTPException(status_code=400, detail="range_days must be between 1 and 180")

    query = """
    SELECT date,
           AVG(deployment_frequency) AS deployment_frequency,
           AVG(avg_lead_time_minutes) AS avg_lead_time_minutes,
           AVG(change_failure_rate) AS change_failure_rate,
           AVG(mttr_minutes) AS mttr_minutes
    FROM dora_metrics
    WHERE date >= (CURRENT_DATE - $1 * INTERVAL '1 day')
    GROUP BY date
    ORDER BY date ASC;
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, range_days)
    metrics = [dict(row) for row in rows]
    return {"range_days": range_days, "metrics": metrics}


@app.get("/metrics/dora/drilldown")
async def get_dora_drilldown(repo: str, date: dt.date, pool=Depends(pool_dep)):
    """Return PRs merged on a specific date for contextualization (FR009)."""
    since = dt.datetime.combine(date, dt.time.min).isoformat() + "Z"
    until = dt.datetime.combine(date + dt.timedelta(days=1), dt.time.min).isoformat() + "Z"
    prs = await mcp_client.list_pull_requests(repo=repo, state="closed", since=since)
    items = prs if isinstance(prs, list) else prs.get("items", [])
    merged_that_day = [p for p in items if p.get("merged_at", "").startswith(str(date))]
    return {"repo": repo, "date": str(date), "pull_requests": merged_that_day}


@app.get("/metrics/contributors")
async def get_contributor_risk(repo: str, lookback_days: int = 30):
    """Aggregate commit counts by author and flag bus factor risk (FR008)."""
    if lookback_days < 1 or lookback_days > 180:
        raise HTTPException(status_code=400, detail="lookback_days must be between 1 and 180")
    since_dt = dt.datetime.utcnow() - dt.timedelta(days=lookback_days)
    since_iso = since_dt.isoformat() + "Z"
    commits = await mcp_client.list_commits(repo, since=since_iso)
    items = commits if isinstance(commits, list) else commits.get("items", [])
    authors: dict[str, int] = {}
    for c in items:
        author = c.get("author", {}).get("login") or c.get("commit", {}).get("author", {}).get("name")
        if not author:
            continue
        authors[author] = authors.get(author, 0) + 1
    total = sum(authors.values()) or 1
    sorted_authors = sorted(authors.items(), key=lambda x: x[1], reverse=True)
    risk_flags = []
    if sorted_authors and sorted_authors[0][1] / total >= 0.8:
        risk_flags.append("bus_factor")
    return {
        "repo": repo,
        "lookback_days": lookback_days,
        "authors": [{"author": a, "commit_count": c} for a, c in sorted_authors],
        "risk_flags": risk_flags,
    }


@app.get("/insights/daily")
async def get_daily_insights(repo: str, limit: int = 7, pool=Depends(pool_dep)):
    # TODO: fetch from Postgres daily_insights table
        if limit < 1 or limit > 30:
            raise HTTPException(status_code=400, detail="limit must be between 1 and 30")

        query = """
        SELECT date, summary_text, risk_flags, top_contributors
        FROM daily_insights
        WHERE repo_id = $1
        ORDER BY date DESC
        LIMIT $2;
        """

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, repo, limit)
        insights = [dict(row) for row in rows]
        return {"repo": repo, "insights": insights, "limit": limit}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    # TODO: route NL to MCP tools + LLM
        # Minimal heuristic router: if asks for commits -> list_commits, else pull requests
        since_dt = dt.datetime.utcnow() - dt.timedelta(days=req.lookback_days)
        since_iso = since_dt.isoformat() + "Z"
        if "commit" in req.message.lower():
            data = await mcp_client.list_commits(req.repo, since=since_iso)
            items = data if isinstance(data, list) else data.get("items", [])
            answer = f"Found {len(items)} commits in the last {req.lookback_days} days."
            return ChatResponse(answer=answer, data_used={"commits": items[:5]}, tool="list_commits")
        else:
            data = await mcp_client.list_pull_requests(req.repo, state="closed", since=since_iso)
            items = data if isinstance(data, list) else data.get("items", [])
            answer = f"Found {len(items)} PRs closed in the last {req.lookback_days} days."
            return ChatResponse(answer=answer, data_used={"pull_requests": items[:5]}, tool="list_pull_requests")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
