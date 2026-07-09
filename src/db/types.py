"""Кастомные типы столбцов SQLAlchemy."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator):
    """Хранит время как UTC, на чтении ВСЕГДА возвращает tz-aware UTC.

    SQLite не сохраняет tzinfo (вернул бы «наивный» datetime, что ломает
    сравнения с aware-временем). Нормализуем сами — единообразно работает
    и на SQLite (dev), и на Postgres (прод).
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)
