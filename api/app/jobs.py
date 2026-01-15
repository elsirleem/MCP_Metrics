"""Background job helpers for daily ingestion + insights (FR007)."""

from __future__ import annotations

import asyncio
import datetime as dt
import os
from typing import Sequence

from app.dora import compute_dora_from_prs, upsert_dora_metrics
from app.insights import generate_insight_summary, upsert_daily_insight
from app.mcp_client import MCPClient
from app.db import init_pool


async def run_daily_ingestion(repositories: Sequence[str], lookback_days: int = 1):
    mcp_client = MCPClient()
    pool = await init_pool()
    since_dt = dt.datetime.utcnow() - dt.timedelta(days=lookback_days)
    since_iso = since_dt.isoformat() + "Z"

    async with pool.acquire() as conn:
        for repo in repositories:
            raw_prs = await mcp_client.list_pull_requests(repo=repo, state="closed", since=since_iso)
            prs = raw_prs if isinstance(raw_prs, list) else raw_prs.get("items", [])
            metrics_per_day = compute_dora_from_prs(prs)
            await upsert_dora_metrics(pool, repo, metrics_per_day)
            if metrics_per_day:
                latest_day = max(metrics_per_day.keys())
                insight_text, risk_flags, top_contrib = generate_insight_summary(repo, metrics_per_day, prs, latest_day)
                await upsert_daily_insight(pool, repo, latest_day, insight_text, risk_flags, top_contrib)


def main():
    repos_env = os.getenv("INGEST_REPOSITORIES", "")
    if not repos_env:
        raise SystemExit("Set INGEST_REPOSITORIES as comma-separated list, e.g., owner1/repo1,owner2/repo2")
    repositories = [r.strip() for r in repos_env.split(",") if r.strip()]
    lookback_days = int(os.getenv("INGEST_LOOKBACK_DAYS", "1"))
    asyncio.run(run_daily_ingestion(repositories, lookback_days=lookback_days))


if __name__ == "__main__":
    main()
