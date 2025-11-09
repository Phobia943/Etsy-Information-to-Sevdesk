"""
FastAPI main application entry point.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import get_logger, setup_logging

# Setup logging on import
setup_logging()

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan handler.

    Runs on startup and shutdown for resource management.
    """
    # Startup
    logger.info(
        "Starting Etsy-sevDesk Sync API",
        extra={
            "version": "1.0.0",
            "environment": settings.app_env,
            "dry_run": settings.dry_run,
        },
    )

    # TODO: Initialize database connection pool, caches, etc.

    yield

    # Shutdown
    logger.info("Shutting down Etsy-sevDesk Sync API")

    # TODO: Close database connections, cleanup resources


# Create FastAPI application
app = FastAPI(
    title="Etsy-sevDesk Synchronization API",
    description="Production-ready automation for syncing Etsy orders, fees, and payouts to sevDesk",
    version="1.0.0",
    docs_url="/docs" if settings.enable_api_docs else None,
    redoc_url="/redoc" if settings.enable_api_docs else None,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """
    Health check endpoint.

    Returns:
        Status and version information
    """
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.app_env,
    }


@app.get("/")
async def root() -> dict[str, str]:
    """
    Root endpoint.

    Returns:
        Welcome message
    """
    return {
        "message": "Etsy-sevDesk Synchronization API",
        "version": "1.0.0",
        "docs": "/docs" if settings.enable_api_docs else "disabled",
    }


# TODO: Add additional API routes
# from app.api.routes import admin, webhooks
# app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
# app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])


@app.exception_handler(Exception)
async def global_exception_handler(request: Any, exc: Exception) -> JSONResponse:
    """
    Global exception handler for unhandled errors.

    Args:
        request: Request that caused the exception
        exc: Exception that was raised

    Returns:
        JSON error response
    """
    logger.error(
        "Unhandled exception",
        extra={
            "path": str(request.url),
            "method": request.method,
            "error": str(exc),
        },
        exc_info=True,
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if settings.debug else "An unexpected error occurred",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.is_development,
        log_level=settings.log_level.lower(),
    )
