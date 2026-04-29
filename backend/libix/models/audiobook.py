"""Audiobook model for library management."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class Audiobook(Base):
    """Audiobook model representing items in the library."""

    __tablename__ = "audiobooks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(500), index=True)
    author: Mapped[str | None] = mapped_column(String(255), index=True)
    narrator: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    path: Mapped[str] = mapped_column(String(1000), unique=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    cover_image_url: Mapped[str | None] = mapped_column(String(2000))
    asin: Mapped[str | None] = mapped_column(String(20), index=True)
    open_library_key: Mapped[str | None] = mapped_column(String(50), index=True)
    series_name: Mapped[str | None] = mapped_column(String(500))
    series_position: Mapped[str | None] = mapped_column(String(20))
    release_date: Mapped[date | None] = mapped_column(Date)
    language: Mapped[str | None] = mapped_column(String(50))
    indexer: Mapped[str | None] = mapped_column(String(100))  # Torrent source
    source_url: Mapped[str | None] = mapped_column(String(2000))  # Original torrent URL
    added_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    added_by = relationship("User", foreign_keys=[added_by_id])

    def __repr__(self) -> str:
        return f"<Audiobook {self.title} by {self.author}>"
