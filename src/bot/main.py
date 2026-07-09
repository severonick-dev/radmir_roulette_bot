"""Точка входа бота (long-polling для MVP).

Запуск из корня репозитория:
    python -m src.bot.main
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from src.access import service
from src.ai.client import AIClient
from src.bot.handlers import router
from src.config import load_settings
from src.db.base import init_db, session_scope


async def _on_startup() -> None:
    await init_db()
    async with session_scope() as db:
        added = await service.seed_promocodes(db)
    logging.info("Промокодов засеяно: %s", added)


async def main() -> None:
    settings = load_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    bot = Bot(
        settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp["admin_ids"] = settings.admin_ids
    dp["window"] = settings.analysis_window
    dp["ai"] = AIClient(settings) if settings.ai_api_key else None
    if dp["ai"] is None:
        logging.warning("AI_API_KEY не задан — ИИ-разбор будет недоступен.")
    dp.include_router(router)

    await _on_startup()
    me = await bot.get_me()
    logging.info("Бот запущен: @%s (id=%s)", me.username, me.id)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
