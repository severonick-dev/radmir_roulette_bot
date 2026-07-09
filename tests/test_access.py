"""Тесты слоя доступа: промокоды, лимиты, продление, гейт."""

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.access import service
from src.access.service import RedeemStatus
from src.db import models  # noqa: F401 — регистрирует таблицы
from src.db.base import Base, make_engine

NOW = datetime(2026, 7, 9, 12, 0, 0, tzinfo=timezone.utc)


@pytest_asyncio.fixture
async def db(tmp_path):
    engine = make_engine(f"sqlite+aiosqlite:///{tmp_path}/acc.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as session:
        await service.seed_promocodes(session)
        await session.commit()
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_seed_is_idempotent(db):
    added = await service.seed_promocodes(db)
    assert added == 0  # оба кода уже засеяны фикстурой


@pytest.mark.asyncio
async def test_closed_by_default(db):
    ok, until = await service.check_access(db, tg_user_id=1000, now=NOW)
    assert ok is False
    assert until is None


@pytest.mark.asyncio
async def test_admin_always_has_access(db):
    ok, _ = await service.check_access(
        db, tg_user_id=42, admin_ids=frozenset({42}), now=NOW
    )
    assert ok is True


@pytest.mark.asyncio
async def test_nekazual_grants_one_hour_then_access(db):
    r = await service.redeem_promo(db, tg_user_id=1, code="nekazual", now=NOW)
    assert r.status is RedeemStatus.OK
    assert r.access_until == NOW + timedelta(hours=1)
    ok, _ = await service.check_access(db, tg_user_id=1, now=NOW)
    assert ok is True
    # через 2 часа доступа уже нет
    ok2, _ = await service.check_access(db, tg_user_id=1, now=NOW + timedelta(hours=2))
    assert ok2 is False


@pytest.mark.asyncio
async def test_nekazual_only_once_per_account(db):
    await service.redeem_promo(db, tg_user_id=2, code="NEKAZUAL", now=NOW)
    again = await service.redeem_promo(db, tg_user_id=2, code="NEKAZUAL", now=NOW)
    assert again.status is RedeemStatus.ALREADY_USED


@pytest.mark.asyncio
async def test_gospodryad_grants_month(db):
    r = await service.redeem_promo(db, tg_user_id=3, code="GOSPODRYAD", now=NOW)
    assert r.status is RedeemStatus.OK
    assert r.access_until == NOW + timedelta(days=30)


@pytest.mark.asyncio
async def test_redeem_extends_from_current_access(db):
    # активный час + месяц => месяц добавляется к остатку, а не от now
    await service.redeem_promo(db, tg_user_id=4, code="NEKAZUAL", now=NOW)
    r = await service.redeem_promo(db, tg_user_id=4, code="GOSPODRYAD", now=NOW)
    assert r.access_until == NOW + timedelta(hours=1) + timedelta(days=30)


@pytest.mark.asyncio
async def test_unknown_and_case_insensitive(db):
    assert (await service.redeem_promo(db, tg_user_id=5, code="nope", now=NOW)).status is RedeemStatus.UNKNOWN
    # регистр и пробелы не важны
    r = await service.redeem_promo(db, tg_user_id=5, code="  gospodryad  ", now=NOW)
    assert r.status is RedeemStatus.OK
