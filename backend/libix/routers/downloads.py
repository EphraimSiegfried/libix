"""Downloads management router."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..models import Download, DownloadStatus, User
from ..schemas.download import DownloadCreate, DownloadResponse
from ..services.transmission import TransmissionClient
from .auth import get_current_user

router = APIRouter(prefix="/api/downloads", tags=["downloads"])


@router.get("", response_model=list[DownloadResponse])
async def list_downloads(
    _current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[DownloadResponse]:
    """List all downloads."""
    result = await session.execute(
        select(Download).order_by(Download.created_at.desc())
    )
    downloads = result.scalars().all()

    # Update status from Transmission for active downloads
    client = TransmissionClient()
    for download in downloads:
        if download.transmission_id and download.status in (
            DownloadStatus.PENDING,
            DownloadStatus.DOWNLOADING,
            DownloadStatus.SEEDING,
        ):
            torrent = client.get_torrent(download.transmission_id)
            if torrent:
                download.progress = torrent["progress"]
                if torrent["progress"] >= 100:
                    download.status = DownloadStatus.SEEDING
                elif torrent["error"]:
                    download.status = DownloadStatus.FAILED
                    download.error_message = torrent["error_string"]
                else:
                    download.status = DownloadStatus.DOWNLOADING

    await session.commit()
    return [DownloadResponse.model_validate(d) for d in downloads]


@router.post("", response_model=DownloadResponse, status_code=status.HTTP_201_CREATED)
async def add_download(
    download_data: DownloadCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DownloadResponse:
    """Add a new download to Transmission."""
    # Determine what to download
    url_or_magnet = download_data.magnet_url or download_data.download_url
    if not url_or_magnet:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either download_url or magnet_url must be provided",
        )

    # Create download record
    download = Download(
        title=download_data.title,
        source_url=download_data.download_url,
        magnet_or_torrent=url_or_magnet,
        status=DownloadStatus.PENDING,
        size_bytes=download_data.size,
        indexer=download_data.indexer,
        added_by_id=current_user.id,
    )
    session.add(download)
    await session.flush()
    await session.refresh(download)  # Load server-generated defaults

    # Add to Transmission
    try:
        client = TransmissionClient()
        result = client.add_torrent(url_or_magnet)
        download.transmission_id = result["id"]
        download.status = DownloadStatus.DOWNLOADING
    except Exception as e:
        download.status = DownloadStatus.FAILED
        download.error_message = str(e)

    await session.commit()
    await session.refresh(download)  # Ensure all server-side values are loaded
    return DownloadResponse.model_validate(download)


@router.get("/{download_id}", response_model=DownloadResponse)
async def get_download(
    download_id: int,
    _current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DownloadResponse:
    """Get download status."""
    result = await session.execute(
        select(Download).where(Download.id == download_id)
    )
    download = result.scalar_one_or_none()
    if download is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Download not found",
        )

    # Update status from Transmission
    if download.transmission_id and download.status in (
        DownloadStatus.PENDING,
        DownloadStatus.DOWNLOADING,
        DownloadStatus.SEEDING,
    ):
        client = TransmissionClient()
        torrent = client.get_torrent(download.transmission_id)
        if torrent:
            download.progress = torrent["progress"]
            if torrent["progress"] >= 100:
                download.status = DownloadStatus.SEEDING
            elif torrent["error"]:
                download.status = DownloadStatus.FAILED
                download.error_message = torrent["error_string"]
            else:
                download.status = DownloadStatus.DOWNLOADING
            await session.commit()

    return DownloadResponse.model_validate(download)


@router.delete("/{download_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_download(
    download_id: int,
    _current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    delete_data: bool = False,
) -> None:
    """Cancel/remove a download."""
    result = await session.execute(
        select(Download).where(Download.id == download_id)
    )
    download = result.scalar_one_or_none()
    if download is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Download not found",
        )

    # Remove from Transmission if present
    if download.transmission_id:
        client = TransmissionClient()
        client.remove_torrent(download.transmission_id, delete_data=delete_data)

    download.status = DownloadStatus.CANCELLED
    await session.commit()
