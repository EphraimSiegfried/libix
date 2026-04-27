"""Settings router."""

from typing import Annotated

from fastapi import APIRouter, Depends

from ..config import get_config
from ..models import User
from ..schemas.settings import (
    ConnectionTestResult,
    LibrarySettings,
    ProwlarrSettings,
    SettingsResponse,
    TransmissionSettings,
)
from ..services.prowlarr import ProwlarrClient
from ..services.transmission import TransmissionClient
from .auth import get_current_user

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
async def get_settings(
    _current_user: Annotated[User, Depends(get_current_user)],
) -> SettingsResponse:
    """Get current settings (safe view, no secrets)."""
    config = get_config()
    return SettingsResponse(
        server_port=config.server.port,
        database_path=config.database.path,
        library=LibrarySettings(path=config.library.path),
        prowlarr=ProwlarrSettings(
            url=config.prowlarr.url,
            categories=config.prowlarr.categories,
            limit=config.prowlarr.limit,
            has_api_key=bool(config.prowlarr.get_api_key()),
        ),
        transmission=TransmissionSettings(
            url=config.transmission.url,
            username=config.transmission.username,
            has_password=bool(config.transmission.get_password()),
            download_dir=config.transmission.download_dir,
        ),
    )


@router.post("/test-prowlarr", response_model=ConnectionTestResult)
async def test_prowlarr(
    _current_user: Annotated[User, Depends(get_current_user)],
) -> ConnectionTestResult:
    """Test connection to Prowlarr."""
    client = ProwlarrClient()
    success, message, details = await client.test_connection()
    return ConnectionTestResult(success=success, message=message, details=details)


@router.post("/test-transmission", response_model=ConnectionTestResult)
async def test_transmission(
    _current_user: Annotated[User, Depends(get_current_user)],
) -> ConnectionTestResult:
    """Test connection to Transmission."""
    client = TransmissionClient()
    success, message, details = client.test_connection()
    return ConnectionTestResult(success=success, message=message, details=details)
