"""Проверка слоя доступа: сид промокодов + сценарий активаций.

Запуск из корня репозитория:
    python -m scripts.access_smoke
"""

from __future__ import annotations

import asyncio

from src.access import service
from src.db.base import init_db, session_scope

UID = 777


async def main() -> None:
    await init_db()

    async with session_scope() as db:
        added = await service.seed_promocodes(db)
    print(f"промокодов добавлено: {added}")

    async with session_scope() as db:
        r = await service.redeem_promo(db, tg_user_id=UID, code="nekazual")
        print(f"NEKAZUAL: {r.status.value}, доступ до {r.access_until}")

    async with session_scope() as db:
        r = await service.redeem_promo(db, tg_user_id=UID, code="NEKAZUAL")
        print(f"NEKAZUAL повторно: {r.status.value} (ожидаем already_used)")

    async with session_scope() as db:
        r = await service.redeem_promo(db, tg_user_id=UID, code="GOSPODRYAD")
        print(f"GOSPODRYAD: {r.status.value}, доступ до {r.access_until}")

    async with session_scope() as db:
        ok, until = await service.check_access(db, tg_user_id=UID)
        print(f"доступ у {UID}: {ok} (до {until})")
        ok_admin, _ = await service.check_access(
            db, tg_user_id=999, admin_ids=frozenset({999})
        )
        print(f"доступ у админа 999: {ok_admin}")
        ok_stranger, _ = await service.check_access(db, tg_user_id=555)
        print(f"доступ у случайного 555: {ok_stranger} (ожидаем False)")


if __name__ == "__main__":
    asyncio.run(main())
