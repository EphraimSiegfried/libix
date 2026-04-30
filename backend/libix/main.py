"""FastAPI application entry point."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .auth import ensure_initial_admin
from .config import get_config, load_config, set_config
from .database import close_db, get_session, init_db
from .routers import (
    auth_router,
    covers_router,
    downloads_router,
    library_router,
    search_router,
    settings_router,
    users_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Initialize database
    await init_db()

    # Create initial admin user if needed
    async for session in get_session():
        await ensure_initial_admin(session)
        break

    yield

    # Cleanup
    await close_db()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Libix",
        description="Self-hosted audiobook management application",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Add CORS middleware for development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(search_router)
    app.include_router(downloads_router)
    app.include_router(library_router)
    app.include_router(settings_router)
    app.include_router(covers_router)

    # Health check endpoint (no auth required)
    @app.get("/api/health")
    async def health_check():
        return {"status": "ok"}

    # Serve static files if LIBIX_STATIC_DIR is set (production bundle)
    static_dir = os.environ.get("LIBIX_STATIC_DIR")
    if static_dir and Path(static_dir).exists():
        from fastapi.responses import FileResponse

        # Serve static assets (js, css, images, etc.)
        app.mount("/assets", StaticFiles(directory=Path(static_dir) / "assets"), name="assets")

        # SPA fallback - serve index.html for all non-API routes
        @app.get("/{path:path}")
        async def spa_fallback(path: str):
            # Check if it's a static file that exists
            file_path = Path(static_dir) / path
            if file_path.is_file():
                return FileResponse(file_path)
            # Otherwise serve index.html for SPA routing
            return FileResponse(Path(static_dir) / "index.html")

    return app


def main():
    """Main entry point for the application."""
    import argparse

    parser = argparse.ArgumentParser(description="Libix audiobook management server")
    parser.add_argument(
        "-c", "--config",
        help="Path to configuration file",
        default=None,
    )
    parser.add_argument(
        "--host",
        help="Host to bind to (overrides config)",
        default=None,
    )
    parser.add_argument(
        "--port",
        help="Port to bind to (overrides config)",
        type=int,
        default=None,
    )
    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)
    set_config(config)

    # Get host/port from args or config
    host = args.host or config.server.host
    port = args.port or config.server.port

    # Run the server
    app = create_app()
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
