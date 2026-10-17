"""Engine and session management for the AI-owned database.

PostgreSQL (``asyncpg``) is the deployment target; SQLite (``aiosqlite``) is used by
tests so the suite needs no external service. Schema creation is Alembic's job in
deployment and is only done inline when ``AUTO_CREATE_SCHEMA`` is enabled.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.conversations.models import Base


class Database:
    def __init__(self, url: str, *, echo: bool = False, auto_create_schema: bool = False) -> None:
        self._auto_create_schema = auto_create_schema
        self._engine: AsyncEngine = create_async_engine(url, **_engine_options(url, echo))
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    def session(self) -> AsyncSession:
        return self._session_factory()

    @asynccontextmanager
    async def session_scope(self) -> AsyncIterator[AsyncSession]:
        async with self._session_factory() as session:
            yield session

    async def start(self) -> None:
        if self._auto_create_schema:
            await self.create_schema()

    async def create_schema(self) -> None:
        async with self._engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def ping(self) -> bool:
        try:
            async with self._engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return False
        return True

    async def dispose(self) -> None:
        await self._engine.dispose()


def _engine_options(url: str, echo: bool) -> dict[str, Any]:
    options: dict[str, Any] = {"echo": echo}
    if _is_memory_sqlite(url):
        # A single shared connection keeps an in-memory SQLite schema alive across sessions.
        options["poolclass"] = StaticPool
    else:
        options["pool_pre_ping"] = True
    return options


def _is_memory_sqlite(url: str) -> bool:
    return url.startswith("sqlite") and ":memory:" in url
