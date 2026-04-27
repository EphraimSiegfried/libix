"""Library management router."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_config
from ..database import get_session
from ..models import Audiobook, Download, User
from ..models.download import DownloadStatus
from ..schemas.library import AudiobookResponse
from ..services import LibraryImportError, import_download_to_library
from .auth import get_current_user

router = APIRouter(prefix="/api/library", tags=["library"])


@router.get("", response_model=list[AudiobookResponse])
async def list_audiobooks(
    _current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[AudiobookResponse]:
    """List all audiobooks in the library."""
    result = await session.execute(
        select(Audiobook).order_by(Audiobook.added_at.desc())
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
        select(Audiobook).where(Audiobook.id == audiobook_id)
    )
    audiobook = result.scalar_one_or_none()
    if audiobook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audiobook not found",
        )
    return AudiobookResponse.model_validate(audiobook)


@router.post("/scan", status_code=status.HTTP_202_ACCEPTED)
async def scan_library(
    _current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Scan library directory and add new audiobooks.

    This is a basic implementation that looks for directories in the library path.
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

    for item in library_path.iterdir():
        if not item.is_dir():
            continue

        # Check if already in database
        result = await session.execute(
            select(Audiobook).where(Audiobook.path == str(item))
        )
        if result.scalar_one_or_none():
            skipped += 1
            continue

        # Calculate size
        size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())

        # Add to database (using directory name as title)
        audiobook = Audiobook(
            title=item.name,
            path=str(item),
            size_bytes=size,
        )
        session.add(audiobook)
        added += 1

    await session.commit()
    return {"added": added, "skipped": skipped}


@router.post("/import/{download_id}", response_model=AudiobookResponse)
async def import_download_endpoint(
    download_id: int,
    _current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AudiobookResponse:
    """Import a completed download to the library.

    Moves files from download directory to library and creates an Audiobook record.
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
        audiobook = await import_download_to_library(
            download, session, delete_after_import=True
        )
        return AudiobookResponse.model_validate(audiobook)
    except LibraryImportError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
