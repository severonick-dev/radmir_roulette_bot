"""Настройки приложения из окружения (.env)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True, slots=True)
class Settings:
    # Telegram
    bot_token: str
    admin_ids: frozenset[int]  # всегда имеют доступ (не блокируются гейтом)
    # Хранилище
    database_url: str
    # Аналитика
    analysis_window: int
    # ИИ (RouterAI, OpenAI-совместимый)
    ai_api_key: str
    ai_base_url: str
    ai_model: str
    ai_max_tokens: int
    ai_temperature: float
    # Прод
    public_url: str
    force_ipv4: bool  # форсить IPv4 к Telegram (на VDS часто сломан IPv6)
    telegram_proxy: str  # socks5://.. или http://.. — если Telegram режется с хоста
    log_level: str


def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN не задан — заполни .env (см. .env.example)")
    # только числовые id; кривые/пустые значения молча пропускаем, чтобы
    # опечатка в ADMIN_IDS не роняла весь бот при старте
    admin_ids = frozenset(
        int(x)
        for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",")
        if x.isdigit()
    )
    return Settings(
        bot_token=token,
        admin_ids=admin_ids,
        database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./radmir.db").strip(),
        analysis_window=int(os.getenv("ANALYSIS_WINDOW", "300")),
        ai_api_key=os.getenv("AI_API_KEY", "").strip(),
        ai_base_url=os.getenv("AI_BASE_URL", "https://routerai.ru/api/v1").strip(),
        ai_model=os.getenv("AI_MODEL", "deepseek/deepseek-v4-flash").strip(),
        ai_max_tokens=int(os.getenv("AI_MAX_TOKENS", "2000")),
        ai_temperature=float(os.getenv("AI_TEMPERATURE", "0.3")),
        public_url=os.getenv("PUBLIC_URL", "https://proxels-web.ru").strip(),
        force_ipv4=os.getenv("FORCE_IPV4", "1").strip().lower() in ("1", "true", "yes", "on"),
        telegram_proxy=os.getenv("TELEGRAM_PROXY", "").strip(),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
    )
