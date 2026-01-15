import os
from typing import Any
import httpx


class MCPClient:
    """Thin HTTP client to talk to the GitHub MCP server tools."""

    def __init__(self, base_url: str | None = None, token: str | None = None) -> None:
        self.base_url = base_url or os.getenv("MCP_BASE_URL", "http://mcp:3001")
        self.token = token or os.getenv("GITHUB_PAT", "")

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def list_commits(self, repo: str, since: str | None = None) -> Any:
        url = f"{self.base_url}/list_commits"
        payload: dict[str, Any] = {"repo": repo}
        if since:
            payload["since"] = since
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=self._headers(), timeout=30)
            resp.raise_for_status()
            return resp.json()

    async def list_pull_requests(self, repo: str, state: str = "closed", since: str | None = None) -> Any:
        url = f"{self.base_url}/list_pull_requests"
        payload: dict[str, Any] = {"repo": repo, "state": state}
        if since:
            payload["since"] = since
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=self._headers(), timeout=30)
            resp.raise_for_status()
            return resp.json()

    async def list_issues(self, repo: str, state: str = "open", since: str | None = None) -> Any:
        url = f"{self.base_url}/list_issues"
        payload: dict[str, Any] = {"repo": repo, "state": state}
        if since:
            payload["since"] = since
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=self._headers(), timeout=30)
            resp.raise_for_status()
            return resp.json()
