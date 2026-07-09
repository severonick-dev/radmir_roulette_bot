"""Модели БД: игровые сессии и спины (выпавшие числа).

Единица анализа — связка СЕРВЕР → КАЗИНО → СТОЛ: скрипты рулетки на разных
серверах Radmir отличаются, поэтому данные хранятся раздельно.

Производные признаки числа (цвет, дюжина, колонка, …) денормализованы в
таблицу `spins` — их считает доменный модуль при вставке, а аналитике так
не нужно пересчитывать при каждом запросе (GROUP BY color/dozen и т.п.).
Полная история не обрезается; окно анализа ограничивается на стороне запроса.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base
from src.db.types import UTCDateTime


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Session(Base):
    """Сеанс игры: пользователь сел за стол конкретного сервера/казино."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    server: Mapped[str] = mapped_column(String(32), index=True)
    casino: Mapped[str] = mapped_column(String(32), index=True)
    table_no: Mapped[int] = mapped_column(Integer)
    difficulty: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=_utcnow
    )

    spins: Mapped[list["Spin"]] = relationship(back_populates="session")


class Spin(Base):
    """Одно выпавшее число на столе (+ производные признаки)."""

    __tablename__ = "spins"
    __table_args__ = (
        # ключевой индекс под запрос «последние N по серверу+казино+столу»
        Index("ix_spins_channel_id", "server", "casino", "table_no", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    server: Mapped[str] = mapped_column(String(32))
    casino: Mapped[str] = mapped_column(String(32))
    table_no: Mapped[int] = mapped_column(Integer)

    number: Mapped[int] = mapped_column(Integer)
    color: Mapped[str] = mapped_column(String(8))
    dozen: Mapped[int] = mapped_column(Integer)
    column_no: Mapped[int] = mapped_column(Integer)  # 'column' — зарезервировано в SQL
    half: Mapped[int] = mapped_column(Integer)
    even: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # None для зеро
    wheel_index: Mapped[int] = mapped_column(Integer)

    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("sessions.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=_utcnow, index=True
    )

    session: Mapped["Session | None"] = relationship(back_populates="spins")


class User(Base):
    """Пользователь Telegram. Доступ есть, если access_until > now (или админ)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    access_until: Mapped[datetime | None] = mapped_column(
        UTCDateTime, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=_utcnow
    )


class PromoCode(Base):
    """Промокод: добавляет duration_seconds доступа при активации."""

    __tablename__ = "promo_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # UPPER
    duration_seconds: Mapped[int] = mapped_column(Integer)
    per_account_limit: Mapped[int] = mapped_column(Integer, default=1)
    max_total_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None=∞
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=_utcnow
    )


class PromoRedemption(Base):
    """Факт активации промокода конкретным аккаунтом."""

    __tablename__ = "promo_redemptions"
    __table_args__ = (
        Index("ix_redemption_code_user", "code", "tg_user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), index=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    redeemed_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=_utcnow
    )
