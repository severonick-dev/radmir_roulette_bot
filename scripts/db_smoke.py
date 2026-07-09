"""Проверка слоя БД: создаёт таблицы, пишет спины, читает обратно.

Запуск из корня репозитория:
    python -m scripts.db_smoke
Пишет в БД из DATABASE_URL (по умолчанию ./radmir.db).
"""

from __future__ import annotations

import asyncio

from src.db import repo
from src.db.base import init_db, session_scope


async def main() -> None:
    await init_db()

    async with session_scope() as db:
        sess = await repo.create_session(
            db, user_id=123, server="1", casino="yuzhnoe", table_no=3,
            difficulty="numbers",
        )
        for n in [0, 32, 15, 19, 4, 32, 32]:
            await repo.add_spin(
                db, server="1", casino="yuzhnoe", table_no=3, number=n,
                user_id=123, session_id=sess.id,
            )

    async with session_scope() as db:
        total = await repo.count_spins(db, server="1", casino="yuzhnoe", table_no=3)
        chrono = await repo.recent_numbers(
            db, server="1", casino="yuzhnoe", table_no=3, limit=300
        )
        last3 = await repo.recent_spins(
            db, server="1", casino="yuzhnoe", table_no=3, limit=3
        )

    print(f"канал: сервер=1 / казино=yuzhnoe / стол=3")
    print(f"всего спинов на столе: {total}")
    print(f"числа (хронологически): {chrono}")
    print("последние 3 (новые сверху):")
    for s in last3:
        print(f"  #{s.number}  {s.color}  дюжина={s.dozen}  колонка={s.column_no}")


if __name__ == "__main__":
    asyncio.run(main())
