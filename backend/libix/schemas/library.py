"""Library-related schemas."""

from datetime import datetime

from pydantic import BaseModel


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
    added_at: datetime

    model_config = {"from_attributes": True}
