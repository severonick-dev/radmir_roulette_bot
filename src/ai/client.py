"""Асинхронный клиент к RouterAI (OpenAI-совместимый) для DeepSeek.

Важное про `deepseek/deepseek-v4-flash`:
  • это reasoning-модель — часть токенов уходит в скрытое рассуждение,
    поэтому `max_tokens` берём с запасом, иначе `content` придёт пустым;
  • без системного промпта DeepSeek может отвечать не по-русски —
    промпт с требованием русского обязателен (и он честный: не обещаем
    предсказывать случайность).
"""

from __future__ import annotations

from openai import AsyncOpenAI

from src.config import Settings, load_settings

DEFAULT_SYSTEM_PROMPT = (
    "Ты — аналитик статистики игры «Рулетка» в казино на сервере GTA SA Radmir RP. "
    "Отвечай только на русском языке, кратко и по делу. "
    "Будь честен: рулетка — генератор случайных чисел. Если в данных нет "
    "статистически значимого смещения, прямо говори, что исходы равновероятны, "
    "и не выдумывай «закономерности». Указывай на перекос только когда он "
    "подтверждён статистикой."
)


class AIClient:
    """Тонкая обёртка над chat.completions RouterAI."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._s = settings or load_settings()
        if not self._s.ai_api_key:
            raise RuntimeError(
                "AI_API_KEY не задан — заполни .env (см. .env.example), "
                "иначе ИИ-аналитика недоступна."
            )
        self._client = AsyncOpenAI(
            api_key=self._s.ai_api_key,
            base_url=self._s.ai_base_url,
        )

    async def complete(
        self,
        user_prompt: str,
        *,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Одиночный запрос к модели, возвращает текст ответа (content)."""
        resp = await self._client.chat.completions.create(
            model=self._s.ai_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens or self._s.ai_max_tokens,
            temperature=self._s.ai_temperature if temperature is None else temperature,
        )
        choice = resp.choices[0]
        content = (choice.message.content or "").strip()
        if not content:
            # У reasoning-модели весь бюджет мог уйти в рассуждение.
            raise RuntimeError(
                f"Модель вернула пустой content (finish_reason={choice.finish_reason}). "
                "Скорее всего не хватило лимита — увеличь AI_MAX_TOKENS."
            )
        return content

    async def aclose(self) -> None:
        await self._client.close()
