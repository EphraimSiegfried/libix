"""API routers for Libix."""

from .auth import router as auth_router
from .covers import router as covers_router
from .downloads import router as downloads_router
from .library import router as library_router
from .search import router as search_router
from .settings import router as settings_router
from .users import router as users_router

__all__ = [
    "auth_router",
    "covers_router",
    "downloads_router",
    "library_router",
    "search_router",
    "settings_router",
    "users_router",
]
