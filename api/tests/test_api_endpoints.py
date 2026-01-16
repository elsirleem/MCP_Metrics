import datetime as dt
import pytest
import pytest_asyncio
import httpx

from app import main


class _FakeConn:
    def __init__(self, pool):
        self.pool = pool

    async def fetch(self, query, *args):
        return self.pool.fetch_result

    async def execute(self, query, *args):
        self.pool.executed.append((query, args))
        return None

    def transaction(self):
        class _Txn:
            async def __aenter__(self_inner):
                return self

            async def __aexit__(self_inner, exc_type, exc, tb):
                return False

        return _Txn()


class _Acquire:
    def __init__(self, pool):
        self.pool = pool
        self.conn = _FakeConn(pool)

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakePool:
    def __init__(self):
        self.fetch_result = []
        self.executed = []

    def acquire(self):
        return _Acquire(self)


class StubMCP:
    def __init__(self):
        self.prs = []
        self.commits = []

    async def list_pull_requests(self, repo: str, state: str = "closed", since: str | None = None):
        return self.prs

    async def list_commits(self, repo: str, since: str | None = None):
        return self.commits

    async def health(self):
        return True


@pytest_asyncio.fixture
async def client(monkeypatch):
    fake_pool = FakePool()
    stub = StubMCP()
    main.app.dependency_overrides[main.pool_dep] = lambda: fake_pool
    main.app.state.pool = fake_pool
    main.mcp_client = stub

    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, fake_pool, stub


@pytest.mark.asyncio
async def test_ingest_and_metrics_flow(client):
    ac, pool, stub = client
    stub.prs = [
        {
            "title": "Add feature",
            "created_at": "2024-01-01T00:00:00Z",
            "merged_at": "2024-01-02T00:00:00Z",
            "labels": [],
        }
    ]
    resp = await ac.post("/ingest", json={"repositories": ["owner/repo"], "lookback_days": 7})
    assert resp.status_code == 200
    # upsert_dora_metrics and upsert_daily_insight should have executed writes
    assert pool.executed, "expected DB writes during ingest"

    # mock stored metrics for read-back
    pool.fetch_result = [
        {
            "date": dt.date(2024, 1, 2),
            "deployment_frequency": 1,
            "avg_lead_time_minutes": 60.0,
            "change_failure_rate": 0.0,
            "mttr_minutes": 0.0,
        }
    ]
    resp = await ac.get("/metrics/dora", params={"repo": "owner/repo", "range_days": 7})
    assert resp.status_code == 200
    data = resp.json()
    assert data["metrics"][0]["deployment_frequency"] == 1


@pytest.mark.asyncio
async def test_contributor_risk_and_chat_fallback(client, monkeypatch):
    ac, pool, stub = client
    stub.commits = [
        {"author": {"login": "alice"}},
        {"author": {"login": "alice"}},
        {"author": {"login": "alice"}},
        {"author": {"login": "alice"}},
        {"author": {"login": "bob"}},
    ]
    resp = await ac.get("/metrics/contributors", params={"repo": "owner/repo", "lookback_days": 7})
    data = resp.json()
    assert resp.status_code == 200
    assert data["risk_flags"] == ["bus_factor"]

    # chat falls back when summarize_chat returns None
    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(main, "summarize_chat", _noop)
    stub.prs = []
    resp = await ac.post("/chat", json={"repo": "owner/repo", "message": "show prs", "lookback_days": 7})
    assert resp.status_code == 200
    assert "Found" in resp.json()["answer"]


@pytest.mark.asyncio
async def test_daily_insights_listing(client):
    ac, pool, stub = client
    pool.fetch_result = [
        {
            "date": dt.date(2024, 1, 2),
            "summary_text": "Summary",
            "risk_flags": ["bus_factor"],
            "top_contributors": [{"author": "alice", "pr_count": 2}],
        }
    ]
    resp = await ac.get("/insights/daily", params={"repo": "owner/repo", "limit": 5})
    assert resp.status_code == 200
    assert resp.json()["insights"][0]["summary_text"] == "Summary"


@pytest.mark.asyncio
async def test_invalid_repo_rejected(client):
    ac, pool, stub = client
    resp = await ac.get("/metrics/dora", params={"repo": "badformat", "range_days": 7})
    assert resp.status_code == 400