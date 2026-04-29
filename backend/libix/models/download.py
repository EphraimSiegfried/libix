"""Download model for tracking downloads."""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class DownloadStatus(str, enum.Enum):
    """Download status enumeration."""

    PENDING = "pending"
    DOWNLOADING = "downloading"
    SEEDING = "seeding"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Download(Base):
    """Download model for tracking torrent downloads."""

    __tablename__ = "downloads"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    source_url: Mapped[str | None] = mapped_column(String(2000))  # Original download URL
    magnet_or_torrent: Mapped[str | None] = mapped_column(Text)  # Magnet link or torrent URL
    transmission_id: Mapped[int | None] = mapped_column(Integer, index=True)
    status: Mapped[DownloadStatus] = mapped_column(
        Enum(DownloadStatus), default=DownloadStatus.PENDING
    )
    progress: Mapped[int] = mapped_column(Integer, default=0)  # 0-100
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    indexer: Mapped[str | None] = mapped_column(String(100))
    added_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    audiobook_id: Mapped[int | None] = mapped_column(ForeignKey("audiobooks.id"))
    # Metadata fields from search
    metadata_asin: Mapped[str | None] = mapped_column(String(20))
    metadata_open_library_key: Mapped[str | None] = mapped_column(String(50))
    metadata_author: Mapped[str | None] = mapped_column(String(255))
    metadata_narrator: Mapped[str | None] = mapped_column(String(255))
    metadata_description: Mapped[str | None] = mapped_column(Text)
    metadata_duration_seconds: Mapped[int | None] = mapped_column(Integer)
    metadata_cover_url: Mapped[str | None] = mapped_column(String(2000))
    metadata_series_name: Mapped[str | None] = mapped_column(String(500))
    metadata_series_position: Mapped[str | None] = mapped_column(String(20))
    metadata_language: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    added_by = relationship("User", foreign_keys=[added_by_id])
    audiobook = relationship("Audiobook", foreign_keys=[audiobook_id])

    def __repr__(self) -> str:
        return f"<Download {self.title} ({self.status.value})>"
