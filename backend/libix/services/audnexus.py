"""Audiobook metadata clients for Audnexus and OpenLibrary."""

from datetime import date

import httpx
from pydantic import BaseModel

from ..config import get_config


class AudiobookMetadata(BaseModel):
    """Audiobook metadata from metadata APIs."""

    asin: str | None = None  # May be None for OpenLibrary results
    title: str
    author: str | None = None
    narrator: str | None = None
    description: str | None = None
    publisher: str | None = None
    duration_seconds: int | None = None
    release_date: date | None = None
    cover_url: str | None = None
    series_name: str | None = None
    series_position: str | None = None
    language: str | None = None
    # OpenLibrary specific
    open_library_key: str | None = None


class AudnexusClient:
    """Client for interacting with Audnexus API.

    Audnexus provides rich audiobook metadata given an ASIN.
    It does NOT support title-based search.
    """

    def __init__(self) -> None:
        config = get_config()
        self.base_url = config.audnexus.url.rstrip("/")
        self.enabled = config.audnexus.enabled

    # Regions to try when looking up ASINs
    REGIONS = ["us", "uk", "de", "fr", "au", "ca", "it", "es", "in", "jp"]

    async def get_by_asin(self, asin: str, region: str | None = None) -> AudiobookMetadata | None:
        """Get audiobook details by ASIN.

        Args:
            asin: The Audible ASIN identifier.
            region: Audible region. If None, tries multiple regions.

        Returns:
            Audiobook metadata or None if not found.
        """
        if not self.enabled:
            return None

        regions_to_try = [region] if region else self.REGIONS

        async with httpx.AsyncClient() as client:
            for r in regions_to_try:
                try:
                    response = await client.get(
                        f"{self.base_url}/books/{asin}",
                        params={"region": r},
                        timeout=30.0,
                    )
                    if response.status_code == 404:
                        continue

                    response.raise_for_status()
                    data = response.json()

                    # Check if we got an error response (region unavailable)
                    if "error" in data:
                        continue

                    # Check if we got valid data
                    if data.get("title"):
                        return self._parse_book(data)

                except httpx.HTTPStatusError:
                    continue

        return None

    def _parse_book(self, data: dict) -> AudiobookMetadata | None:
        """Parse a book response into AudiobookMetadata."""
        asin = data.get("asin")
        title = data.get("title")
        if not title:
            return None

        # Parse authors
        author = None
        authors = data.get("authors")
        if authors:
            if isinstance(authors, list) and len(authors) > 0:
                author_names = [a.get("name", "") for a in authors if isinstance(a, dict)]
                author = ", ".join(filter(None, author_names))
            elif isinstance(authors, str):
                author = authors

        # Parse narrators
        narrator = None
        narrators = data.get("narrators")
        if narrators:
            if isinstance(narrators, list) and len(narrators) > 0:
                narrator_names = [n.get("name", "") for n in narrators if isinstance(n, dict)]
                narrator = ", ".join(filter(None, narrator_names))
            elif isinstance(narrators, str):
                narrator = narrators

        # Parse series info
        series_name = None
        series_position = None
        series_primary = data.get("seriesPrimary")
        if series_primary:
            series_name = series_primary.get("name")
            series_position = series_primary.get("position")

        # Parse duration (Audnexus returns runtime in minutes)
        duration_seconds = None
        runtime = data.get("runtimeLengthMin")
        if runtime:
            duration_seconds = int(runtime) * 60

        # Parse release date
        release_date = None
        release_str = data.get("releaseDate")
        if release_str:
            try:
                release_date = date.fromisoformat(release_str[:10])
            except (ValueError, TypeError):
                pass

        return AudiobookMetadata(
            asin=asin,
            title=title,
            author=author,
            narrator=narrator,
            description=data.get("summary"),
            publisher=data.get("publisherName"),
            duration_seconds=duration_seconds,
            release_date=release_date,
            cover_url=data.get("image"),
            series_name=series_name,
            series_position=series_position,
            language=data.get("language"),
        )

    async def test_connection(self) -> tuple[bool, str, dict | None]:
        """Test connection to Audnexus."""
        if not self.enabled:
            return (False, "Audnexus is disabled in configuration.", None)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/health",
                    timeout=10.0,
                )
                response.raise_for_status()
                return (True, "Connected successfully.", None)
        except httpx.HTTPStatusError as e:
            return (False, f"HTTP error: {e.response.status_code}", None)
        except httpx.RequestError as e:
            return (False, f"Connection failed: {str(e)}", None)
        except Exception as e:
            return (False, f"Unexpected error: {str(e)}", None)


class OpenLibraryClient:
    """Client for OpenLibrary API for book metadata search."""

    BASE_URL = "https://openlibrary.org"
    COVERS_URL = "https://covers.openlibrary.org"

    async def get_by_key(self, key: str) -> AudiobookMetadata | None:
        """Get book metadata by OpenLibrary work key.

        Args:
            key: OpenLibrary work key (e.g., /works/OL82586W or OL82586W).

        Returns:
            Audiobook metadata or None if not found.
        """
        # Normalize key format
        if not key.startswith("/works/"):
            key = f"/works/{key}"

        async with httpx.AsyncClient() as client:
            try:
                # Fetch work details
                response = await client.get(
                    f"{self.BASE_URL}{key}.json",
                    timeout=30.0,
                )
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                work = response.json()

                title = work.get("title")
                if not title:
                    return None

                # Get description
                description = None
                desc_data = work.get("description")
                if desc_data:
                    if isinstance(desc_data, str):
                        description = desc_data
                    elif isinstance(desc_data, dict):
                        description = desc_data.get("value")

                # Get cover URL from cover IDs
                cover_url = None
                covers = work.get("covers", [])
                if covers:
                    cover_url = f"{self.COVERS_URL}/b/id/{covers[0]}-L.jpg"

                # Get author names - need to fetch author details
                author = None
                authors = work.get("authors", [])
                if authors:
                    author_keys = []
                    for a in authors:
                        if isinstance(a, dict):
                            author_key = a.get("author", {}).get("key")
                            if author_key:
                                author_keys.append(author_key)

                    # Fetch first 3 authors
                    author_names = []
                    for author_key in author_keys[:3]:
                        try:
                            author_resp = await client.get(
                                f"{self.BASE_URL}{author_key}.json",
                                timeout=10.0,
                            )
                            if author_resp.status_code == 200:
                                author_data = author_resp.json()
                                name = author_data.get("name")
                                if name:
                                    author_names.append(name)
                        except Exception:
                            pass

                    if author_names:
                        author = ", ".join(author_names)

                # Get first publish date
                release_date = None
                first_publish = work.get("first_publish_date")
                if first_publish:
                    try:
                        # Try to parse year from various formats
                        import re
                        year_match = re.search(r'\d{4}', first_publish)
                        if year_match:
                            release_date = date(int(year_match.group()), 1, 1)
                    except (ValueError, TypeError):
                        pass

                return AudiobookMetadata(
                    asin=None,
                    title=title,
                    author=author,
                    narrator=None,  # OpenLibrary doesn't have narrator info
                    description=description,
                    publisher=None,
                    duration_seconds=None,
                    release_date=release_date,
                    cover_url=cover_url,
                    series_name=None,
                    series_position=None,
                    language=None,
                    open_library_key=key,
                )

            except httpx.HTTPStatusError:
                return None
            except Exception:
                return None

    async def search(self, query: str, limit: int = 20) -> list[AudiobookMetadata]:
        """Search for books by title/author.

        Args:
            query: Search query (title, author, or both).
            limit: Maximum number of results.

        Returns:
            List of audiobook metadata results.
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/search.json",
                params={"q": query, "limit": limit},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        results = []
        for doc in data.get("docs", []):
            metadata = self._parse_doc(doc)
            if metadata:
                results.append(metadata)

        return results

    def _parse_doc(self, doc: dict) -> AudiobookMetadata | None:
        """Parse an OpenLibrary search result."""
        title = doc.get("title")
        if not title:
            return None

        # Get author names
        author = None
        author_names = doc.get("author_name")
        if author_names and isinstance(author_names, list):
            author = ", ".join(author_names[:3])  # Limit to 3 authors

        # Get cover URL
        cover_url = None
        cover_id = doc.get("cover_i")
        if cover_id:
            cover_url = f"{self.COVERS_URL}/b/id/{cover_id}-L.jpg"

        # Get first publish year as release date
        release_date = None
        first_year = doc.get("first_publish_year")
        if first_year:
            try:
                release_date = date(int(first_year), 1, 1)
            except (ValueError, TypeError):
                pass

        # Get OpenLibrary key for potential later enrichment
        ol_key = doc.get("key")

        return AudiobookMetadata(
            asin=None,  # OpenLibrary doesn't have ASINs
            title=title,
            author=author,
            narrator=None,  # OpenLibrary doesn't have narrator info
            description=None,  # Not in search results
            publisher=doc.get("publisher", [None])[0] if doc.get("publisher") else None,
            duration_seconds=None,  # Not in OpenLibrary
            release_date=release_date,
            cover_url=cover_url,
            series_name=None,  # Would need additional lookup
            series_position=None,
            language=doc.get("language", [None])[0] if doc.get("language") else None,
            open_library_key=ol_key,
        )


class AudibleSearchClient:
    """Client to search Audible and find ASINs."""

    # Try multiple Audible domains to handle geo-redirects
    SEARCH_DOMAINS = [
        "https://www.audible.com",
        "https://www.audible.co.uk",
        "https://www.audible.de",
    ]

    def _clean_title(self, title: str) -> str:
        """Clean up a malformed title for better search results."""
        import re

        # Replace underscores and plus signs with spaces
        cleaned = title.replace("_", " ").replace("+", " ")

        # Remove common torrent/release suffixes
        patterns_to_remove = [
            r'\s*\([^)]*\)\s*$',  # Trailing parentheses like (miok), (M4B)
            r'\s*\[[^\]]*\]\s*$',  # Trailing brackets like [Audiobook]
            r'\s*-\s*\d{4}\s*$',  # Year suffix like - 2024
            r'\s+M4B\s*$',  # M4B suffix
            r'\s+MP3\s*$',  # MP3 suffix
            r'\s+by\s+.*$',  # "by Author" suffix
            r'\s+audiobook\s*$',  # Audiobook suffix
        ]

        for pattern in patterns_to_remove:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

        # Extract author from "Author - Title" format
        if ' - ' in cleaned:
            parts = cleaned.split(' - ', 1)
            # If first part looks like an author name (shorter), swap
            if len(parts[0]) < len(parts[1]):
                cleaned = parts[1]  # Use the title part

        # Clean up multiple spaces
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        return cleaned

    async def search_asin(
        self, title: str, author: str | None = None, limit: int = 5
    ) -> list[dict]:
        """Search Audible for audiobooks and return potential ASIN matches.

        Args:
            title: Book title to search for.
            author: Optional author name.
            limit: Maximum results to return.

        Returns:
            List of dicts with asin, title, author, narrator info.
        """
        import re

        # Clean up the title before searching
        cleaned_title = self._clean_title(title)

        query = cleaned_title
        if author:
            query = f"{cleaned_title} {author}"

        asins_found: list[str] = []

        async with httpx.AsyncClient(follow_redirects=False) as client:
            for domain in self.SEARCH_DOMAINS:
                try:
                    # First request - may redirect
                    response = await client.get(
                        f"{domain}/search",
                        params={"keywords": query},
                        headers={
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                            "Accept-Language": "en-US,en;q=0.5",
                        },
                        timeout=30.0,
                    )

                    # If redirected, follow but check if it's to a different domain's homepage
                    redirect_count = 0
                    while response.is_redirect and redirect_count < 5:
                        redirect_count += 1
                        location = response.headers.get("location", "")

                        # If redirecting to homepage (geo-redirect), skip this domain
                        if "ipRedirect" in location or location.endswith("/?"):
                            break

                        # Follow redirect
                        if location.startswith("/"):
                            location = f"{domain}{location}"
                        response = await client.get(
                            location,
                            headers={
                                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                                "Accept-Language": "en-US,en;q=0.5",
                            },
                            timeout=30.0,
                        )

                    # Check if we got search results (not a homepage redirect)
                    if response.status_code == 200 and "/search" in str(response.url):
                        html = response.text

                        # Parse ASINs from search results
                        asin_pattern = re.compile(r'["\'/](B[A-Z0-9]{9})["\'/]')
                        found = list(dict.fromkeys(asin_pattern.findall(html)))

                        if found:
                            asins_found = found[:limit]
                            break  # Got results, stop trying other domains

                except httpx.HTTPError:
                    continue

        # Return ASINs - metadata will be enriched from Audnexus
        return [{"asin": asin, "title": None, "author": None, "narrator": None} for asin in asins_found]


class MetadataClient:
    """Combined metadata client that uses OpenLibrary for search
    and Audnexus for ASIN-based enrichment.
    """

    def __init__(self) -> None:
        self.openlibrary = OpenLibraryClient()
        self.audnexus = AudnexusClient()
        self.audible = AudibleSearchClient()

    async def search(self, query: str) -> list[AudiobookMetadata]:
        """Search for audiobooks by title/author.

        Uses OpenLibrary for the search since Audnexus doesn't support title search.

        Args:
            query: Search query.

        Returns:
            List of audiobook metadata.
        """
        return await self.openlibrary.search(query)

    async def search_asin(
        self, title: str, author: str | None = None
    ) -> list[dict]:
        """Search for ASINs matching a title/author.

        Args:
            title: Book title.
            author: Optional author name.

        Returns:
            List of potential ASIN matches with metadata.
        """
        # First try Audible search
        results = await self.audible.search_asin(title, author)

        # Enrich results with Audnexus data
        enriched = []
        for result in results:
            asin = result["asin"]
            try:
                metadata = await self.audnexus.get_by_asin(asin)
                if metadata:
                    enriched.append({
                        "asin": asin,
                        "title": metadata.title,
                        "author": metadata.author,
                        "narrator": metadata.narrator,
                        "duration_seconds": metadata.duration_seconds,
                        "cover_url": metadata.cover_url,
                        "series_name": metadata.series_name,
                        "series_position": metadata.series_position,
                    })
                else:
                    enriched.append(result)
            except Exception:
                enriched.append(result)

        return enriched

    async def enrich_by_asin(self, asin: str) -> AudiobookMetadata | None:
        """Get enriched metadata by ASIN from Audnexus.

        Args:
            asin: Audible ASIN.

        Returns:
            Enriched metadata or None.
        """
        return await self.audnexus.get_by_asin(asin)
