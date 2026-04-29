"""AudioBookBay scraper client."""

import logging
import re
from urllib.parse import urljoin

import httpx

from ..config import get_config
from ..schemas.search import SearchResult

logger = logging.getLogger(__name__)


class AudioBookBayClient:
    """Client for scraping AudioBookBay search results."""

    # Known AudioBookBay domains (they change frequently)
    DOMAINS = [
        "https://audiobookbay.lu",
        "https://audiobookbay.is",
        "https://audiobookbay.se",
        "https://audiobookbay.fi",
    ]

    def __init__(self) -> None:
        config = get_config()
        self.configured_url = config.audiobookbay.url.rstrip("/")
        self.enabled = config.audiobookbay.enabled

    def _get_headers(self) -> dict:
        """Get headers for requests."""
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

    def _clean_query(self, query: str) -> str:
        """Clean search query to avoid AudioBookBay quirks.

        AudioBookBay has issues with certain leading words like 'Die', 'The', etc.
        """
        # Strip common articles that cause issues
        articles = ["die ", "der ", "das ", "the ", "a ", "an "]
        query_lower = query.lower()
        for article in articles:
            if query_lower.startswith(article):
                query = query[len(article):]
                break
        return query.strip()

    def _parse_size(self, size_str: str) -> int:
        """Parse size string to bytes."""
        size_str = size_str.strip().upper()
        try:
            if "GB" in size_str:
                return int(float(size_str.replace("GB", "").strip()) * 1024 * 1024 * 1024)
            elif "MB" in size_str:
                return int(float(size_str.replace("MB", "").strip()) * 1024 * 1024)
            elif "KB" in size_str:
                return int(float(size_str.replace("KB", "").strip()) * 1024)
            else:
                return int(float(size_str))
        except (ValueError, AttributeError):
            return 0

    async def _try_search_on_domain(
        self, client: httpx.AsyncClient, base_url: str, query: str
    ) -> str | None:
        """Try to search on a specific domain, return HTML if successful."""
        try:
            # Visit homepage first to establish session
            await client.get(base_url, headers=self._get_headers())

            # Perform search using POST (AudioBookBay requires POST for search)
            headers = self._get_headers()
            headers["Referer"] = f"{base_url}/"
            response = await client.post(
                f"{base_url}/",
                data={"s": query},
                headers=headers,
            )

            # Check if search was successful by looking for query in page title
            # Homepage title: "Unabridged Audiobooks Free Online"
            # Search title: "<query> Audiobook" or "<query> Audiobooks"
            if response.status_code == 200:
                # Check if any word from the query appears in the page title
                first_word = query.split()[0].lower() if query else ""
                title_match = re.search(r"<title>([^<]+)</title>", response.text, re.IGNORECASE)
                if title_match and first_word in title_match.group(1).lower():
                    return response.text

            return None
        except Exception as e:
            logger.debug(f"Search failed on {base_url}: {e}")
            return None

    async def search(self, query: str, limit: int = 25) -> list[SearchResult]:
        """Search AudioBookBay for audiobooks.

        Args:
            query: Search query string.
            limit: Maximum number of results.

        Returns:
            List of search results.
        """
        if not self.enabled:
            return []

        results: list[SearchResult] = []

        # Clean query to avoid ABB quirks
        clean_query = self._clean_query(query)

        # Try configured URL first, then fallback domains
        urls_to_try = [self.configured_url] + [
            u for u in self.DOMAINS if u != self.configured_url
        ]

        html: str | None = None
        base_url: str = self.configured_url

        try:
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=30.0, verify=False
            ) as client:
                # Try each domain until one works
                for url in urls_to_try:
                    html = await self._try_search_on_domain(client, url, clean_query)
                    if html:
                        base_url = url
                        break

                if not html:
                    logger.warning("AudioBookBay search failed on all domains")
                    return []

                # Parse search results from HTML
                # AudioBookBay uses a specific HTML structure for search results
                # Look for post entries
                post_pattern = re.compile(
                    r'<div class="post"[^>]*>.*?'
                    r'<div class="postTitle">\s*<h2><a href="([^"]+)"[^>]*>([^<]+)</a>',
                    re.DOTALL
                )

                # Find all post entries
                posts = post_pattern.findall(html)

                for i, (href, title) in enumerate(posts[:limit]):
                    if not href or not title:
                        continue

                    # Clean up title
                    title = title.strip()
                    title = re.sub(r'\s+', ' ', title)

                    # Build full URL
                    info_url = urljoin(base_url, href)

                    # Try to extract size from the post content
                    size = 0
                    size_match = re.search(
                        rf'{re.escape(href)}.*?(?:Size|File Size)[:\s]*([0-9.]+\s*[KMGT]?B)',
                        html,
                        re.DOTALL | re.IGNORECASE
                    )
                    if size_match:
                        size = self._parse_size(size_match.group(1))

                    # Create a unique guid
                    guid = f"abb-{hash(info_url) & 0xFFFFFFFF:08x}"

                    results.append(SearchResult(
                        guid=guid,
                        title=title,
                        indexer="AudioBookBay",
                        size=size,
                        seeders=0,  # Not available from search page
                        leechers=0,
                        download_url=None,  # Requires visiting detail page
                        magnet_url=None,  # Will be fetched on demand
                        info_url=info_url,
                        publish_date=None,
                        categories=[3030],  # Audiobook category
                    ))

                # If we found results, try to get magnet links for top results
                if results:
                    # Fetch magnet links for first few results
                    for result in results[:min(5, len(results))]:
                        try:
                            magnet = await self._get_magnet_link(client, result.info_url)
                            if magnet:
                                result.magnet_url = magnet
                        except Exception as e:
                            logger.debug(f"Failed to get magnet for {result.title}: {e}")

        except httpx.HTTPError as e:
            logger.warning(f"AudioBookBay search failed: {e}")
        except Exception as e:
            logger.warning(f"AudioBookBay search error: {e}")

        return results

    async def _get_magnet_link(
        self, client: httpx.AsyncClient, info_url: str
    ) -> str | None:
        """Fetch the magnet link from an audiobook detail page.

        Args:
            client: HTTP client to use.
            info_url: URL of the audiobook detail page.

        Returns:
            Magnet link if found, None otherwise.
        """
        try:
            response = await client.get(info_url, headers=self._get_headers())
            response.raise_for_status()
            html = response.text

            # Look for magnet link
            magnet_match = re.search(r'href="(magnet:\?[^"]+)"', html)
            if magnet_match:
                return magnet_match.group(1)

            # Also check for info hash which we can convert to magnet
            hash_match = re.search(r'Info Hash:\s*</td>\s*<td[^>]*>([a-fA-F0-9]{40})', html)
            if hash_match:
                info_hash = hash_match.group(1).lower()
                return f"magnet:?xt=urn:btih:{info_hash}"

        except Exception as e:
            logger.debug(f"Failed to fetch magnet from {info_url}: {e}")

        return None

    async def get_magnet(self, info_url: str) -> str | None:
        """Get magnet link for a specific audiobook.

        Args:
            info_url: URL of the audiobook detail page.

        Returns:
            Magnet link if found.
        """
        if not self.enabled:
            return None

        async with httpx.AsyncClient(
            follow_redirects=True, timeout=30.0, verify=False
        ) as client:
            return await self._get_magnet_link(client, info_url)

    async def test_connection(self) -> tuple[bool, str, dict | None]:
        """Test connection to AudioBookBay.

        Returns:
            Tuple of (success, message, details).
        """
        if not self.enabled:
            return (False, "AudioBookBay is disabled in configuration.", None)

        urls_to_try = [self.configured_url] + [
            u for u in self.DOMAINS if u != self.configured_url
        ]

        try:
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=15.0, verify=False
            ) as client:
                for url in urls_to_try:
                    try:
                        response = await client.get(url, headers=self._get_headers())
                        if response.status_code == 200:
                            return (True, "Connected successfully.", {"url": url})
                    except Exception:
                        continue

            return (False, "No working AudioBookBay domain found.", None)

        except httpx.HTTPStatusError as e:
            return (False, f"HTTP error: {e.response.status_code}", None)
        except httpx.RequestError as e:
            return (False, f"Connection failed: {str(e)}", None)
        except Exception as e:
            return (False, f"Unexpected error: {str(e)}", None)
