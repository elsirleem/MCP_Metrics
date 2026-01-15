"""Lightweight insight generation and persistence helpers."""

from __future__ import annotations

import datetime as dt
from collections import Counter
from typing import Any, Iterable

import asyncpg


def generate_insight_summary(
    repo: str,
    metrics_per_day: dict[dt.date, dict[str, float]],
    prs: Iterable[dict[str, Any]],
    target_day: dt.date,
) -> tuple[str, list[str], list[dict[str, Any]]]:
    day_metrics = metrics_per_day.get(target_day, {})
    dep_freq = int(day_metrics.get("deployment_frequency", 0))
    lead = day_metrics.get("avg_lead_time_minutes", 0.0)

    # simple contributor tally from PR authors
    authors = [pr.get("user", {}).get("login") for pr in prs if pr.get("merged_at", "").startswith(str(target_day))]
    author_counts = Counter([a for a in authors if a])
    top_contrib = [
        {"author": name, "pr_count": count}
        for name, count in author_counts.most_common(5)
    ]

    risk_flags: list[str] = []
    if dep_freq == 0:
        risk_flags.append("no_deployments")
    if top_contrib and top_contrib[0]["pr_count"] / max(1, sum(author_counts.values())) >= 0.8:
        risk_flags.append("bus_factor")

    summary = (
        f"On {target_day}, repo {repo} merged {dep_freq} PR(s) with average lead time {lead:.1f} minutes. "
        f"Top contributors: {', '.join([c['author'] for c in top_contrib]) or 'n/a'}."
    )
    return summary, risk_flags, top_contrib


async def upsert_daily_insight(
    pool: asyncpg.pool.Pool,
    repo_id: str,
    date: dt.date,
    summary_text: str,
    risk_flags: list[str],
    top_contributors: list[dict[str, Any]],
) -> None:
    query = """
    INSERT INTO daily_insights (repo_id, date, summary_text, risk_flags, top_contributors)
    VALUES ($1, $2, $3, $4, $5)
    ON CONFLICT (repo_id, date) DO UPDATE SET
        summary_text = EXCLUDED.summary_text,
        risk_flags = EXCLUDED.risk_flags,
        top_contributors = EXCLUDED.top_contributors;
    """

    async with pool.acquire() as conn:
        await conn.execute(query, repo_id, date, summary_text, risk_flags, top_contributors)
