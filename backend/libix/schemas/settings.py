"""Settings-related schemas."""

from pydantic import BaseModel


class ProwlarrSettings(BaseModel):
    """Prowlarr settings (safe view, no secrets)."""

    url: str
    categories: list[int]
    limit: int
    has_api_key: bool


class TransmissionSettings(BaseModel):
    """Transmission settings (safe view, no secrets)."""

    url: str
    username: str | None
    has_password: bool
    download_dir: str


class LibrarySettings(BaseModel):
    """Library settings."""

    path: str


class SettingsResponse(BaseModel):
    """Current settings (safe view, no secrets)."""

    server_port: int
    database_path: str
    library: LibrarySettings
    prowlarr: ProwlarrSettings
    transmission: TransmissionSettings


class ConnectionTestResult(BaseModel):
    """Result of a connection test."""

    success: bool
    message: str
    details: dict | None = None
