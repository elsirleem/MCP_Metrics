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


def _client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or AsyncOpenAI is None:
        return None
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    return AsyncOpenAI(api_key=api_key), model


async def summarize_chat(message: str, tool: str, items: Sequence[dict[str, Any]] | None = None) -> str | None:
    client_info = _client()
    if client_info is None:
        return None
    client, model = client_info
    slim_items = []
    for item in (items or [])[:10]:
        slim_items.append({k: item.get(k) for k in ["title", "html_url", "user", "created_at", "merged_at", "author", "commit"] if k in item})
    prompt = (
        "You are a concise engineering assistant. Based on the provided MCP tool output, "
        "answer the user's question with short, actionable insight. If data is empty, say that briefly."
    )
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"User message: {message}\nTool used: {tool}\nData: {json.dumps(slim_items, default=str)}"},
    ]
    try:
        resp = await client.chat.completions.create(model=model, messages=messages, temperature=0.3, max_tokens=240)
        return resp.choices[0].message.content
    except Exception:
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
