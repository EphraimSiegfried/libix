"""Download-related schemas."""

from datetime import datetime

from pydantic import BaseModel

from ..models.download import DownloadStatus


class DownloadCreate(BaseModel):
    """Request to add a download."""

    title: str
    download_url: str | None = None
    magnet_url: str | None = None
    info_url: str | None = None  # Link to the torrent page on the indexer
    indexer: str | None = None
    size: int | None = None
    # Metadata from search
    metadata_asin: str | None = None
    metadata_open_library_key: str | None = None
    metadata_author: str | None = None
    metadata_narrator: str | None = None
    metadata_description: str | None = None
    metadata_duration_seconds: int | None = None
    metadata_cover_url: str | None = None
    metadata_series_name: str | None = None
    metadata_series_position: str | None = None
    metadata_language: str | None = None


class DownloadResponse(BaseModel):
    """Download status response."""

    id: int
    title: str
    status: DownloadStatus
    progress: int
    size_bytes: int | None
    error_message: str | None
    indexer: str | None
    transmission_id: int | None
    audiobook_id: int | None
    metadata_asin: str | None
    metadata_open_library_key: str | None
    metadata_author: str | None
    metadata_narrator: str | None
    metadata_description: str | None
    metadata_duration_seconds: int | None
    metadata_cover_url: str | None
    metadata_series_name: str | None
    metadata_series_position: str | None
    metadata_language: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
