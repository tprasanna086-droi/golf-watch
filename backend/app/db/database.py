"""Async SQLAlchemy engine, session factory, and schema initialization."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger(__name__)

_DEFAULT_DATABASE_URL = (
    "postgresql+asyncpg://glof:glof@localhost:5432/glofwatch"
)

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

load_dotenv(_BACKEND_ROOT / ".env")


def _async_database_url() -> str:
    """Return DATABASE_URL, normalized for the asyncpg driver."""
    url = os.getenv("DATABASE_URL", _DEFAULT_DATABASE_URL)
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


engine = create_async_engine(_async_database_url(), echo=False)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def _schema_statements(schema_sql: str) -> list[str]:
    """Split schema.sql into individual statements for asyncpg execution."""
    lines: list[str] = []
    for line in schema_sql.splitlines():
        code = line.split("--", 1)[0]
        if code.strip():
            lines.append(code)
    body = "\n".join(lines)
    return [stmt.strip() for stmt in body.split(";") if stmt.strip()]


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for FastAPI dependency injection."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Apply backend/app/db/schema.sql to the live database."""
    try:
        schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
        statements = _schema_statements(schema_sql)
        connectable = engine.execution_options(isolation_level="AUTOCOMMIT")
        async with connectable.connect() as conn:
            for statement in statements:
                await conn.execute(text(statement))
        logger.info("Database schema applied from %s", _SCHEMA_PATH)
    except Exception:
        logger.exception("Failed to apply database schema")
        raise
