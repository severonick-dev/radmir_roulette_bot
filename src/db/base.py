"""Асинхронный движок и сессии SQLAlchemy 2.

Слой БД намеренно НЕ зависит от полного Settings (и от BOT_TOKEN):
берём только DATABASE_URL из окружения, чтобы хранилище можно было
тестировать и использовать изолированно от бота.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./radmir.db").strip()


class Base(DeclarativeBase):
    pass


def make_engine(url: str = DATABASE_URL) -> AsyncEngine:
    """Создаёт async-движок по URL (для тестов удобно передавать свой)."""
    return create_async_engine(url, future=True)


engine: AsyncEngine = make_engine()
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db(target: AsyncEngine | None = None) -> None:
    """Создаёт таблицы (для MVP; на проде — миграции Alembic)."""
    from src.db import models  # noqa: F401 — регистрирует модели в metadata

    eng = target or engine
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Сессия с авто-commit при успехе и rollback при ошибке."""
    async with async_session() as s:
        try:
            yield s
            await s.commit()
        except Exception:
            await s.rollback()
            raise
