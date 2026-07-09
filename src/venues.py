"""Справочник казино и столов на Radmir RP.

Планировка залов одинаковая в обоих казино, столов везде 6.
Ключи (slug) используются в БД и колбэках бота, значения — для показа игроку.
"""

from __future__ import annotations

# slug -> отображаемое имя
CASINOS: dict[str, str] = {
    "yuzhnoe": "г. Южное",
    "lytkarino": "г. Лыткарино",
}

# Номера столов (одинаково в обоих казино).
TABLES: tuple[int, ...] = (1, 2, 3, 4, 5, 6)

# Игровые серверы Radmir. Скрипты рулетки на них могут отличаться, поэтому
# статистика хранится и анализируется РАЗДЕЛЬНО по серверам.
# TODO: заменить плейсхолдеры на реальные названия серверов.
SERVER_COUNT = 21
SERVERS: dict[str, str] = {str(i): f"Сервер {i}" for i in range(1, SERVER_COUNT + 1)}


def casino_name(slug: str) -> str:
    """Отображаемое имя казино по slug (или сам slug, если неизвестен)."""
    return CASINOS.get(slug, slug)


def server_name(slug: str) -> str:
    """Отображаемое имя сервера по slug (или сам slug, если неизвестен)."""
    return SERVERS.get(slug, slug)


def is_valid_table(number: int) -> bool:
    return number in TABLES


def is_valid_server(slug: str) -> bool:
    return slug in SERVERS


def is_valid_casino(slug: str) -> bool:
    return slug in CASINOS
