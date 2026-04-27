"""Pydantic schemas for API request/response validation."""

from .auth import Token, TokenData, UserCreate, UserResponse, UserUpdate
from .download import DownloadCreate, DownloadResponse
from .library import AudiobookResponse
from .search import SearchResult
from .settings import ConnectionTestResult, SettingsResponse

__all__ = [
    "Token",
    "TokenData",
    "UserCreate",
    "UserResponse",
    "UserUpdate",
    "SearchResult",
    "DownloadCreate",
    "DownloadResponse",
    "AudiobookResponse",
    "SettingsResponse",
    "ConnectionTestResult",
]
