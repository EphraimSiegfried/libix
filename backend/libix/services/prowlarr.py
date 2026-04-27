"""Prowlarr API client."""

import httpx

from ..config import get_config
from ..schemas.search import SearchResult


class ProwlarrClient:
    """Client for interacting with Prowlarr API."""

    def __init__(self) -> None:
        config = get_config()
        self.base_url = config.prowlarr.url.rstrip("/")
        self.api_key = config.prowlarr.get_api_key()
        self.categories = config.prowlarr.categories
        self.limit = config.prowlarr.limit

    def _get_headers(self) -> dict:
        """Get headers for API requests."""
        return {
            "X-Api-Key": self.api_key or "",
            "Accept": "application/json",
        }

    async def search(self, query: str, categories: list[int] | None = None) -> list[SearchResult]:
        """Search for releases.

        Args:
            query: Search query string.
            categories: Optional list of category IDs to filter by.

        Returns:
            List of search results.
        """
        if categories is None:
            categories = self.categories

        params = {
            "query": query,
            "limit": self.limit,
        }
        if categories:
            params["categories"] = ",".join(str(c) for c in categories)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/search",
                headers=self._get_headers(),
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        results = []
        for item in data:
            result = SearchResult(
                guid=item.get("guid", ""),
                title=item.get("title", ""),
                indexer=item.get("indexer", ""),
                size=item.get("size", 0),
                seeders=item.get("seeders", 0),
                leechers=item.get("leechers", 0),
                download_url=item.get("downloadUrl"),
                magnet_url=item.get("magnetUrl"),
                info_url=item.get("infoUrl"),
                publish_date=item.get("publishDate"),
                categories=[c.get("id", 0) for c in item.get("categories", [])],
            )
            results.append(result)

        return results

    async def get_indexers(self) -> list[dict]:
        """Get list of configured indexers.

        Returns:
            List of indexer information.
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/indexer",
                headers=self._get_headers(),
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()

    async def test_connection(self) -> tuple[bool, str, dict | None]:
        """Test connection to Prowlarr.

        Returns:
            Tuple of (success, message, details).
        """
        try:
            indexers = await self.get_indexers()
            return (
                True,
                f"Connected successfully. Found {len(indexers)} indexer(s).",
                {"indexer_count": len(indexers)},
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                return (False, "Authentication failed. Check your API key.", None)
            return (False, f"HTTP error: {e.response.status_code}", None)
        except httpx.RequestError as e:
            return (False, f"Connection failed: {str(e)}", None)
        except Exception as e:
            return (False, f"Unexpected error: {str(e)}", None)
