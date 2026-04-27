"""Library service for importing downloads."""

import logging
import shutil
from pathlib import Path
from typing import TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_config
from ..models import Audiobook, Download
from ..models.download import DownloadStatus
from .transmission import TransmissionClient

logger = logging.getLogger(__name__)


class LibraryImportError(Exception):
    """Error during import operation."""

    pass


class TorrentInfo(TypedDict):
    """Torrent information needed for import."""

    download_dir: str
    name: str


async def import_download_to_library(
    download: Download,
    session: AsyncSession,
    delete_after_import: bool = True,
    torrent_info: TorrentInfo | None = None,
    transmission_client: TransmissionClient | None = None,
) -> Audiobook | None:
    """Import a completed download to the library.

    Args:
        download: The download to import (must have transmission_id).
        session: Database session.
        delete_after_import: Whether to delete the download record after import.
        torrent_info: Optional torrent info if already fetched (download_dir, name).
        transmission_client: Optional existing TransmissionClient to reuse.

    Returns:
        The created Audiobook, or None if import failed.

    Raises:
        ImportError: If import fails due to validation or file errors.
    """
    # Validate download has transmission_id
    if download.transmission_id is None:
        raise LibraryImportError("Download has no associated Transmission torrent")

    transmission = transmission_client or TransmissionClient()

    # Get torrent info if not provided
    if torrent_info is None:
        fetched_info = transmission.get_torrent(download.transmission_id)
        if fetched_info is None:
            raise LibraryImportError("Torrent not found in Transmission")
        torrent_info = TorrentInfo(
            download_dir=fetched_info["download_dir"],
            name=fetched_info["name"],
        )

    # Determine source path
    source_path = Path(torrent_info["download_dir"]) / torrent_info["name"]
    if not source_path.exists():
        raise LibraryImportError(f"Downloaded files not found at: {source_path}")

    # Get library path and move files
    config = get_config()
    library_path = Path(config.library.path)
    if not library_path.exists():
        library_path.mkdir(parents=True, exist_ok=True)

    # Use download title for the destination directory name
    # Sanitize the title to be filesystem-safe
    safe_title = "".join(
        c if c.isalnum() or c in " ._-" else "_" for c in download.title
    ).strip()
    if not safe_title:
        safe_title = "Untitled"
    dest_path = library_path / safe_title

    # Avoid overwriting existing files
    if dest_path.exists():
        counter = 1
        while dest_path.exists():
            dest_path = library_path / f"{safe_title} ({counter})"
            counter += 1

    # Move files to library
    try:
        shutil.move(str(source_path), str(dest_path))
    except Exception as e:
        raise LibraryImportError(f"Failed to move files: {e}")

    # Calculate size
    if dest_path.is_dir():
        size = sum(f.stat().st_size for f in dest_path.rglob("*") if f.is_file())
    else:
        size = dest_path.stat().st_size

    # Create Audiobook record
    audiobook = Audiobook(
        title=download.title,
        path=str(dest_path),
        size_bytes=size,
    )
    session.add(audiobook)
    await session.flush()

    # Remove torrent from Transmission (keep data since we moved it)
    transmission.remove_torrent(download.transmission_id, delete_data=False)

    if delete_after_import:
        # Delete the download record
        await session.delete(download)
    else:
        # Update download: status=COMPLETED, audiobook_id=new_id
        download.status = DownloadStatus.COMPLETED
        download.audiobook_id = audiobook.id

    await session.commit()
    await session.refresh(audiobook)

    logger.info(f"Imported '{download.title}' to library at {dest_path}")
    return audiobook
