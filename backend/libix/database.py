"""SQLite database setup with SQLAlchemy."""

from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import get_config


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


# Engine and session factory (initialized lazily)
_engine = None
_async_session_factory = None


def get_database_url() -> str:
    """Get the SQLite database URL from config."""
    config = get_config()
    db_path = config.database.path
    return f"sqlite+aiosqlite:///{db_path}"


def ensure_db_directory() -> None:
    """Ensure the database directory exists."""
    config = get_config()
    db_path = Path(config.database.path)
    db_path.parent.mkdir(parents=True, exist_ok=True)


async def init_db() -> None:
    """Initialize the database, creating tables if needed."""
    global _engine, _async_session_factory

    ensure_db_directory()

    _engine = create_async_engine(
        get_database_url(),
        echo=False,
    )

    # Enable foreign keys for SQLite
    @event.listens_for(_engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    _async_session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Import models to ensure they're registered
    from . import models  # noqa: F401

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session."""
    if _async_session_factory is None:
        await init_db()

    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def close_db() -> None:
    """Close the database connection."""
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None
