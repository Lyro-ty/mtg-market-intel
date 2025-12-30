"""
HTTP API client for MCP server.

Makes requests to the FastAPI backend for operations that should go through business logic.
"""
from typing import Any
import httpx

from mcp_server.config import config


class APIClient:
    """Async HTTP client for the FastAPI backend."""

    def __init__(self):
        self.base_url = config.api_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        """Make a GET request to the API."""
        client = await self._get_client()
        response = await client.get(f"/api{path}", params=params)
        response.raise_for_status()
        return response.json()

    async def post(self, path: str, json: dict | None = None) -> dict[str, Any]:
        """Make a POST request to the API."""
        client = await self._get_client()
        response = await client.post(f"/api{path}", json=json)
        response.raise_for_status()
        return response.json()

    async def health_check(self) -> dict[str, Any]:
        """Check API health."""
        try:
            client = await self._get_client()
            response = await client.get("/api/health")
            return {
                "healthy": response.status_code == 200,
                "status_code": response.status_code,
                "base_url": self.base_url,
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "base_url": self.base_url,
            }


# Global client instance
api_client = APIClient()
