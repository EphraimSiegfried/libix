"""Search router."""

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..models import User
from ..schemas.metadata import (
    MetadataSearchResponse,
    MetadataSearchResult,
    TorrentSearchRequest,
)
from ..schemas.search import SearchResult
from ..services.audiobookbay import AudioBookBayClient
from ..services.audnexus import MetadataClient
from ..services.prowlarr import ProwlarrClient
from .auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("", response_model=list[SearchResult])
async def search(
    _current_user: Annotated[User, Depends(get_current_user)],
    q: str = Query(..., min_length=1, description="Search query"),
    categories: list[int] | None = Query(None, description="Category IDs to filter by"),
) -> list[SearchResult]:
    """Search for audiobooks via Prowlarr and AudioBookBay."""
    prowlarr = ProwlarrClient()
    audiobookbay = AudioBookBayClient()

    # Search both sources in parallel
    async def search_prowlarr() -> list[SearchResult]:
        try:
            return await prowlarr.search(q, categories)
        except Exception as e:
            logger.warning(f"Prowlarr search failed: {e}")
            return []

    async def search_audiobookbay() -> list[SearchResult]:
        try:
            return await audiobookbay.search(q)
        except Exception as e:
            logger.warning(f"AudioBookBay search failed: {e}")
            return []

    prowlarr_results, abb_results = await asyncio.gather(
        search_prowlarr(),
        search_audiobookbay(),
    )

    # Combine results, with Prowlarr first (usually has better metadata)
    all_results = prowlarr_results + abb_results

    if not all_results:
        # If both failed, raise an error
        raise HTTPException(
            status_code=502,
            detail="Search failed: no results from any indexer",
        )

    return all_results


@router.get("/metadata", response_model=MetadataSearchResponse)
async def search_metadata(
    _current_user: Annotated[User, Depends(get_current_user)],
    q: str = Query(..., min_length=1, description="Search query"),
) -> MetadataSearchResponse:
    """Search for audiobook metadata via OpenLibrary (Stage 1)."""
    client = MetadataClient()
    try:
        results = await client.search(q)
        return MetadataSearchResponse(
            results=[
                MetadataSearchResult(
                    asin=r.asin,  # Only actual Audible ASINs
                    open_library_key=r.open_library_key,
                    title=r.title,
                    author=r.author,
                    narrator=r.narrator,
                    description=r.description,
                    duration_seconds=r.duration_seconds,
                    release_date=r.release_date,
                    cover_url=r.cover_url,
                    series_name=r.series_name,
                    series_position=r.series_position,
                    language=r.language,
                )
                for r in results
            ],
            query=q,
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Metadata search failed: {str(e)}",
        )


@router.post("/torrents", response_model=list[SearchResult])
async def search_torrents(
    _current_user: Annotated[User, Depends(get_current_user)],
    request: TorrentSearchRequest,
) -> list[SearchResult]:
    """Search for torrents for a specific audiobook (Stage 2)."""
    prowlarr = ProwlarrClient()
    audiobookbay = AudioBookBayClient()

    # Build search query from title and optionally author
    query = request.title
    if request.author:
        query = f"{request.title} {request.author}"

    # Search both sources in parallel
    async def search_prowlarr() -> list[SearchResult]:
        try:
            return await prowlarr.search(query)
        except Exception as e:
            logger.warning(f"Prowlarr torrent search failed: {e}")
            return []

    async def search_audiobookbay() -> list[SearchResult]:
        try:
            return await audiobookbay.search(query)
        except Exception as e:
            logger.warning(f"AudioBookBay torrent search failed: {e}")
            return []

    prowlarr_results, abb_results = await asyncio.gather(
        search_prowlarr(),
        search_audiobookbay(),
    )

    return prowlarr_results + abb_results


class TorrentAvailabilityRequest(BaseModel):
    """Request to check torrent availability for multiple titles."""

    items: list[TorrentSearchRequest]


class TorrentAvailabilityResult(BaseModel):
    """Availability result for a single title."""

    asin: str | None
    title: str
    available: bool
    count: int


class TorrentAvailabilityResponse(BaseModel):
    """Response with availability info for all requested titles."""

    results: list[TorrentAvailabilityResult]


@router.post("/torrents/availability", response_model=TorrentAvailabilityResponse)
async def check_torrent_availability(
    _current_user: Annotated[User, Depends(get_current_user)],
    request: TorrentAvailabilityRequest,
) -> TorrentAvailabilityResponse:
    """Check torrent availability for multiple audiobooks at once."""
    prowlarr = ProwlarrClient()
    audiobookbay = AudioBookBayClient()

    async def check_single(item: TorrentSearchRequest) -> TorrentAvailabilityResult:
        query = item.title
        if item.author:
            query = f"{item.title} {item.author}"

        # Search both sources
        async def search_prowlarr() -> list[SearchResult]:
            try:
                return await prowlarr.search(query)
            except Exception:
                return []

        async def search_abb() -> list[SearchResult]:
            try:
                return await audiobookbay.search(query, limit=5)
            except Exception:
                return []

        prowlarr_results, abb_results = await asyncio.gather(
            search_prowlarr(),
            search_abb(),
        )

        all_results = prowlarr_results + abb_results
        return TorrentAvailabilityResult(
            asin=item.asin,
            title=item.title,
            available=len(all_results) > 0,
            count=len(all_results),
        )

    # Check all items in parallel
    results = await asyncio.gather(*[check_single(item) for item in request.items])

    return TorrentAvailabilityResponse(results=list(results))


class MagnetRequest(BaseModel):
    """Request to fetch a magnet link."""

    info_url: str


class MagnetResponse(BaseModel):
    """Response with magnet link."""

    magnet_url: str | None


@router.post("/magnet", response_model=MagnetResponse)
async def get_magnet_link(
    _current_user: Annotated[User, Depends(get_current_user)],
    request: MagnetRequest,
) -> MagnetResponse:
    """Fetch magnet link for an AudioBookBay result.

    This is needed because AudioBookBay magnet links are on detail pages.
    """
    audiobookbay = AudioBookBayClient()
    magnet = await audiobookbay.get_magnet(request.info_url)
    return MagnetResponse(magnet_url=magnet)
