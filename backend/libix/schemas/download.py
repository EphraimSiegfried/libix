"""Download-related schemas."""

from datetime import datetime

from pydantic import BaseModel

from ..models.download import DownloadStatus


class DownloadCreate(BaseModel):
    """Request to add a download."""

    title: str
    download_url: str | None = None
    magnet_url: str | None = None
    indexer: str | None = None
    size: int | None = None


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
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
