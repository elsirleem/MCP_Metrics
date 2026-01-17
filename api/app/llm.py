"""Optional LLM helpers for chat and insights.

This module is resilient: if no API key or dependency is available, it quietly
returns ``None`` so callers can fall back to heuristic responses.
"""
from __future__ import annotations

import json
import os
from typing import Any, Sequence

try:  # pragma: no cover - optional dependency
    from openai import AsyncOpenAI
except Exception:  # pragma: no cover - optional dependency
    AsyncOpenAI = None


# Domain knowledge about DORA metrics, MCP, and engineering productivity
SYSTEM_KNOWLEDGE = """You are an expert engineering productivity assistant for the Technical Metrics Observation Dashboard.

## DORA Metrics Knowledge
DORA (DevOps Research and Assessment) metrics are four key indicators of software delivery performance:

1. **Deployment Frequency (DF)**: How often code is deployed to production.
   - Elite: Multiple deploys per day
   - High: Once per day to once per week
   - Medium: Once per week to once per month
   - Low: Less than once per month

2. **Lead Time for Changes**: Time from code commit to production deployment.
   - Elite: Less than 1 hour
   - High: 1 day to 1 week
   - Medium: 1 week to 1 month
   - Low: More than 1 month

3. **Change Failure Rate (CFR)**: Percentage of deployments causing failures.
   - Elite: 0-15%
   - High: 16-30%
   - Medium: 31-45%
   - Low: 46-100%

4. **Mean Time to Recovery (MTTR)**: Time to restore service after a failure.
   - Elite: Less than 1 hour
   - High: Less than 1 day
   - Medium: 1 day to 1 week
   - Low: More than 1 week

## MCP (Model Context Protocol) Knowledge
MCP is a protocol that allows AI models to securely access external tools and data sources:
- This dashboard uses MCP to connect to GitHub and fetch repository data
- MCP tools used: list_commits, list_pull_requests, list_issues
- The MCP server acts as a secure proxy between the dashboard and GitHub API

## Risk Indicators
- **Bus Factor Risk**: Flagged when one contributor makes >80% of commits (over-reliance on single developer)
- **High CFR**: Change failure rate above 30% indicates quality issues
- **Slow Lead Time**: Lead times over 1 week may indicate process bottlenecks

## How This Dashboard Works
1. **Ingestion**: Fetches GitHub data (PRs, commits) via MCP
2. **DORA Calculation**: Computes metrics from PR merge data
3. **Insights Generation**: AI-powered daily summaries with risk flags
4. **Chat**: Ask questions about your repository's engineering health

Be helpful, concise, and actionable. When discussing metrics, provide context on what good/bad looks like.
"""

import logging

logger = logging.getLogger(__name__)


def _client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY not set")
        return None
    if AsyncOpenAI is None:
        logger.warning("openai package not available")
        return None
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    return AsyncOpenAI(api_key=api_key), model


async def summarize_chat(
    message: str,
    tool: str | None = None,
    items: Sequence[dict[str, Any]] | None = None,
    metrics: Sequence[dict[str, Any]] | None = None,
    insights: Sequence[dict[str, Any]] | None = None,
    contributors: Sequence[dict[str, Any]] | None = None,
    repo: str | None = None,
    lookback_days: int | None = None,
) -> str | None:
    """Enhanced chat that understands DORA metrics, MCP, and repository context."""
    client_info = _client()
    if client_info is None:
        return None
    client, model = client_info
    
    # Build context from available data
    context_parts = []
    
    if repo:
        context_parts.append(f"Repository: {repo}")
    if lookback_days:
        context_parts.append(f"Lookback period: {lookback_days} days")
    
    # Include DORA metrics summary
    if metrics:
        recent_metrics = metrics[-7:] if len(metrics) > 7 else metrics
        total_deployments = sum(m.get("deployment_frequency", 0) for m in recent_metrics)
        avg_lead = sum(m.get("avg_lead_time_minutes", 0) for m in recent_metrics) / max(len(recent_metrics), 1)
        avg_cfr = sum(m.get("change_failure_rate", 0) for m in recent_metrics) / max(len(recent_metrics), 1)
        avg_mttr = sum(m.get("mttr_minutes", 0) for m in recent_metrics) / max(len(recent_metrics), 1)
        context_parts.append(f"""
DORA Metrics (recent {len(recent_metrics)} days):
- Total Deployments: {total_deployments}
- Avg Lead Time: {avg_lead:.1f} minutes
- Avg Change Failure Rate: {avg_cfr:.2%}
- Avg MTTR: {avg_mttr:.1f} minutes
""")
    
    # Include insights
    if insights:
        insight_summaries = [f"- {i.get('date')}: {i.get('summary_text', '')[:100]}" for i in insights[:3]]
        context_parts.append(f"Recent Insights:\n" + "\n".join(insight_summaries))
    
    # Include contributor info
    if contributors:
        top_contribs = contributors[:5] if len(contributors) > 5 else contributors
        contrib_str = ", ".join([f"{c.get('author')} ({c.get('commit_count')} commits)" for c in top_contribs])
        context_parts.append(f"Top Contributors: {contrib_str}")
    
    # Include GitHub data if available
    if items and tool:
        slim_items = []
        for item in (items or [])[:10]:
            slim_items.append({k: item.get(k) for k in ["title", "html_url", "user", "created_at", "merged_at", "author", "commit", "message"] if k in item})
        context_parts.append(f"GitHub Data ({tool}): {json.dumps(slim_items, default=str)}")
    
    context = "\n\n".join(context_parts) if context_parts else "No specific repository data available."
    
    messages = [
        {"role": "system", "content": SYSTEM_KNOWLEDGE},
        {"role": "user", "content": f"User Question: {message}\n\nContext:\n{context}"},
    ]
    
    try:
        resp = await client.chat.completions.create(
            model=model, 
            messages=messages, 
            temperature=0.4, 
            max_tokens=500
        )
        return resp.choices[0].message.content
    except Exception as e:
        logger.error(f"LLM chat error: {e}")
        return None


async def enhance_insight(
    repo: str,
    date: str,
    summary_text: str,
    metrics: dict[str, Any] | None,
    top_contributors: Sequence[dict[str, Any]] | None = None,
) -> str | None:
    client_info = _client()
    if client_info is None:
        return None
    client, model = client_info
    messages = [
        {"role": "system", "content": "Rewrite the summary to highlight notable patterns, keep it under 80 words."},
        {
            "role": "user",
            "content": (
                f"Repo: {repo}\nDate: {date}\nMetrics: {json.dumps(metrics or {}, default=str)}\n"
                f"Top contributors: {json.dumps(top_contributors or [], default=str)}\n"
                f"Current summary: {summary_text}"
            ),
        },
    ]
    try:
        resp = await client.chat.completions.create(model=model, messages=messages, temperature=0.4, max_tokens=180)
        return resp.choices[0].message.content
    except Exception:
        return None
