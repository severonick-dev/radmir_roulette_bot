"""Инлайн-клавиатуры и callback-данные флоу."""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from src import venues
from src.bot.texts import DIFF_LABELS

# тексты кнопок reply-клавиатуры активной сессии
STATS_BTN = "📊 Статистика"
CHANGE_BTN = "🔄 Сменить стол"


class Pick(CallbackData, prefix="pick"):
    """Универсальный колбэк выбора: step = server|casino|table|diff|restart."""

    step: str
    value: str


def servers_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for slug in venues.SERVERS:  # "1".."21"
        b.button(text=slug, callback_data=Pick(step="server", value=slug))
    b.adjust(5)
    return b.as_markup()


def casino_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for slug, name in venues.CASINOS.items():
        b.button(text=name, callback_data=Pick(step="casino", value=slug))
    b.adjust(2)
    return b.as_markup()


def table_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for n in venues.TABLES:
        b.button(text=f"Стол {n}", callback_data=Pick(step="table", value=str(n)))
    b.adjust(3)
    return b.as_markup()


def difficulty_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, label in DIFF_LABELS.items():
        b.button(text=label, callback_data=Pick(step="diff", value=key))
    b.adjust(1)
    return b.as_markup()


def numpad_kb() -> ReplyKeyboardMarkup:
    """Reply-клавиатура: цифры 0–36 + действия. Тап шлёт текст кнопки."""
    b = ReplyKeyboardBuilder()
    b.button(text="0")
    for n in range(1, 37):
        b.button(text=str(n))
    b.button(text=STATS_BTN)
    b.button(text=CHANGE_BTN)
    b.adjust(1, 6, 6, 6, 6, 6, 6, 2)  # [0] / 1-6 / … / 31-36 / [действия]
    return b.as_markup(
        resize_keyboard=True,
        input_field_placeholder="Тапни выпавшее число 0–36",
    )
