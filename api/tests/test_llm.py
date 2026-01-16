import pytest

from app import llm


@pytest.mark.asyncio
async def test_summarize_chat_returns_none_without_client(monkeypatch):
    # Force _client to return None
    monkeypatch.setenv("OPENAI_API_KEY", "")
    result = await llm.summarize_chat("msg", "tool", [])
    assert result is None


@pytest.mark.asyncio
async def test_enhance_insight_returns_none_without_client(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    result = await llm.enhance_insight("repo", "2024-01-01", "summary", {}, [])
    assert result is None
