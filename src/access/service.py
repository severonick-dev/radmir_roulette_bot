"""Слой доступа: пользователи, промокоды, гейт закрытого бота.

Доступ у пользователя есть, если `access_until > now` (или он в списке админов).
Промокод продлевает доступ. Время передаётся явно (`now`) — ради
детерминизма в тестах; слой не зависит от BOT_TOKEN.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import PromoCode, PromoRedemption, User

DAY = 86_400

# Промокоды, нужные сейчас: (code, duration_seconds, per_account_limit, max_total_uses)
DEFAULT_PROMOCODES: list[tuple[str, int, int, int | None]] = [
    ("GOSPODRYAD", 30 * DAY, 1, None),  # месяц, 1 раз на аккаунт
    ("NEKAZUAL", 3600, 1, None),        # 1 час, 1 раз на аккаунт
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_code(code: str) -> str:
    return code.strip().upper()


async def get_or_create_user(
    db: AsyncSession, *, tg_user_id: int, username: str | None = None
) -> User:
    user = (
        await db.execute(select(User).where(User.tg_user_id == tg_user_id))
    ).scalar_one_or_none()
    if user is None:
        user = User(tg_user_id=tg_user_id, username=username)
        db.add(user)
        await db.flush()
    elif username and user.username != username:
        user.username = username
    return user


def user_has_access(user: User, *, now: datetime | None = None) -> bool:
    now = now or _utcnow()
    return user.access_until is not None and user.access_until > now


async def check_access(
    db: AsyncSession,
    *,
    tg_user_id: int,
    username: str | None = None,
    admin_ids: frozenset[int] = frozenset(),
    now: datetime | None = None,
) -> tuple[bool, datetime | None]:
    """Возвращает (есть_доступ, до_какого_времени). Админам — всегда True."""
    now = now or _utcnow()
    user = await get_or_create_user(db, tg_user_id=tg_user_id, username=username)
    if tg_user_id in admin_ids:
        return True, None
    return user_has_access(user, now=now), user.access_until


class RedeemStatus(str, Enum):
    OK = "ok"
    UNKNOWN = "unknown"            # нет такого кода
    INACTIVE = "inactive"         # код выключен
    ALREADY_USED = "already_used"  # лимит на аккаунт исчерпан
    EXHAUSTED = "exhausted"       # общий лимит активаций исчерпан


@dataclass(frozen=True, slots=True)
class RedeemResult:
    status: RedeemStatus
    access_until: datetime | None = None
    duration_seconds: int | None = None


async def redeem_promo(
    db: AsyncSession,
    *,
    tg_user_id: int,
    code: str,
    username: str | None = None,
    now: datetime | None = None,
) -> RedeemResult:
    """Активирует промокод: проверяет лимиты и продлевает доступ."""
    now = now or _utcnow()
    code = normalize_code(code)

    promo = (
        await db.execute(select(PromoCode).where(PromoCode.code == code))
    ).scalar_one_or_none()
    if promo is None:
        return RedeemResult(RedeemStatus.UNKNOWN)
    if not promo.active:
        return RedeemResult(RedeemStatus.INACTIVE)

    # лимит на аккаунт
    used_by_user = (
        await db.execute(
            select(func.count())
            .select_from(PromoRedemption)
            .where(
                PromoRedemption.code == code,
                PromoRedemption.tg_user_id == tg_user_id,
            )
        )
    ).scalar_one()
    if used_by_user >= promo.per_account_limit:
        return RedeemResult(RedeemStatus.ALREADY_USED)

    # общий лимит активаций
    if promo.max_total_uses is not None:
        total_used = (
            await db.execute(
                select(func.count())
                .select_from(PromoRedemption)
                .where(PromoRedemption.code == code)
            )
        ).scalar_one()
        if total_used >= promo.max_total_uses:
            return RedeemResult(RedeemStatus.EXHAUSTED)

    user = await get_or_create_user(db, tg_user_id=tg_user_id, username=username)
    # продлеваем от текущего доступа, если он ещё активен, иначе от now
    base = user.access_until if user_has_access(user, now=now) else now
    user.access_until = base + timedelta(seconds=promo.duration_seconds)

    db.add(PromoRedemption(code=code, tg_user_id=tg_user_id, redeemed_at=now))
    await db.flush()
    return RedeemResult(
        RedeemStatus.OK,
        access_until=user.access_until,
        duration_seconds=promo.duration_seconds,
    )


async def seed_promocodes(db: AsyncSession) -> int:
    """Создаёт недостающие промокоды из DEFAULT_PROMOCODES. Возвращает сколько добавил."""
    added = 0
    for code, dur, per_acc, total in DEFAULT_PROMOCODES:
        exists = (
            await db.execute(select(PromoCode.id).where(PromoCode.code == code))
        ).scalar_one_or_none()
        if exists is None:
            db.add(
                PromoCode(
                    code=code,
                    duration_seconds=dur,
                    per_account_limit=per_acc,
                    max_total_uses=total,
                    active=True,
                )
            )
            added += 1
    await db.flush()
    return added
