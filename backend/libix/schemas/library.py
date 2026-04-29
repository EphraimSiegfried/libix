"""Library-related schemas."""

from datetime import date, datetime

from pydantic import BaseModel


class UserInfo(BaseModel):
    """Minimal user info for display."""

    id: int
    username: str

    model_config = {"from_attributes": True}


class AudiobookResponse(BaseModel):
    """Audiobook response."""

    id: int
    title: str
    author: str | None
    narrator: str | None
    description: str | None
    path: str
    size_bytes: int | None
    duration_seconds: int | None
    cover_image_url: str | None
    asin: str | None
    open_library_key: str | None
    series_name: str | None
    series_position: str | None
    release_date: date | None
    language: str | None
    indexer: str | None
    source_url: str | None
    added_by: UserInfo | None
    added_at: datetime

    model_config = {"from_attributes": True}
