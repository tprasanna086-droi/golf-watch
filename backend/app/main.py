"""FastAPI application entry point for GLOF Watch."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from urllib.parse import urlparse, urlunparse

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import _async_database_url, init_db

APP_VERSION = "0.1.0"
SERVICE_NAME = "glof-watch"
MAX_DB_INIT_RETRIES = 5
DB_INIT_RETRY_DELAY_SEC = 2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


def mask_database_url(url: str) -> str:
    """Return a database URL with the password redacted for safe logging."""
    parsed = urlparse(url)
    if not parsed.password:
        return url
    host = parsed.hostname or ""
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"
    user = parsed.username or ""
    masked_netloc = f"{user}:****@{host}" if user else f"****@{host}"
    return urlunparse(parsed._replace(netloc=masked_netloc))


async def _init_db_with_retry() -> None:
    """Apply the database schema, retrying when Postgres is not yet available."""
    for attempt in range(1, MAX_DB_INIT_RETRIES + 1):
        try:
            await init_db()
            logger.info("Database schema initialized (attempt %d)", attempt)
            return
        except Exception:
            logger.warning(
                "Database initialization failed (attempt %d/%d)",
                attempt,
                MAX_DB_INIT_RETRIES,
                exc_info=True,
            )
            if attempt >= MAX_DB_INIT_RETRIES:
                logger.error(
                    "Database initialization failed after %d attempts",
                    MAX_DB_INIT_RETRIES,
                )
                raise
            await asyncio.sleep(DB_INIT_RETRY_DELAY_SEC)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup tasks before serving requests."""
    database_url = _async_database_url()
    logger.info("Starting %s API v%s", SERVICE_NAME, APP_VERSION)
    logger.info("Database URL: %s", mask_database_url(database_url))
    await _init_db_with_retry()
    yield


app = FastAPI(
    title="GLOF Watch API",
    version=APP_VERSION,
    description="Glacial Lake Outburst Flood early warning system for Nepal",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# TODO: implement app.routers.lakes and remove the ImportError guard when ready.
try:
    from app.routers import lakes as lakes_router

    app.include_router(lakes_router.router, prefix="/api/v1")
    logger.info("Mounted lakes router at /api/v1")
except ImportError:
    logger.warning(
        "app.routers.lakes not found; lakes routes will not be mounted yet"
    )


@app.get("/health")
async def health():
    """Liveness probe for load balancers and orchestrators."""
    return {
        "status": "ok",
        "version": APP_VERSION,
        "service": SERVICE_NAME,
    }


@app.get("/")
async def root():
    """Root welcome endpoint."""
    return {
        "message": "Welcome to the GLOF Watch API",
        "status": "ok",
        "version": APP_VERSION,
        "service": SERVICE_NAME,
    }
