"""Library service for importing downloads."""

import logging
import shutil
from pathlib import Path
from typing import TypedDict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_config
from ..models import Audiobook, Download
from ..models.download import DownloadStatus
from .transmission import TransmissionClient

logger = logging.getLogger(__name__)

# Audio file extensions to detect audiobook directories
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".m4b", ".flac", ".ogg", ".opus", ".wma", ".aac"}


def _is_audiobook_directory(path: Path) -> bool:
    """Check if a directory contains audio files (is an audiobook)."""
    if not path.is_dir():
        return False
    for f in path.iterdir():
        if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS:
            return True
    return False


def _sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename/directory name."""
    return "".join(c if c.isalnum() or c in " ._-" else "_" for c in name).strip() or "Unknown"


def _get_dest_path(library_path: Path, title: str, author: str | None) -> Path:
    """Get destination path for an audiobook, using author-based structure if available."""
    safe_title = _sanitize_filename(title)

    if author:
        # Author-based structure: /library/Author/Title/
        safe_author = _sanitize_filename(author)
        author_dir = library_path / safe_author
        return author_dir / safe_title
    else:
        # Flat structure: /library/Title/
        return library_path / safe_title


def _detect_multi_audiobook(source_path: Path) -> list[Path]:
    """Detect if a directory contains multiple audiobooks.

    Returns a list of audiobook directories. If the torrent is a single
    audiobook, returns [source_path]. If it contains multiple audiobook
    subdirectories, returns those.
    """
    if not source_path.is_dir():
        return [source_path]

    # Check if the root directory itself contains audio files
    root_has_audio = any(
        f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS
        for f in source_path.iterdir()
    )

    if root_has_audio:
        # Audio files in root = single audiobook
        return [source_path]

    # Check subdirectories for audio files
    audiobook_dirs = []
    for subdir in sorted(source_path.iterdir()):
        if subdir.is_dir() and _is_audiobook_directory(subdir):
            audiobook_dirs.append(subdir)

    # If we found multiple audiobook directories, return them
    if len(audiobook_dirs) > 1:
        logger.info(
            f"Detected multi-audiobook torrent with {len(audiobook_dirs)} audiobooks"
        )
        return audiobook_dirs

    # Otherwise treat the whole thing as one audiobook
    return [source_path]


class LibraryImportError(Exception):
    """Error during import operation."""

    pass


class TorrentInfo(TypedDict):
    """Torrent information needed for import."""

    download_dir: str
    name: str


async def _import_single_audiobook(
    source_path: Path,
    dest_path: Path,
    title: str,
    download: Download,
    session: AsyncSession,
) -> Audiobook | None:
    """Import a single audiobook directory to the library.

    Returns the created Audiobook, or None if skipped as duplicate.
    """
    # Calculate source size for duplicate detection
    if source_path.is_dir():
        source_size = sum(f.stat().st_size for f in source_path.rglob("*") if f.is_file())
    else:
        source_size = source_path.stat().st_size

    # Check for existing audiobook with same title
    normalized_title = title.lower().strip()
    existing = await session.execute(
        select(Audiobook).where(func.lower(Audiobook.title) == normalized_title)
    )
    existing_audiobook = existing.scalar_one_or_none()

    if existing_audiobook and existing_audiobook.size_bytes:
        size_diff = abs(existing_audiobook.size_bytes - source_size) / max(source_size, 1)
        if size_diff < 0.01:
            logger.info(f"Skipping duplicate: '{title}' already exists in library")
            return None

    # If destination exists but no DB entry, it's orphaned - remove it first
    if dest_path.exists():
        logger.warning(f"Removing orphaned path: {dest_path}")
        if dest_path.is_dir():
            shutil.rmtree(dest_path)
        else:
            dest_path.unlink()

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
        title=title,
        path=str(dest_path),
        size_bytes=size,
        author=download.metadata_author,
        narrator=download.metadata_narrator,
        description=download.metadata_description,
        duration_seconds=download.metadata_duration_seconds,
        cover_image_url=download.metadata_cover_url,
        asin=download.metadata_asin,
        open_library_key=download.metadata_open_library_key,
        series_name=download.metadata_series_name,
        series_position=download.metadata_series_position,
        language=download.metadata_language,
        indexer=download.indexer,
        source_url=download.source_url,
        added_by_id=download.added_by_id,
    )
    session.add(audiobook)
    await session.flush()

    logger.info(f"Imported '{title}' to library at {dest_path}")
    return audiobook


async def import_download_to_library(
    download: Download,
    session: AsyncSession,
    delete_after_import: bool = True,
    torrent_info: TorrentInfo | None = None,
    transmission_client: TransmissionClient | None = None,
) -> list[Audiobook]:
    """Import a completed download to the library.

    Automatically detects multi-audiobook torrents (like series) and splits
    them into separate audiobook entries.

    Args:
        download: The download to import (must have transmission_id).
        session: Database session.
        delete_after_import: Whether to delete the download record after import.
        torrent_info: Optional torrent info if already fetched (download_dir, name).
        transmission_client: Optional existing TransmissionClient to reuse.

    Returns:
        List of created Audiobooks (may be multiple for series torrents).

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

    # Get library path
    config = get_config()
    library_path = Path(config.library.path)
    if not library_path.exists():
        library_path.mkdir(parents=True, exist_ok=True)

    # Detect if this is a multi-audiobook torrent
    audiobook_dirs = _detect_multi_audiobook(source_path)
    is_multi = len(audiobook_dirs) > 1

    imported_audiobooks: list[Audiobook] = []

    if is_multi:
        logger.info(
            f"Splitting multi-audiobook torrent '{download.title}' into "
            f"{len(audiobook_dirs)} separate audiobooks"
        )

        for audiobook_dir in audiobook_dirs:
            # Use the subdirectory name as the title
            title = audiobook_dir.name

            # Use author-based structure if author is available from metadata
            dest_path = _get_dest_path(library_path, title, download.metadata_author)

            # Ensure parent directory exists (for author-based structure)
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            audiobook = await _import_single_audiobook(
                source_path=audiobook_dir,
                dest_path=dest_path,
                title=title,
                download=download,
                session=session,
            )
            if audiobook:
                imported_audiobooks.append(audiobook)

        # Clean up the now-empty parent directory
        if source_path.exists() and source_path.is_dir():
            try:
                # Only remove if empty
                remaining = list(source_path.iterdir())
                if not remaining:
                    source_path.rmdir()
                else:
                    # If there are leftover files, move the whole thing too
                    logger.warning(f"Leftover files in {source_path}, moving to library")
                    extras_path = _get_dest_path(
                        library_path, f"{download.title}_extras", download.metadata_author
                    )
                    extras_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(source_path), str(extras_path))
            except Exception as e:
                logger.warning(f"Could not clean up source directory: {e}")

    else:
        # Single audiobook - import normally
        # Use author-based structure if author is available from metadata
        dest_path = _get_dest_path(library_path, download.title, download.metadata_author)

        # Ensure parent directory exists (for author-based structure)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        audiobook = await _import_single_audiobook(
            source_path=source_path,
            dest_path=dest_path,
            title=download.title,
            download=download,
            session=session,
        )
        if audiobook:
            imported_audiobooks.append(audiobook)

    # Remove torrent from Transmission (keep data since we moved it)
    transmission.remove_torrent(download.transmission_id, delete_data=False)

    if delete_after_import:
        await session.delete(download)
    else:
        download.status = DownloadStatus.COMPLETED
        # Link to first audiobook if any were imported
        if imported_audiobooks:
            download.audiobook_id = imported_audiobooks[0].id

    await session.commit()

    # Refresh all audiobooks
    for audiobook in imported_audiobooks:
        await session.refresh(audiobook)

    return imported_audiobooks
