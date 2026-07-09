"""Тесты слоя БД (репозиторий) на временной SQLite-базе."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.db import models, repo  # noqa: F401 — models регистрирует таблицы
from src.db.base import Base, make_engine


@pytest_asyncio.fixture
async def db(tmp_path):
    engine = make_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as session:
        yield session
    await engine.dispose()


async def _add(db, **kw):
    kw.setdefault("server", "1")
    kw.setdefault("casino", "yuzhnoe")
    return await repo.add_spin(db, **kw)


@pytest.mark.asyncio
async def test_add_spin_fills_derived_fields(db):
    await _add(db, table_no=3, number=32)
    await db.commit()
    spins = await repo.recent_spins(db, server="1", casino="yuzhnoe", table_no=3)
    assert len(spins) == 1
    s = spins[0]
    assert s.number == 32
    assert s.color == "red"
    assert s.dozen == 3
    assert s.column_no == 2
    assert s.even is True


@pytest.mark.asyncio
async def test_zero_has_null_even(db):
    await _add(db, casino="lytkarino", table_no=1, number=0)
    await db.commit()
    s = (await repo.recent_spins(db, server="1", casino="lytkarino", table_no=1))[0]
    assert s.color == "green"
    assert s.dozen == 0
    assert s.even is None


@pytest.mark.asyncio
async def test_recent_numbers_is_chronological(db):
    for n in [5, 10, 15, 20]:
        await _add(db, table_no=2, number=n)
    await db.commit()
    got = await repo.recent_numbers(db, server="1", casino="yuzhnoe", table_no=2)
    assert got == [5, 10, 15, 20]


@pytest.mark.asyncio
async def test_limit_keeps_last_n_chronological(db):
    for n in range(1, 11):  # 1..10
        await _add(db, table_no=4, number=n)
    await db.commit()
    got = await repo.recent_numbers(db, server="1", casino="yuzhnoe", table_no=4, limit=3)
    assert got == [8, 9, 10]  # последние 3 в хронологическом порядке


@pytest.mark.asyncio
async def test_servers_are_isolated(db):
    # один и тот же казино+стол, но разные серверы — данные не смешиваются
    await _add(db, server="1", table_no=1, number=7)
    await _add(db, server="2", table_no=1, number=8)
    await db.commit()
    assert await repo.recent_numbers(db, server="1", casino="yuzhnoe", table_no=1) == [7]
    assert await repo.recent_numbers(db, server="2", casino="yuzhnoe", table_no=1) == [8]
    assert await repo.count_spins(db, server="1", casino="yuzhnoe", table_no=1) == 1


@pytest.mark.asyncio
async def test_tables_are_isolated(db):
    await _add(db, table_no=1, number=7)
    await _add(db, table_no=2, number=8)
    await db.commit()
    assert await repo.count_spins(db, server="1", casino="yuzhnoe", table_no=1) == 1
    assert await repo.recent_numbers(db, server="1", casino="yuzhnoe", table_no=2) == [8]


@pytest.mark.asyncio
async def test_create_session_and_link(db):
    sess = await repo.create_session(
        db, user_id=42, server="3", casino="yuzhnoe", table_no=5, difficulty="easy"
    )
    await db.commit()
    assert sess.id is not None
    spin = await _add(
        db, server="3", table_no=5, number=1, user_id=42, session_id=sess.id
    )
    await db.commit()
    assert spin.session_id == sess.id
