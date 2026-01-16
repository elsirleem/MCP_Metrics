"""Utilities to compute and persist DORA metrics from MCP GitHub data."""

from __future__ import annotations

import datetime as dt
from typing import Any, Iterable

import asyncpg


def _parse_datetime(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def compute_dora_from_prs(prs: Iterable[dict[str, Any]]) -> dict[dt.date, dict[str, float]]:
    """Return per-date DORA aggregates keyed by date with light heuristics.

    Heuristics (can be refined later):
    - change_failure_rate: PRs whose title contains "revert"/"rollback" or label contains
      any of {bug, incident, revert} divided by total merged that day.
    - mttr_minutes: average lead time of those failure PRs as a proxy for recovery speed.
    """

    per_day: dict[dt.date, dict[str, Any]] = {}
    for pr in prs:
        merged_at = _parse_datetime(pr.get("merged_at"))
        created_at = _parse_datetime(pr.get("created_at"))
        if not merged_at or not created_at:
            continue

        day = merged_at.date()
        lead_minutes = (merged_at - created_at).total_seconds() / 60.0

        title = (pr.get("title") or "").lower()
        labels = [l.get("name", "").lower() for l in pr.get("labels", [])]
        is_failure = any(keyword in title for keyword in ["revert", "rollback"]) or any(
            k in labels for k in ["bug", "incident", "revert", "rollback"]
        )

        bucket = per_day.setdefault(
            day,
            {
                "deployment_frequency": 0,
                "lead_times": [],
                "failure_count": 0,
                "failure_leads": [],
            },
        )

        bucket["deployment_frequency"] += 1
        bucket["lead_times"].append(lead_minutes)
        if is_failure:
            bucket["failure_count"] += 1
            bucket["failure_leads"].append(lead_minutes)

    # finalize averages
    finalized: dict[dt.date, dict[str, float]] = {}
    for day, vals in per_day.items():
        leads = vals.get("lead_times", [])
        avg_lead = sum(leads) / len(leads) if leads else 0.0
        failure_count = vals.get("failure_count", 0)
        deployment_freq = vals.get("deployment_frequency", 0) or 1  # avoid div/0
        cfr = failure_count / deployment_freq
        mttr = sum(vals.get("failure_leads", [])) / failure_count if failure_count else 0.0
        finalized[day] = {
            "deployment_frequency": float(vals.get("deployment_frequency", 0)),
            "avg_lead_time_minutes": avg_lead,
            "change_failure_rate": float(cfr),
            "mttr_minutes": float(mttr),
        }
    return finalized


async def upsert_dora_metrics(
    pool: asyncpg.pool.Pool,
    repo_id: str,
    metrics_per_day: dict[dt.date, dict[str, float]],
) -> None:
    if not metrics_per_day:
        return

    query = """
    INSERT INTO dora_metrics (
        repo_id, date, deployment_frequency, avg_lead_time_minutes, change_failure_rate, mttr_minutes
    ) VALUES ($1, $2, $3, $4, $5, $6)
    ON CONFLICT (repo_id, date) DO UPDATE SET
        deployment_frequency = EXCLUDED.deployment_frequency,
        avg_lead_time_minutes = EXCLUDED.avg_lead_time_minutes,
        change_failure_rate = EXCLUDED.change_failure_rate,
        mttr_minutes = EXCLUDED.mttr_minutes;
    """

    async with pool.acquire() as conn:
        async with conn.transaction():
            for day, vals in metrics_per_day.items():
                await conn.execute(
                    query,
                    repo_id,
                    day,
                    vals.get("deployment_frequency", 0.0),
                    vals.get("avg_lead_time_minutes", 0.0),
                    vals.get("change_failure_rate", 0.0),
                    vals.get("mttr_minutes", 0.0),
                )
