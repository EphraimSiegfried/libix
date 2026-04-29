"""Metadata-related schemas for audiobook search."""

from datetime import date

from pydantic import BaseModel


class MetadataSearchResult(BaseModel):
    """A single audiobook metadata result from search."""

    asin: str | None = None  # Audible ASIN (starts with B)
    open_library_key: str | None = None  # OpenLibrary work key (e.g., /works/OL123W)
    title: str
    author: str | None = None
    narrator: str | None = None
    description: str | None = None
    duration_seconds: int | None = None
    release_date: date | None = None
    cover_url: str | None = None
    series_name: str | None = None
    series_position: str | None = None
    language: str | None = None


class MetadataSearchResponse(BaseModel):
    """Response wrapper for metadata search results."""

    results: list[MetadataSearchResult]
    query: str


class TorrentSearchRequest(BaseModel):
    """Request for stage 2 torrent search."""

    title: str
    author: str | None = None
    asin: str | None = None


class EnrichedDownloadCreate(BaseModel):
    """Request to add a download with metadata attached."""

    title: str
    download_url: str | None = None
    magnet_url: str | None = None
    indexer: str | None = None
    size: int | None = None
    # Metadata from Audnexus
    metadata_asin: str | None = None
    metadata_author: str | None = None
    metadata_narrator: str | None = None
    metadata_description: str | None = None
    metadata_duration_seconds: int | None = None
    metadata_cover_url: str | None = None
    metadata_series_name: str | None = None
    metadata_series_position: str | None = None
