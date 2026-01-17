import os
from typing import Any
import httpx


class MCPClient:
    """Thin HTTP client to talk to the GitHub MCP server tools."""

    def __init__(self, base_url: str | None = None, token: str | None = None) -> None:
        self.base_url = base_url or os.getenv("MCP_BASE_URL", "http://mcp:3001")
        self.default_token = token or os.getenv("GITHUB_PAT", "")

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        return headers

    async def _post_json(self, url: str, payload: dict[str, Any], timeout: int = 30, token: str | None = None) -> Any:
        # If a token is provided, include it in the payload for MCP server to use
        if token:
            payload = {**payload, "token": token}
        elif self.default_token:
            payload = {**payload, "token": self.default_token}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, headers=self._headers(), timeout=timeout)
                resp.raise_for_status()
                return resp.json()
        except Exception:
            # Keep API resilient: callers can detect empty list/dict and fall back.
            return []

    async def health(self) -> bool:
        url = f"{self.base_url}/health"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                return data.get("status") == "ok"
        except Exception:
            return False

    async def list_commits(self, repo: str, since: str | None = None, token: str | None = None) -> Any:
        url = f"{self.base_url}/list_commits"
        payload: dict[str, Any] = {"repo": repo}
        if since:
            payload["since"] = since
        return await self._post_json(url, payload, token=token)

    async def list_pull_requests(self, repo: str, state: str = "closed", since: str | None = None, token: str | None = None) -> Any:
        url = f"{self.base_url}/list_pull_requests"
        payload: dict[str, Any] = {"repo": repo, "state": state}
        if since:
            payload["since"] = since
        return await self._post_json(url, payload, token=token)

    async def list_issues(self, repo: str, state: str = "open", since: str | None = None, token: str | None = None) -> Any:
        url = f"{self.base_url}/list_issues"
        payload: dict[str, Any] = {"repo": repo, "state": state}
        if since:
            payload["since"] = since
        return await self._post_json(url, payload, token=token)
