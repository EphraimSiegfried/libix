"""Library management router."""

import logging
import shutil
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..config import get_config
from ..database import get_session
from ..models import Audiobook, Download, User
from ..models.download import DownloadStatus
from ..schemas.library import AudiobookResponse
from ..services import LibraryImportError, import_download_to_library
from ..services.audnexus import MetadataClient, OpenLibraryClient
from .auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/library", tags=["library"])


@router.get("", response_model=list[AudiobookResponse])
async def list_audiobooks(
    _current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[AudiobookResponse]:
    """List all audiobooks in the library."""
    result = await session.execute(
        select(Audiobook)
        .options(selectinload(Audiobook.added_by))
        .order_by(Audiobook.added_at.desc())
    )
    audiobooks = result.scalars().all()
    return [AudiobookResponse.model_validate(a) for a in audiobooks]


@router.get("/{audiobook_id}", response_model=AudiobookResponse)
async def get_audiobook(
    audiobook_id: int,
    _current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AudiobookResponse:
    """Get audiobook details."""
    result = await session.execute(
        select(Audiobook)
        .options(selectinload(Audiobook.added_by))
        .where(Audiobook.id == audiobook_id)
    )
    audiobook = result.scalar_one_or_none()
    if audiobook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audiobook not found",
        )
    return AudiobookResponse.model_validate(audiobook)


@router.delete("/{audiobook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_audiobook(
    audiobook_id: int,
    _current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    delete_files: Annotated[bool, Query()] = False,
) -> None:
    """Delete an audiobook from the library.

    Args:
        audiobook_id: The audiobook to delete.
        delete_files: If True, also delete the files from disk.
    """
    import shutil

    result = await session.execute(
        select(Audiobook).where(Audiobook.id == audiobook_id)
    )
    audiobook = result.scalar_one_or_none()
    if audiobook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audiobook not found",
        )

    if delete_files:
        path = Path(audiobook.path)
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()

    await session.delete(audiobook)
    await session.commit()


# Audio file extensions for detecting audiobook directories
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".m4b", ".flac", ".ogg", ".opus", ".wma", ".aac"}


def _is_audiobook_dir(path: Path) -> bool:
    """Check if a directory contains audio files (is an audiobook)."""
    for f in path.iterdir():
        if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS:
            return True
    return False


@router.post("/scan", status_code=status.HTTP_202_ACCEPTED)
async def scan_library(
    _current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Scan library directory and add new audiobooks.

    Supports both flat structure (/library/Title/) and author-based
    structure (/library/Author/Title/).
    """
    config = get_config()
    library_path = Path(config.library.path)

    if not library_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Library path does not exist: {library_path}",
        )

    added = 0
    skipped = 0

    # Collect all potential audiobook directories
    audiobook_dirs: list[tuple[Path, str | None]] = []  # (path, author or None)

    for item in library_path.iterdir():
        if not item.is_dir():
            continue

        if _is_audiobook_dir(item):
            # Flat structure: /library/Title/
            audiobook_dirs.append((item, None))
        else:
            # Might be an author directory, check subdirectories
            for subitem in item.iterdir():
                if subitem.is_dir() and _is_audiobook_dir(subitem):
                    # Author-based structure: /library/Author/Title/
                    audiobook_dirs.append((subitem, item.name))

    for audiobook_path, author in audiobook_dirs:
        # Check if already in database
        result = await session.execute(
            select(Audiobook).where(Audiobook.path == str(audiobook_path))
        )
        if result.scalar_one_or_none():
            skipped += 1
            continue

        # Calculate size
        size = sum(f.stat().st_size for f in audiobook_path.rglob("*") if f.is_file())

        # Add to database
        audiobook = Audiobook(
            title=audiobook_path.name,
            author=author,
            path=str(audiobook_path),
            size_bytes=size,
        )
        session.add(audiobook)
        added += 1

    await session.commit()
    return {"added": added, "skipped": skipped}


@router.post("/import/{download_id}", response_model=list[AudiobookResponse])
async def import_download_endpoint(
    download_id: int,
    _current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[AudiobookResponse]:
    """Import a completed download to the library.

    Moves files from download directory to library and creates Audiobook records.
    Multi-audiobook torrents (like series) are automatically split into separate entries.
    This endpoint is used for manual import when auto-import failed.
    """
    # Get the download
    result = await session.execute(
        select(Download).where(Download.id == download_id)
    )
    download = result.scalar_one_or_none()
    if download is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Download not found",
        )

    # Validate download is in SEEDING status (100% complete, auto-import failed)
    if download.status != DownloadStatus.SEEDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Download must be in SEEDING status to import (current: {download.status.value})",
        )

    try:
        audiobooks = await import_download_to_library(
            download, session, delete_after_import=True
        )
        return [AudiobookResponse.model_validate(ab) for ab in audiobooks]
    except LibraryImportError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


class AsinSearchResult(BaseModel):
    """ASIN search result."""

    asin: str
    title: str | None = None
    author: str | None = None
    narrator: str | None = None
    duration_seconds: int | None = None
    cover_url: str | None = None
    series_name: str | None = None
    series_position: str | None = None


@router.get("/{audiobook_id}/search-asin", response_model=list[AsinSearchResult])
async def search_asin_for_audiobook(
    audiobook_id: int,
    _current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[AsinSearchResult]:
    """Search for ASINs matching an audiobook's title/author."""
    result = await session.execute(
        select(Audiobook).where(Audiobook.id == audiobook_id)
    )
    audiobook = result.scalar_one_or_none()
    if audiobook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audiobook not found",
        )

    client = MetadataClient()
    try:
        results = await client.search_asin(audiobook.title, audiobook.author)
        return [AsinSearchResult(**r) for r in results]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ASIN search failed: {str(e)}",
        )


import re


def is_valid_asin(asin: str) -> bool:
    """Check if string is a valid Audible ASIN (starts with B, 10 alphanumeric chars)."""
    return bool(re.match(r'^B[A-Z0-9]{9}$', asin.upper()))


class SetAsinRequest(BaseModel):
    """Request to set ASIN and fetch metadata."""

    asin: str


def _sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename/directory name."""
    return "".join(c if c.isalnum() or c in " ._-" else "_" for c in name).strip() or "Unknown"


def _reorganize_audiobook_by_author(audiobook: Audiobook) -> bool:
    """Reorganize an audiobook into author-based folder structure.

    Moves from /library/Title/ to /library/Author/Title/

    Returns True if reorganization happened, False if skipped.
    """
    if not audiobook.author:
        return False

    current_path = Path(audiobook.path)
    if not current_path.exists():
        logger.warning(f"Cannot reorganize: path does not exist: {current_path}")
        return False

    config = get_config()
    library_path = Path(config.library.path)

    # Check if already in author-based structure
    # If parent is not the library root, assume it's already organized
    if current_path.parent != library_path:
        logger.debug(f"Already organized: {current_path}")
        return False

    # Create author directory
    safe_author = _sanitize_filename(audiobook.author)
    author_dir = library_path / safe_author
    author_dir.mkdir(parents=True, exist_ok=True)

    # Determine new path - use clean title if available, otherwise keep current name
    safe_title = _sanitize_filename(audiobook.title)
    new_path = author_dir / safe_title

    # Handle collision
    if new_path.exists() and new_path != current_path:
        # Add a suffix to avoid overwriting
        counter = 1
        while new_path.exists():
            new_path = author_dir / f"{safe_title}_{counter}"
            counter += 1

    if new_path == current_path:
        return False

    try:
        shutil.move(str(current_path), str(new_path))
        audiobook.path = str(new_path)
        logger.info(f"Reorganized '{audiobook.title}' to {new_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to reorganize '{audiobook.title}': {e}")
        return False


async def _update_audiobook_from_asin(
    audiobook: Audiobook, asin: str, session: AsyncSession
) -> Audiobook:
    """Fetch metadata from Audnexus and update audiobook fields."""
    client = MetadataClient()
    metadata = await client.enrich_by_asin(asin)
    if metadata is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No metadata found for ASIN: {asin}",
        )

    # Update audiobook with metadata (prefer metadata values over existing)
    audiobook.asin = asin
    audiobook.title = metadata.title or audiobook.title  # Replace torrent title with clean title
    audiobook.author = metadata.author or audiobook.author
    audiobook.narrator = metadata.narrator or audiobook.narrator
    audiobook.duration_seconds = metadata.duration_seconds or audiobook.duration_seconds
    audiobook.cover_image_url = metadata.cover_url or audiobook.cover_image_url
    audiobook.series_name = metadata.series_name or audiobook.series_name
    audiobook.series_position = metadata.series_position or audiobook.series_position
    audiobook.release_date = metadata.release_date or audiobook.release_date
    audiobook.language = metadata.language or audiobook.language

    # Keep HTML description for frontend rendering
    if metadata.description:
        audiobook.description = metadata.description

    # Reorganize to author-based folder structure if author is known
    if audiobook.author:
        _reorganize_audiobook_by_author(audiobook)

    await session.commit()
    await session.refresh(audiobook)
    return audiobook


async def _update_audiobook_from_openlibrary(
    audiobook: Audiobook, ol_key: str, session: AsyncSession
) -> Audiobook:
    """Fetch metadata from OpenLibrary and update audiobook fields."""
    client = OpenLibraryClient()
    metadata = await client.get_by_key(ol_key)
    if metadata is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No metadata found for OpenLibrary key: {ol_key}",
        )

    # Update audiobook with metadata (prefer metadata values over existing)
    audiobook.open_library_key = ol_key
    audiobook.title = metadata.title or audiobook.title
    audiobook.author = metadata.author or audiobook.author
    # OpenLibrary doesn't have narrator info
    audiobook.cover_image_url = metadata.cover_url or audiobook.cover_image_url
    audiobook.release_date = metadata.release_date or audiobook.release_date

    if metadata.description:
        audiobook.description = metadata.description

    # Reorganize to author-based folder structure if author is known
    if audiobook.author:
        _reorganize_audiobook_by_author(audiobook)

    await session.commit()
    await session.refresh(audiobook)
    return audiobook


@router.post("/{audiobook_id}/set-asin", response_model=AudiobookResponse)
async def set_audiobook_asin(
    audiobook_id: int,
    request: SetAsinRequest,
    _current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AudiobookResponse:
    """Set ASIN for an audiobook and fetch metadata from Audnexus."""
    # Validate ASIN format (must be Audible ASIN starting with B)
    asin = request.asin.upper().strip()
    if not is_valid_asin(asin):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid ASIN format: '{request.asin}'. Audible ASINs start with 'B' followed by 9 alphanumeric characters (e.g., B002VA9SWS).",
        )

    result = await session.execute(
        select(Audiobook).where(Audiobook.id == audiobook_id)
    )
    audiobook = result.scalar_one_or_none()
    if audiobook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audiobook not found",
        )

    try:
        audiobook = await _update_audiobook_from_asin(audiobook, asin, session)
        return AudiobookResponse.model_validate(audiobook)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch metadata: {str(e)}",
        )


@router.post("/{audiobook_id}/refresh-metadata", response_model=AudiobookResponse)
async def refresh_audiobook_metadata(
    audiobook_id: int,
    _current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AudiobookResponse:
    """Refresh metadata for an audiobook from ASIN (Audnexus) or OpenLibrary key."""
    result = await session.execute(
        select(Audiobook).where(Audiobook.id == audiobook_id)
    )
    audiobook = result.scalar_one_or_none()
    if audiobook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audiobook not found",
        )

    # Try ASIN first (Audnexus has richer audiobook metadata)
    if audiobook.asin:
        try:
            audiobook = await _update_audiobook_from_asin(audiobook, audiobook.asin, session)
            return AudiobookResponse.model_validate(audiobook)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to refresh metadata from Audnexus: {str(e)}",
            )

    # Fall back to OpenLibrary if we have a key
    if audiobook.open_library_key:
        try:
            audiobook = await _update_audiobook_from_openlibrary(
                audiobook, audiobook.open_library_key, session
            )
            return AudiobookResponse.model_validate(audiobook)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to refresh metadata from OpenLibrary: {str(e)}",
            )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Audiobook has no ASIN or OpenLibrary key. Use set-asin or set-openlibrary-key first.",
    )


class SetOpenLibraryKeyRequest(BaseModel):
    """Request to set OpenLibrary key and fetch metadata."""

    open_library_key: str


@router.post("/{audiobook_id}/set-openlibrary-key", response_model=AudiobookResponse)
async def set_audiobook_openlibrary_key(
    audiobook_id: int,
    request: SetOpenLibraryKeyRequest,
    _current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AudiobookResponse:
    """Set OpenLibrary key for an audiobook and fetch metadata."""
    result = await session.execute(
        select(Audiobook).where(Audiobook.id == audiobook_id)
    )
    audiobook = result.scalar_one_or_none()
    if audiobook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audiobook not found",
        )

    ol_key = request.open_library_key.strip()
    # Normalize key format
    if not ol_key.startswith("/works/"):
        ol_key = f"/works/{ol_key}"

    try:
        audiobook = await _update_audiobook_from_openlibrary(audiobook, ol_key, session)
        return AudiobookResponse.model_validate(audiobook)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch metadata from OpenLibrary: {str(e)}",
        )
