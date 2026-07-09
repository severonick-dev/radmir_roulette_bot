"""Репозиторий: операции над сессиями и спинами.

Все запросы к спинам скоупятся по связке (server, casino, table_no) —
это единица анализа. Управление транзакцией (commit/rollback) остаётся
на вызывающей стороне (см. base.session_scope).
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Session, Spin
from src.roulette import domain
from src.roulette.domain import Difficulty


def _difficulty_str(value: Difficulty | str) -> str:
    return value.value if isinstance(value, Difficulty) else str(value)


async def create_session(
    db: AsyncSession,
    *,
    user_id: int,
    server: str,
    casino: str,
    table_no: int,
    difficulty: Difficulty | str,
) -> Session:
    """Создаёт игровую сессию и возвращает её (с проставленным id)."""
    obj = Session(
        user_id=user_id,
        server=server,
        casino=casino,
        table_no=table_no,
        difficulty=_difficulty_str(difficulty),
    )
    db.add(obj)
    await db.flush()
    return obj


async def add_spin(
    db: AsyncSession,
    *,
    server: str,
    casino: str,
    table_no: int,
    number: int,
    user_id: int | None = None,
    session_id: int | None = None,
) -> Spin:
    """Сохраняет выпавшее число; производные признаки считает домен."""
    o = domain.classify(number)  # заодно валидирует 0–36
    spin = Spin(
        server=server,
        casino=casino,
        table_no=table_no,
        number=o.number,
        color=o.color.value,
        dozen=o.dozen,
        column_no=o.column,
        half=o.half,
        even=o.even,
        wheel_index=o.wheel_index,
        user_id=user_id,
        session_id=session_id,
    )
    db.add(spin)
    await db.flush()
    return spin


def _channel(stmt, server: str, casino: str, table_no: int):
    return stmt.where(
        Spin.server == server,
        Spin.casino == casino,
        Spin.table_no == table_no,
    )


async def recent_numbers(
    db: AsyncSession,
    *,
    server: str,
    casino: str,
    table_no: int,
    limit: int = 300,
) -> list[int]:
    """Последние N чисел по столу в ХРОНОЛОГИЧЕСКОМ порядке (старые → новые).

    Порядок нужен аналитике (цепь Маркова смотрит переходы во времени).
    """
    stmt = _channel(select(Spin.number), server, casino, table_no)
    stmt = stmt.order_by(Spin.id.desc()).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return list(reversed(rows))


async def recent_spins(
    db: AsyncSession,
    *,
    server: str,
    casino: str,
    table_no: int,
    limit: int = 20,
) -> list[Spin]:
    """Последние спины по столу, НОВЫЕ СВЕРХУ (для показа истории игроку)."""
    stmt = _channel(select(Spin), server, casino, table_no)
    stmt = stmt.order_by(Spin.id.desc()).limit(limit)
    return list((await db.execute(stmt)).scalars().all())


async def count_spins(
    db: AsyncSession, *, server: str, casino: str, table_no: int
) -> int:
    """Сколько всего спинов накоплено по столу."""
    stmt = _channel(select(func.count()).select_from(Spin), server, casino, table_no)
    return int((await db.execute(stmt)).scalar_one())
