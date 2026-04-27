"""Search-related schemas."""

from pydantic import BaseModel


class SearchResult(BaseModel):
    """A single search result from Prowlarr."""

    guid: str
    title: str
    indexer: str
    size: int
    seeders: int
    leechers: int
    download_url: str | None = None
    magnet_url: str | None = None
    info_url: str | None = None
    publish_date: str | None = None
    categories: list[int] = []
