"""Проверка связи с ИИ (RouterAI / DeepSeek).

Запуск из корня репозитория после `pip install -r requirements.txt`:
    python -m scripts.ai_smoke
"""

from __future__ import annotations

import asyncio

from src.ai.client import AIClient


async def main() -> None:
    ai = AIClient()
    try:
        answer = await ai.complete("Ответь ровно одним словом: работает")
        print("Ответ модели:", answer)
    finally:
        await ai.aclose()


if __name__ == "__main__":
    asyncio.run(main())
