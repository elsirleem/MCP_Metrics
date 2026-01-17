from __future__ import annotations

import datetime as dt
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.db import init_pool
from app.dora import compute_dora_from_prs, upsert_dora_metrics
from app.mcp_client import MCPClient
from app.insights import generate_insight_summary, upsert_daily_insight
from app.llm import enhance_insight, summarize_chat
from app.business import (
    upsert_business_metrics,
    get_business_metrics,
    compute_correlations,
    calculate_business_impact,
    get_dora_performance_level,
)


mcp_client = MCPClient()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await init_pool()
    yield
    await app.state.pool.close()


app = FastAPI(title="GitHub MCP Productivity Engine", version="0.1.0", lifespan=lifespan)

# Allow frontend to call API from browser (localhost:3000 or container network).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


async def pool_dep(request: Request):
    return request.app.state.pool


class HealthResponse(BaseModel):
    status: str
    service: str = "api"
    mcp_url: str | None = None
    mcp_ok: bool | None = None


class IngestRequest(BaseModel):
    repositories: list[str] = Field(..., example=["owner/repo1", "owner/repo2"])
    lookback_days: int = Field(7, ge=1, le=90)
    github_pat: str | None = Field(None, description="Optional GitHub PAT to use for this request")


class ChatRequest(BaseModel):
    repo: str
    message: str
    lookback_days: int = Field(7, ge=1, le=90)
    github_pat: str | None = Field(None, description="Optional GitHub PAT to use for this request")


class ChatResponse(BaseModel):
    answer: str
    data_used: dict | None = None
    tool: str | None = None


class BusinessMetricsRequest(BaseModel):
    """Business metrics input for correlation with DORA metrics."""
    org_id: str = Field("default", description="Organization identifier")
    date: dt.date = Field(..., description="Date for these metrics")
    revenue: float | None = Field(None, description="Daily/weekly revenue")
    new_customers: int | None = Field(None, description="New customer signups")
    customer_churn_rate: float | None = Field(None, ge=0, le=1, description="Customer churn rate (0-1)")
    customer_satisfaction_score: float | None = Field(None, ge=0, le=100, description="NPS or CSAT score (0-100)")
    support_tickets: int | None = Field(None, description="Number of support tickets")
    avg_resolution_time_hours: float | None = Field(None, description="Avg ticket resolution time in hours")
    incidents: int | None = Field(None, description="Number of production incidents")
    incident_severity_avg: float | None = Field(None, ge=1, le=5, description="Average incident severity (1-5)")
    uptime_percentage: float | None = Field(None, ge=0, le=100, description="Service uptime percentage")
    features_shipped: int | None = Field(None, description="Number of features delivered")
    bug_reports: int | None = Field(None, description="Number of bugs reported by users")
    custom_metrics: dict | None = Field(None, description="Additional custom metrics")


class BusinessImpactRequest(BaseModel):
    """Request to calculate business impact of DORA improvements."""
    dora_before: dict = Field(..., description="DORA metrics before improvement period")
    dora_after: dict = Field(..., description="DORA metrics after improvement period")
    annual_revenue: float | None = Field(None, description="Annual revenue for ROI calculation")
    avg_incident_cost: float | None = Field(None, description="Average cost per incident")
    engineer_hourly_rate: float | None = Field(None, description="Average engineer hourly rate")
    team_size: int | None = Field(None, description="Engineering team size")


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
    mcp_ok = await mcp_client.health()
    status = "ok" if pool_ok and mcp_ok else "degraded"
    return HealthResponse(status=status, mcp_url=MCP_BASE_URL, mcp_ok=mcp_ok)


@app.post("/ingest")
async def ingest(req: IngestRequest, pool=Depends(pool_dep)):
    for repo in req.repositories:
        if "/" not in repo:
            raise HTTPException(status_code=400, detail=f"Invalid repo format: {repo}. Expected owner/repo")
    since_dt = dt.datetime.utcnow() - dt.timedelta(days=req.lookback_days)
    since_iso = since_dt.isoformat() + "Z"

    results: list[dict[str, Any]] = []
    for repo in req.repositories:
        raw_prs = await mcp_client.list_pull_requests(repo=repo, state="closed", since=since_iso, token=req.github_pat)
        prs = raw_prs if isinstance(raw_prs, list) else raw_prs.get("items", [])
        metrics_per_day = compute_dora_from_prs(prs)
        await upsert_dora_metrics(pool, repo, metrics_per_day)
        # generate a simple daily insight for the most recent day with data
        if metrics_per_day:
            latest_day = max(metrics_per_day.keys())
            insight_text, risk_flags, top_contrib = generate_insight_summary(repo, metrics_per_day, prs, latest_day)
            llm_insight = await enhance_insight(
                repo,
                str(latest_day),
                insight_text,
                metrics_per_day.get(latest_day),
                top_contrib,
            )
            if llm_insight:
                insight_text = llm_insight
            await upsert_daily_insight(pool, repo, latest_day, insight_text, risk_flags, top_contrib)
        results.append({"repo": repo, "days": len(metrics_per_day)})

    return {"message": "Ingestion complete", "results": results}


@app.get("/metrics/dora")
async def get_dora_metrics(repo: str, range_days: int = 30, pool=Depends(pool_dep)):
    if "/" not in repo:
        raise HTTPException(status_code=400, detail="Invalid repo format; expected owner/repo")
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
async def get_dora_drilldown(repo: str, date: dt.date, github_pat: str | None = None, pool=Depends(pool_dep)):
    if "/" not in repo:
        raise HTTPException(status_code=400, detail="Invalid repo format; expected owner/repo")
    """Return PRs merged on a specific date for contextualization (FR009)."""
    since = dt.datetime.combine(date, dt.time.min).isoformat() + "Z"
    until = dt.datetime.combine(date + dt.timedelta(days=1), dt.time.min).isoformat() + "Z"
    prs = await mcp_client.list_pull_requests(repo=repo, state="closed", since=since, token=github_pat)
    items = prs if isinstance(prs, list) else prs.get("items", [])
    merged_that_day = [p for p in items if p.get("merged_at", "").startswith(str(date))]
    return {"repo": repo, "date": str(date), "pull_requests": merged_that_day}


@app.get("/metrics/contributors")
async def get_contributor_risk(repo: str, lookback_days: int = 30, github_pat: str | None = None):
    if "/" not in repo:
        raise HTTPException(status_code=400, detail="Invalid repo format; expected owner/repo")
    """Aggregate commit counts by author and flag bus factor risk (FR008)."""
    if lookback_days < 1 or lookback_days > 180:
        raise HTTPException(status_code=400, detail="lookback_days must be between 1 and 180")
    since_dt = dt.datetime.utcnow() - dt.timedelta(days=lookback_days)
    since_iso = since_dt.isoformat() + "Z"
    commits = await mcp_client.list_commits(repo, since=since_iso, token=github_pat)
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
    if "/" not in repo:
        raise HTTPException(status_code=400, detail="Invalid repo format; expected owner/repo")
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
async def chat(req: ChatRequest, pool=Depends(pool_dep)):
    if "/" not in req.repo:
        raise HTTPException(status_code=400, detail="Invalid repo format; expected owner/repo")
    
    since_dt = dt.datetime.utcnow() - dt.timedelta(days=req.lookback_days)
    since_iso = since_dt.isoformat() + "Z"
    
    # Determine what GitHub data to fetch based on the question
    message_lower = req.message.lower()
    tool = None
    items = []
    
    # Only fetch GitHub data if the question seems to need it
    needs_github_data = any(kw in message_lower for kw in [
        "commit", "pr", "pull request", "shipped", "merged", "deploy", 
        "release", "change", "who", "author", "contributor"
    ])
    
    if needs_github_data:
        tool = "list_commits" if "commit" in message_lower else "list_pull_requests"
        if tool == "list_commits":
            data = await mcp_client.list_commits(req.repo, since=since_iso, token=req.github_pat)
        else:
            data = await mcp_client.list_pull_requests(req.repo, state="closed", since=since_iso, token=req.github_pat)
        items = data if isinstance(data, list) else data.get("items", [])
    
    # Fetch DORA metrics from database
    metrics = []
    try:
        query = """
        SELECT date, deployment_frequency, avg_lead_time_minutes, change_failure_rate, mttr_minutes
        FROM dora_metrics
        WHERE repo_id = $1 AND date >= (CURRENT_DATE - $2 * INTERVAL '1 day')
        ORDER BY date DESC;
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, req.repo, req.lookback_days)
        metrics = [dict(row) for row in rows]
    except Exception:
        pass
    
    # Fetch recent insights
    insights = []
    try:
        query = """
        SELECT date, summary_text, risk_flags
        FROM daily_insights
        WHERE repo_id = $1
        ORDER BY date DESC
        LIMIT 5;
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, req.repo)
        insights = [dict(row) for row in rows]
    except Exception:
        pass
    
    # Fetch contributor data
    contributors = []
    try:
        commits = await mcp_client.list_commits(req.repo, since=since_iso, token=req.github_pat)
        commit_items = commits if isinstance(commits, list) else commits.get("items", [])
        authors: dict[str, int] = {}
        for c in commit_items:
            author = c.get("author", {}).get("login") or c.get("commit", {}).get("author", {}).get("name")
            if author:
                authors[author] = authors.get(author, 0) + 1
        contributors = [{"author": a, "commit_count": c} for a, c in sorted(authors.items(), key=lambda x: x[1], reverse=True)]
    except Exception:
        pass
    
    # Get LLM response with full context
    llm_answer = await summarize_chat(
        message=req.message,
        tool=tool,
        items=items if items else None,
        metrics=metrics if metrics else None,
        insights=insights if insights else None,
        contributors=contributors if contributors else None,
        repo=req.repo,
        lookback_days=req.lookback_days,
    )
    
    if llm_answer:
        answer = llm_answer
    else:
        # Enhanced fallback response when no LLM available
        answer = _build_fallback_answer(req.message, req.repo, req.lookback_days, metrics, items, tool, contributors)

    return ChatResponse(answer=answer, data_used={tool: items[:5]} if tool else None, tool=tool)


def _build_fallback_answer(
    message: str,
    repo: str,
    lookback_days: int,
    metrics: list,
    items: list,
    tool: str | None,
    contributors: list,
) -> str:
    """Build a helpful fallback answer when LLM is unavailable."""
    message_lower = message.lower()
    
    # Check if asking about DORA metrics concepts
    if any(kw in message_lower for kw in ["what is", "what are", "explain", "define", "meaning"]):
        if "dora" in message_lower:
            return (
                "**DORA Metrics** are four key indicators of software delivery performance:\n\n"
                "1. **Deployment Frequency**: How often code is deployed to production\n"
                "2. **Lead Time for Changes**: Time from commit to production deployment\n"
                "3. **Change Failure Rate**: Percentage of deployments causing failures\n"
                "4. **Mean Time to Recovery (MTTR)**: Time to restore service after a failure\n\n"
                "Elite teams deploy multiple times per day with <1hr lead time, <15% failure rate, and <1hr recovery."
            )
        if "mcp" in message_lower or "model context protocol" in message_lower:
            return (
                "**MCP (Model Context Protocol)** is a protocol that allows AI models to securely access external tools and data sources.\n\n"
                "This dashboard uses MCP to:\n"
                "- Connect to GitHub and fetch repository data (commits, PRs, issues)\n"
                "- Act as a secure proxy between the dashboard and GitHub API\n"
                "- Enable AI-powered analysis of your engineering metrics"
            )
        if "lead time" in message_lower:
            return (
                "**Lead Time for Changes** measures the time from code commit to production deployment.\n\n"
                "Performance levels:\n"
                "- Elite: Less than 1 hour\n"
                "- High: 1 day to 1 week\n"
                "- Medium: 1 week to 1 month\n"
                "- Low: More than 1 month"
            )
        if "deployment frequency" in message_lower or "deploy" in message_lower:
            return (
                "**Deployment Frequency** measures how often code is deployed to production.\n\n"
                "Performance levels:\n"
                "- Elite: Multiple deploys per day\n"
                "- High: Once per day to once per week\n"
                "- Medium: Once per week to once per month\n"
                "- Low: Less than once per month"
            )
        if "change failure" in message_lower or "cfr" in message_lower:
            return (
                "**Change Failure Rate (CFR)** measures the percentage of deployments that cause failures.\n\n"
                "Performance levels:\n"
                "- Elite: 0-15%\n"
                "- High: 16-30%\n"
                "- Medium: 31-45%\n"
                "- Low: 46-100%"
            )
        if "mttr" in message_lower or "recovery" in message_lower:
            return (
                "**Mean Time to Recovery (MTTR)** measures how long it takes to restore service after a failure.\n\n"
                "Performance levels:\n"
                "- Elite: Less than 1 hour\n"
                "- High: Less than 1 day\n"
                "- Medium: 1 day to 1 week\n"
                "- Low: More than 1 week"
            )
    
    # Return data-based response if we have metrics
    if metrics:
        total_deps = sum(m.get("deployment_frequency", 0) for m in metrics)
        avg_lead = sum(m.get("avg_lead_time_minutes", 0) for m in metrics) / max(len(metrics), 1)
        avg_cfr = sum(m.get("change_failure_rate", 0) for m in metrics) / max(len(metrics), 1)
        return (
            f"**{repo}** - Last {lookback_days} days:\n\n"
            f"- Total Deployments: {total_deps}\n"
            f"- Avg Lead Time: {avg_lead:.1f} minutes\n"
            f"- Avg Change Failure Rate: {avg_cfr:.1%}\n"
            f"- Data points: {len(metrics)} days\n\n"
            f"*Note: For detailed analysis, configure an OpenAI API key.*"
        )
    
    if items:
        noun = "commits" if tool == "list_commits" else "PRs"
        top_authors = ", ".join([c["author"] for c in contributors[:3]]) if contributors else "N/A"
        return (
            f"Found **{len(items)} {noun}** in the last {lookback_days} days.\n\n"
            f"Top contributors: {top_authors}\n\n"
            f"*Run ingestion to compute DORA metrics, or configure an OpenAI API key for detailed analysis.*"
        )
    
    return f"No data available for {repo}. Try running ingestion first, or ask a general question about DORA metrics."


# ============================================================================
# BUSINESS OUTCOMES ENDPOINTS
# ============================================================================

@app.post("/business/metrics")
async def post_business_metrics(req: BusinessMetricsRequest, pool=Depends(pool_dep)):
    """Record business metrics for correlation with DORA metrics."""
    metrics_dict = req.model_dump(exclude={"org_id", "date"})
    await upsert_business_metrics(pool, req.org_id, req.date, metrics_dict)
    return {"message": "Business metrics recorded", "org_id": req.org_id, "date": str(req.date)}


@app.get("/business/metrics")
async def get_business_metrics_endpoint(
    org_id: str = "default",
    range_days: int = 30,
    pool=Depends(pool_dep)
):
    """Retrieve business metrics for the specified period."""
    if range_days < 1 or range_days > 365:
        raise HTTPException(status_code=400, detail="range_days must be between 1 and 365")
    
    metrics = await get_business_metrics(pool, org_id, range_days)
    return {
        "org_id": org_id,
        "range_days": range_days,
        "metrics": metrics
    }


@app.get("/business/correlations")
async def get_business_correlations(
    org_id: str = "default",
    range_days: int = 90,
    pool=Depends(pool_dep)
):
    """Compute correlations between DORA metrics and business outcomes.
    
    Returns correlation coefficients and actionable insights showing how
    engineering performance impacts business results.
    """
    if range_days < 7 or range_days > 365:
        raise HTTPException(status_code=400, detail="range_days must be between 7 and 365")
    
    result = await compute_correlations(pool, org_id, range_days)
    return result


@app.post("/business/impact")
async def calculate_impact(req: BusinessImpactRequest):
    """Calculate the estimated business impact of DORA metric improvements.
    
    Provides ROI estimates based on industry research and your specific context.
    """
    business_context = {}
    if req.annual_revenue:
        business_context["annual_revenue"] = req.annual_revenue
    if req.avg_incident_cost:
        business_context["avg_incident_cost"] = req.avg_incident_cost
    if req.engineer_hourly_rate:
        business_context["engineer_hourly_rate"] = req.engineer_hourly_rate
    if req.team_size:
        business_context["team_size"] = req.team_size
    
    impact = calculate_business_impact(
        req.dora_before,
        req.dora_after,
        business_context if business_context else None
    )
    return impact


@app.get("/business/performance-level")
async def get_performance_level(repo: str | None = None, range_days: int = 30, pool=Depends(pool_dep)):
    """Get DORA performance level classification (Elite, High, Medium, Low).
    
    Classifies your team's performance based on DORA research benchmarks.
    """
    if range_days < 1 or range_days > 180:
        raise HTTPException(status_code=400, detail="range_days must be between 1 and 180")
    
    if repo:
        query = """
        SELECT AVG(deployment_frequency) as deployment_frequency,
               AVG(avg_lead_time_minutes) as avg_lead_time_minutes,
               AVG(change_failure_rate) as change_failure_rate,
               AVG(mttr_minutes) as mttr_minutes
        FROM dora_metrics
        WHERE repo_id = $1 AND date >= (CURRENT_DATE - $2 * INTERVAL '1 day');
        """
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, repo, range_days)
    else:
        query = """
        SELECT AVG(deployment_frequency) as deployment_frequency,
               AVG(avg_lead_time_minutes) as avg_lead_time_minutes,
               AVG(change_failure_rate) as change_failure_rate,
               AVG(mttr_minutes) as mttr_minutes
        FROM dora_metrics
        WHERE date >= (CURRENT_DATE - $1 * INTERVAL '1 day');
        """
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, range_days)
    
    if not row or row["deployment_frequency"] is None:
        return {
            "status": "no_data",
            "message": "No DORA metrics available. Run ingestion first."
        }
    
    metrics = {
        "deployment_frequency": float(row["deployment_frequency"] or 0),
        "avg_lead_time_minutes": float(row["avg_lead_time_minutes"] or 0),
        "change_failure_rate": float(row["change_failure_rate"] or 0),
        "mttr_minutes": float(row["mttr_minutes"] or 0),
    }
    
    levels = get_dora_performance_level(metrics)
    
    return {
        "repo": repo or "all",
        "range_days": range_days,
        "metrics": metrics,
        "performance_levels": levels,
        "recommendations": _get_improvement_recommendations(levels)
    }


def _get_improvement_recommendations(levels: dict[str, str]) -> list[str]:
    """Generate improvement recommendations based on performance levels."""
    recommendations = []
    
    if levels.get("deployment_frequency") in ["Low", "Medium"]:
        recommendations.append(
            "Increase deployment frequency by implementing CI/CD pipelines and reducing batch sizes"
        )
    
    if levels.get("lead_time") in ["Low", "Medium"]:
        recommendations.append(
            "Reduce lead time through automated testing, trunk-based development, and smaller PRs"
        )
    
    if levels.get("change_failure_rate") in ["Low", "Medium"]:
        recommendations.append(
            "Lower change failure rate with better testing, feature flags, and canary deployments"
        )
    
    if levels.get("mttr") in ["Low", "Medium"]:
        recommendations.append(
            "Improve MTTR with better observability, runbooks, and incident response automation"
        )
    
    if levels.get("overall") == "Elite":
        recommendations.append(
            "Maintain elite performance by continuously investing in automation and developer experience"
        )
    
    return recommendations


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
