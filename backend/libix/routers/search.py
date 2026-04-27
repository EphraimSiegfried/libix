"""Search router."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from ..models import User
from ..schemas.search import SearchResult
from ..services.prowlarr import ProwlarrClient
from .auth import get_current_user

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("", response_model=list[SearchResult])
async def search(
    _current_user: Annotated[User, Depends(get_current_user)],
    q: str = Query(..., min_length=1, description="Search query"),
    categories: list[int] | None = Query(None, description="Category IDs to filter by"),
) -> list[SearchResult]:
    """Search for audiobooks via Prowlarr."""
    client = ProwlarrClient()
    try:
        results = await client.search(q, categories)
        return results
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Search failed: {str(e)}",
        )
