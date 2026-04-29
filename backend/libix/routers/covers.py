"""Cover image proxy router."""

import hashlib
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..models import Audiobook, User
from .auth import get_current_user

router = APIRouter(prefix="/api/covers", tags=["covers"])

# Cache directory for cover images
CACHE_DIR = Path("/var/cache/libix/covers")


def get_cache_path(url: str) -> Path:
    """Get cache file path for a URL."""
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
    return CACHE_DIR / url_hash


async def fetch_and_cache_image(url: str) -> bytes:
    """Fetch image from URL and cache it.

    Args:
        url: Image URL to fetch.

    Returns:
        Image bytes.

    Raises:
        HTTPException: If fetch fails.
    """
    cache_path = get_cache_path(url)

    # Check cache first
    if cache_path.exists():
        return cache_path.read_bytes()

    # Fetch image
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=30.0, follow_redirects=True)
            response.raise_for_status()
            image_data = response.content
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch cover image: {e.response.status_code}",
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch cover image: {str(e)}",
        )

    # Cache the image
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(image_data)
    except OSError:
        # Cache write failed, but we still have the image
        pass

    return image_data


def guess_content_type(url: str) -> str:
    """Guess content type from URL."""
    url_lower = url.lower()
    if ".png" in url_lower:
        return "image/png"
    if ".webp" in url_lower:
        return "image/webp"
    if ".gif" in url_lower:
        return "image/gif"
    return "image/jpeg"


# NOTE: /proxy must be defined BEFORE /{audiobook_id} to avoid path parameter conflicts
# This endpoint is public (no auth) because it's accessed via <img> src which can't pass auth headers
@router.get("/proxy")
async def proxy_cover(
    url: str,
) -> Response:
    """Proxy and cache a cover image by URL.

    Used during search before audiobook is imported to library.
    This endpoint is public because img tags cannot pass Authorization headers.
    """
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    # Only allow proxying from known safe domains
    allowed_domains = ["covers.openlibrary.org", "images-na.ssl-images-amazon.com", "m.media-amazon.com"]
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.netloc not in allowed_domains:
        raise HTTPException(status_code=400, detail="URL domain not allowed")

    image_data = await fetch_and_cache_image(url)
    content_type = guess_content_type(url)

    return Response(
        content=image_data,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/{audiobook_id}")
async def get_cover(
    audiobook_id: int,
    _current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Get cover image for an audiobook.

    Fetches and caches the cover image from the original source URL.
    """
    # Get audiobook
    result = await session.execute(
        select(Audiobook).where(Audiobook.id == audiobook_id)
    )
    audiobook = result.scalar_one_or_none()

    if not audiobook:
        raise HTTPException(status_code=404, detail="Audiobook not found")

    if not audiobook.cover_image_url:
        raise HTTPException(status_code=404, detail="Audiobook has no cover image")

    image_data = await fetch_and_cache_image(audiobook.cover_image_url)
    content_type = guess_content_type(audiobook.cover_image_url)

    return Response(
        content=image_data,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )
