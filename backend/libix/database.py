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


def _migrate_add_missing_columns(connection) -> None:
    """Add missing columns to existing tables (simple migration)."""
    from sqlalchemy import inspect, text

    inspector = inspect(connection)

    # Define columns to add if missing: (table_name, column_name, column_type, default)
    migrations = [
        # Audiobook table
        ("audiobooks", "cover_image_url", "VARCHAR(2000)", None),
        ("audiobooks", "asin", "VARCHAR(20)", None),
        ("audiobooks", "series_name", "VARCHAR(500)", None),
        ("audiobooks", "series_position", "VARCHAR(20)", None),
        ("audiobooks", "release_date", "DATE", None),
        ("audiobooks", "open_library_key", "VARCHAR(50)", None),
        ("audiobooks", "indexer", "VARCHAR(100)", None),
        ("audiobooks", "source_url", "VARCHAR(2000)", None),
        ("audiobooks", "added_by_id", "INTEGER", None),
        ("audiobooks", "language", "VARCHAR(50)", None),
        # Download table
        ("downloads", "metadata_asin", "VARCHAR(20)", None),
        ("downloads", "metadata_open_library_key", "VARCHAR(50)", None),
        ("downloads", "metadata_author", "VARCHAR(255)", None),
        ("downloads", "metadata_narrator", "VARCHAR(255)", None),
        ("downloads", "metadata_description", "TEXT", None),
        ("downloads", "metadata_duration_seconds", "INTEGER", None),
        ("downloads", "metadata_cover_url", "VARCHAR(2000)", None),
        ("downloads", "metadata_series_name", "VARCHAR(500)", None),
        ("downloads", "metadata_series_position", "VARCHAR(20)", None),
        ("downloads", "metadata_language", "VARCHAR(50)", None),
    ]

    for table_name, column_name, column_type, default in migrations:
        if not inspector.has_table(table_name):
            continue

        existing_columns = {col["name"] for col in inspector.get_columns(table_name)}
        if column_name not in existing_columns:
            default_clause = f" DEFAULT {default}" if default is not None else ""
            sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}{default_clause}"
            connection.execute(text(sql))


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
        # First, run migrations to add any missing columns
        await conn.run_sync(_migrate_add_missing_columns)
        # Then create any missing tables
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
